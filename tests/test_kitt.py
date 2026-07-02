"""Tests for KITT — Meteor's agent persona + orchestration hardening.

Covers the persona/system-prompt builder, retry-safety classification, transient
error detection, recovery hints, plan parsing, and the end-to-end AgentChatLoop
behaviours: transient retries on read/recon ops, NO retries on mutating ops,
multi-step plan surfacing, and parallel fan-out of independent calls.
"""

from __future__ import annotations

from collections import deque
from typing import Iterator

import pytest

from app.agent import kitt
from app.agent.chatbot_loop import AgentChatLoop, AgentTurn
from app.models.contract import ModelAdapter, ModelInput, ModelOutput
from app.runtime.tool_executor import ToolExecutor, ToolResult, ToolResultStatus


# ── Test doubles ──────────────────────────────────────────────────────────────

class ScriptedModel(ModelAdapter):
    """Yields a pre-scripted response per iteration; records the inputs so tests
    can assert what feedback the loop fed back."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0
        self.inputs: list[ModelInput] = []

    def _next(self) -> str:
        r = self._responses[self.calls] if self.calls < len(self._responses) else ""
        self.calls += 1
        return r

    def stream(self, input: ModelInput) -> Iterator[str]:
        self.inputs.append(input)
        text = self._next()
        # Emit in small chunks so the loop's peek/streaming logic is exercised.
        for i in range(0, len(text), 6):
            yield text[i:i + 6]

    def complete(self, input: ModelInput) -> ModelOutput:
        self.inputs.append(input)
        return ModelOutput(response_text=self._next(), finish_reason="stop")

    def health(self) -> dict:
        return {"healthy": True}

    def fed_back_text(self) -> str:
        """All feedback the loop injected as user turns after the first prompt."""
        chunks = []
        for inp in self.inputs:
            for msg in inp.metadata.get("chat_messages", []):
                if msg["role"] == "user":
                    chunks.append(msg["content"])
        return "\n".join(chunks)


class ScriptedExecutor:
    """Minimal ToolExecutor stand-in. Reuses the real CAPABILITIES (so the
    persona prompt is realistic) and returns scripted results per (tool, op)."""

    CAPABILITIES = ToolExecutor.CAPABILITIES

    def __init__(self, script: dict | None = None) -> None:
        self._script: dict = script or {}
        self.calls: list[tuple[str, str, dict]] = []

    def execute(self, tool: str, operation: str, params=None, session_id: str = "") -> ToolResult:
        self.calls.append((tool, operation, dict(params or {})))
        seq = self._script.get((tool, operation))
        if seq:
            return seq.popleft() if len(seq) > 1 else seq[0]
        return ToolResult(tool=tool, operation=operation, status=ToolResultStatus.OK, result="ok")

    def count(self, tool: str, operation: str) -> int:
        return sum(1 for t, o, _ in self.calls if t == tool and o == operation)


def _ok(tool, op, result="ok") -> ToolResult:
    return ToolResult(tool=tool, operation=op, status=ToolResultStatus.OK, result=result)


def _err(tool, op, error, status=ToolResultStatus.ERROR) -> ToolResult:
    return ToolResult(tool=tool, operation=op, status=status, error=error)


def _events_of(events, kind):
    return [p for k, p in events if k == kind]


def _run(model, executor, prompt="do it", **turn_kw):
    loop = AgentChatLoop(model=model, tools=executor)
    events: list[tuple[str, dict]] = []
    turn = AgentTurn(prompt=prompt, retry_backoff_s=0.0, **turn_kw)  # no real sleeping
    final, results = loop.run(turn, on_event=lambda k, p: events.append((k, p)))
    return final, results, events


# ── Persona / system prompt ─────────────────────────────────────────────────

def test_system_prompt_is_kitt_and_documents_every_cap():
    prompt = kitt.build_system_prompt(ScriptedExecutor())
    assert "KITT" in prompt
    # Doctrine surfaces: planning, parallel fan-out, recovery, the graph memory.
    low = prompt.lower()
    assert "plan" in low
    assert "parallel" in low
    assert "recover" in low
    assert "graph" in low
    # Every capability is listed and the count is stated.
    caps = ScriptedExecutor.CAPABILITIES
    assert f"{len(caps)} capabilities" in prompt
    for tool_op in caps:
        assert tool_op in prompt
    # Grouped by tool namespace.
    assert "[filesystem]" in prompt and "[graph]" in prompt


def test_default_persona_is_kitt_but_overridable():
    ex = ScriptedExecutor()
    assert AgentChatLoop(model=ScriptedModel([]), tools=ex)._system_prompt_override is None
    custom = AgentChatLoop(model=ScriptedModel([]), tools=ex, system_prompt="CUSTOM")
    assert custom._system_prompt_override == "CUSTOM"


# ── Retry-safety classification ───────────────────────────────────────────────

@pytest.mark.parametrize("tool,op,safe", [
    ("filesystem", "read", True),
    ("filesystem", "list", True),
    ("graph", "query", True),
    ("process", "list", True),
    ("keychain", "retrieve", True),
    ("filesystem", "write", False),   # mutating
    ("filesystem", "remove", False),
    ("shell", "run", False),          # executes code
    ("nmap", "scan", False),          # active scan — never auto-retry
    ("grinder", "grind_subnet", False),  # offensive
])
def test_is_retry_safe(tool, op, safe):
    assert kitt.is_retry_safe(tool, op) is safe


@pytest.mark.parametrize("error,transient", [
    ("read timed out", True),
    ("Connection reset by peer", True),
    ("HTTP 503 Service Unavailable", True),
    ("rate limit exceeded", True),
    ("missing required parameter 'path'", False),
    ("no such file or directory", False),
    ("", False),
    (None, False),
])
def test_is_transient_error(error, transient):
    assert kitt.is_transient_error(error) is transient


# ── Recovery hints ────────────────────────────────────────────────────────────

def test_recovery_hint_denied_says_do_not_retry():
    hint = kitt.recovery_hint("policy_denied", "grinder", "grind_subnet", "gated", 1)
    assert "do not retry" in hint.lower()


def test_recovery_hint_budget_says_stop():
    hint = kitt.recovery_hint("budget_exhausted", "x", "y", "", 1)
    assert "stop calling tools" in hint.lower()


def test_recovery_hint_transient_vs_hard():
    transient = kitt.recovery_hint("error", "web", "search", "read timed out", 3)
    assert "transient" in transient.lower()
    hard = kitt.recovery_hint("error", "filesystem", "read", "no such file", 1)
    assert "hard error" in hard.lower()


# ── Plan parsing ──────────────────────────────────────────────────────────────

def test_parse_plan_from_fenced_block():
    text = '```json\n{"plan": ["recon", "map", "report"]}\n```'
    assert kitt.parse_plan(text) == ["recon", "map", "report"]


def test_parse_plan_ignores_tool_calls_and_prose():
    assert kitt.parse_plan('{"tool":"shell","operation":"run","params":{}}') is None
    assert kitt.parse_plan("just a normal answer") is None


def test_parse_plan_caps_steps():
    steps = [f"s{i}" for i in range(40)]
    import json
    got = kitt.parse_plan(json.dumps({"plan": steps}))
    assert got is not None and len(got) == kitt._MAX_PLAN_STEPS


# ── End-to-end loop: retries ──────────────────────────────────────────────────

def test_readonly_op_retries_on_transient_then_succeeds():
    model = ScriptedModel([
        '{"tool": "filesystem", "operation": "read", "params": {"path": "/x"}}',
        "Here is the file content.",
    ])
    ex = ScriptedExecutor({
        ("filesystem", "read"): deque([
            _err("filesystem", "read", "read timed out"),
            _ok("filesystem", "read", "hello world"),
        ]),
    })
    final, results, events = _run(model, ex, max_tool_retries=2)

    assert ex.count("filesystem", "read") == 2          # retried once
    assert len(_events_of(events, "tool_retry")) == 1
    assert results[-1].status is ToolResultStatus.OK
    assert _events_of(events, "tool_result")[-1]["attempts"] == 2
    assert final == "Here is the file content."


def test_mutating_op_is_never_retried_and_gets_recovery_hint():
    model = ScriptedModel([
        '{"tool": "shell", "operation": "run", "params": {"command": "ls"}}',
        "Could not run that, moving on.",
    ])
    ex = ScriptedExecutor({
        ("shell", "run"): deque([_err("shell", "run", "connection reset")]),
    })
    final, results, events = _run(model, ex, max_tool_retries=3)

    assert ex.count("shell", "run") == 1                # NOT retried despite transient
    assert _events_of(events, "tool_retry") == []
    # Recovery guidance was fed back to the model.
    assert "RECOVER" in model.fed_back_text()


def test_denied_op_not_retried():
    model = ScriptedModel([
        '{"tool": "grinder", "operation": "grind_subnet", "params": {"cidr": "10.0.0.0/24"}}',
        "Need authorization for that.",
    ])
    ex = ScriptedExecutor({
        ("grinder", "grind_subnet"): deque([
            _err("grinder", "grind_subnet", "offensive gate", status=ToolResultStatus.POLICY_DENIED),
        ]),
    })
    _run(model, ex, max_tool_retries=3)
    assert ex.count("grinder", "grind_subnet") == 1
    assert "do not retry" in model.fed_back_text().lower()


# ── End-to-end loop: planning ─────────────────────────────────────────────────

def test_plan_is_surfaced_then_executed():
    model = ScriptedModel([
        '```json\n{"plan": ["list processes", "wrap up"]}\n```',
        '{"tool": "process", "operation": "list", "params": {}}',
        "All processes listed.",
    ])
    ex = ScriptedExecutor()
    final, results, events = _run(model, ex)

    plans = _events_of(events, "plan")
    assert plans and plans[0]["steps"] == ["list processes", "wrap up"]
    assert ex.count("process", "list") == 1
    assert final == "All processes listed."


# ── End-to-end loop: parallel fan-out ─────────────────────────────────────────

def test_parallel_array_runs_all_independent_calls():
    model = ScriptedModel([
        '[{"tool": "process", "operation": "list", "params": {}}, '
        '{"tool": "process", "operation": "stats", "params": {}}]',
        "System looks healthy.",
    ])
    ex = ScriptedExecutor()
    final, results, events = _run(model, ex)

    assert ex.count("process", "list") == 1
    assert ex.count("process", "stats") == 1
    assert len(results) == 2
    assert final == "System looks healthy."


def test_build_mcp_instructions_mentions_kitt_and_graph():
    ex = ToolExecutor()
    text = kitt.build_mcp_instructions(ex, visible_count=42)
    assert "KITT" in text
    assert "graph__query" in text
    assert "42" in text
    assert "arsenal__detect" in text

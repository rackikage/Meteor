"""Agentic chat loop — Claude Code-style tool-using assistant.

The loop:
    1. Build a system prompt that documents every registered tool.
    2. Stream a completion from the model. Peek the first non-whitespace bytes:
       * looks like a fenced JSON / bare `{` → probably a tool call. Buffer the
         whole stream silently and parse it after the model stops.
       * anything else → prose final answer. Flush tokens straight to the UI
         as they arrive.
    3. If we parsed tool calls, execute them (in parallel when there are ≥2)
       and feed the results back for another iteration.
    4. If we streamed prose, we're already done.
    5. Cap at `max_iterations` rounds so a confused model can't spin forever.

Events surfaced via the callback so the GUI can render progress:
    "thinking"          → model is generating
    "plan"              → KITT laid out a multi-step plan {steps}
    "tool_call"         → about to execute {tool, operation, params}
    "tool_retry"        → retrying a transient failure {tool, operation, attempt, max, error}
    "tool_result"       → tool returned {tool, operation, status, result_preview, attempts}
    "final_start"       → first prose byte of the final answer is coming
    "final_token"       → one chunk of the final answer (for streaming render)
    "final_done"        → final answer complete
    "error"             → something blew up {message}
    "iteration_limit"   → gave up after N tool rounds
"""

from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from app.agent.kitt import (
    KITT_SYSTEM_TEMPLATE,
    build_system_prompt,
    is_retry_safe,
    is_transient_error,
    parse_plan,
    recovery_hint,
)
from app.agent.loop_freak import (
    LoopFreakConfig,
    build_loop_freak_prompt,
    continue_nudge as loop_freak_continue_nudge,
)
from app.models.contract import ModelAdapter, ModelInput
from app.runtime.danger import classify_danger
from app.runtime.tool_executor import ToolExecutor, ToolResult, ToolResultStatus

logger = logging.getLogger(__name__)

Event = Callable[[str, dict], None]


TOOL_CALL_JSON_RE = re.compile(
    r"```(?:json|tool|tool_call)?\s*(\{[\s\S]*?\})\s*```",
    re.IGNORECASE,
)
TOOL_CALL_LINE_RE = re.compile(
    r"TOOL\s*:\s*([\w]+)\.([\w]+)\s*\(([^)]*)\)",
    re.IGNORECASE,
)
# Captures the inner body of a fenced code block whether it's an object or a
# JSON array of tool calls.
FENCE_BLOCK_RE = re.compile(
    r"```(?:json|tool|tool_call)?\s*([\[{][\s\S]*?[\]}])\s*```",
    re.IGNORECASE,
)


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str


@dataclass
class AgentTurn:
    prompt: str
    session_id: str = ""
    max_iterations: int = 12
    max_tokens: int = 2048
    temperature: float = 0.5
    history: list[ChatMessage] = field(default_factory=list)
    # Resilience: how many extra attempts a *retry-safe* (read/recon) tool call
    # gets after a transient error, and the base backoff between attempts.
    max_tool_retries: int = 2
    retry_backoff_s: float = 0.5
    # Persona: "kitt" (default) or "loop_freak" for aggressive loop mode.
    persona: str = "kitt"


# The agent persona and tool manual now live in app/agent/kitt.py — the loop is
# a thin driver over KITT. Kept as a module-level alias for back-compat with any
# caller that imported the old template name.
SYSTEM_PROMPT_TEMPLATE = KITT_SYSTEM_TEMPLATE


class AgentChatLoop:
    """Streaming tool-using chat loop backed by a ModelAdapter + ToolExecutor."""

    # First non-whitespace chars that mean "this is a tool call, buffer silently".
    _TOOL_CALL_PREFIXES = ("```", "{", "[")
    # How many peeked chars we need before we commit to prose-vs-tool-call.
    _PEEK_CHARS = 4
    # Max parallel tool workers per turn.
    _TOOL_POOL_SIZE = 8

    def __init__(
        self,
        model: ModelAdapter,
        tools: ToolExecutor,
        *,
        stream_model: Optional[ModelAdapter] = None,
        system_prompt: Optional[str] = None,
    ) -> None:
        self.model = model
        self.tools = tools
        self.stream_model = stream_model or model
        # Default persona is KITT (built from the live tool set). Pass an
        # explicit system_prompt to override it entirely.
        self._system_prompt_override = system_prompt

    def run(
        self,
        turn: AgentTurn,
        on_event: Event,
        confirm: Optional[Callable[[dict], bool]] = None,
    ) -> tuple[str, list[ToolResult]]:
        """Execute the loop. Returns (final_text, tool_results).

        `confirm`, when provided, is called for catastrophic tool calls with
        {tool, operation, params, reason}; returning False skips the call.
        """
        lf_cfg = LoopFreakConfig()
        is_loop_freak = turn.persona == "loop_freak"
        if is_loop_freak:
            if turn.max_iterations == 12:
                turn.max_iterations = lf_cfg.max_iterations
            if turn.max_tool_retries == 2:
                turn.max_tool_retries = lf_cfg.max_tool_retries

        if self._system_prompt_override:
            system_prompt = self._system_prompt_override
        elif is_loop_freak:
            system_prompt = build_loop_freak_prompt(self.tools)
        else:
            system_prompt = build_system_prompt(self.tools)

        continue_msg = (
            loop_freak_continue_nudge(lf_cfg)
            if is_loop_freak
            else "Continue: call more tools OR give the user the final answer."
        )

        conversation: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for msg in turn.history:
            conversation.append({"role": msg.role, "content": msg.content})
        conversation.append({"role": "user", "content": turn.prompt})

        tool_results: list[ToolResult] = []
        last_plan: Optional[list[str]] = None

        for iteration in range(turn.max_iterations):
            on_event("thinking", {"iteration": iteration})
            try:
                assistant_text, streamed_to_ui = self._stream_iteration(
                    conversation, turn, on_event,
                )
            except Exception as exc:
                logger.warning("Agent loop model call failed: %s", exc)
                on_event("error", {"message": str(exc)})
                return f"[model error: {exc}]", tool_results

            assistant_text = assistant_text.strip()
            conversation.append({"role": "assistant", "content": assistant_text})

            calls = _parse_tool_calls(assistant_text)
            if not calls:
                # A buffered (non-streamed) turn might be a multi-step plan
                # rather than a final answer. Surface it and drive execution.
                plan = parse_plan(assistant_text) if not streamed_to_ui else None
                if plan is not None:
                    if plan != last_plan:
                        last_plan = plan
                        on_event("plan", {"steps": plan})
                    conversation.append({
                        "role": "user",
                        "content": (
                            f"Plan noted ({len(plan)} steps). Now EXECUTE — emit the tool "
                            "call for the next step, or give the final answer if you're done. "
                            "Do not repeat the plan."
                        ),
                    })
                    continue

                # No tool call — this iteration IS the final answer.
                if streamed_to_ui:
                    on_event("final_done", {})
                else:
                    # We buffered because the peek looked tool-shaped, but the
                    # parser disagreed (e.g. bare JSON that isn't a tool call,
                    # or an empty response). Emit as final answer now.
                    on_event("final_start", {})
                    if assistant_text:
                        on_event("final_token", {"token": assistant_text})
                    on_event("final_done", {})
                return assistant_text, tool_results

            # A tool call was in the stream, so we buffered silently. Execute
            # every tool the model asked for this turn (one or many). When
            # there are ≥2 approved calls we run them in parallel; danger
            # confirmations always run sequentially first.
            feedback_blocks = self._execute_tools(
                calls, turn, on_event, confirm, tool_results,
            )

            conversation.append({
                "role": "user",
                "content": (
                    "\n\n".join(feedback_blocks)
                    + f"\n\n{continue_msg}"
                ),
            })

        on_event("iteration_limit", {"iterations": turn.max_iterations})
        tail = conversation[-1]["content"] if conversation else "[no response]"
        return tail, tool_results

    def _stream_iteration(
        self,
        conversation: list[dict[str, str]],
        turn: AgentTurn,
        on_event: Event,
    ) -> tuple[str, bool]:
        """Stream one iteration from the model.

        Peeks the first non-whitespace bytes. If they start with a tool-call
        indicator (```, {, [) the whole stream is buffered silently and the
        caller parses it. Otherwise the tokens are flushed to the UI as they
        arrive so the first word appears while the model is still generating.

        Returns (full_text, streamed_to_ui).
        """
        collected: list[str] = []
        peek_buffer: list[str] = []
        # None = still deciding; True = streaming prose to UI; False = silent.
        streaming_to_ui: Optional[bool] = None

        for token in self.stream_model.stream(ModelInput(
            prompt="",
            system_prompt=conversation[0]["content"] if conversation else "",
            context=[],
            max_tokens=turn.max_tokens,
            temperature=turn.temperature,
            metadata={"chat_messages": conversation},
        )):
            if not token:
                continue
            collected.append(token)

            if streaming_to_ui is None:
                peek_buffer.append(token)
                stripped = "".join(peek_buffer).lstrip()
                if len(stripped) >= self._PEEK_CHARS:
                    if stripped.startswith(self._TOOL_CALL_PREFIXES):
                        streaming_to_ui = False
                    else:
                        streaming_to_ui = True
                        on_event("final_start", {})
                        on_event("final_token", {"token": "".join(peek_buffer)})
                        peek_buffer = []
            elif streaming_to_ui:
                on_event("final_token", {"token": token})

        full_text = "".join(collected)

        # Response was shorter than PEEK_CHARS — decide from the full text.
        if streaming_to_ui is None:
            stripped = full_text.lstrip()
            if stripped and not stripped.startswith(self._TOOL_CALL_PREFIXES):
                streaming_to_ui = True
                on_event("final_start", {})
                on_event("final_token", {"token": full_text})
            else:
                streaming_to_ui = False

        return full_text, streaming_to_ui

    def _execute_tools(
        self,
        calls: list[tuple[str, str, dict]],
        turn: AgentTurn,
        on_event: Event,
        confirm: Optional[Callable[[dict], bool]],
        tool_results: list[ToolResult],
    ) -> list[str]:
        """Run the tools this turn. Danger-confirmations serialize (safety),
        then all approved calls run in parallel via a thread pool. Feedback
        blocks are returned in the original call order so the model sees them
        in a stable sequence."""
        n = len(calls)
        feedback_blocks: list[Optional[str]] = [None] * n
        approved: list[tuple[int, str, str, dict]] = []

        # 1) Serialize danger checks — the confirm callback may block the loop
        #    thread waiting for the browser, and we don't want two dangerous
        #    prompts on screen at once.
        for idx, (tool, operation, params) in enumerate(calls):
            reason = classify_danger(tool, operation, params)
            if reason and confirm is not None:
                on_event("tool_call", {
                    "tool": tool, "operation": operation,
                    "params": params, "danger": reason,
                })
                ok = False
                try:
                    ok = bool(confirm({
                        "tool": tool, "operation": operation,
                        "params": params, "reason": reason,
                    }))
                except Exception as exc:
                    logger.warning("Confirm callback failed: %s", exc)
                if not ok:
                    declined = ToolResult(
                        tool=tool, operation=operation,
                        status=ToolResultStatus.ERROR,
                        error=f"declined by user (guarded: {reason})",
                        duration_ms=0,
                    )
                    tool_results.append(declined)
                    on_event("tool_result", {
                        "tool": tool, "operation": operation,
                        "status": "declined", "result_preview": "",
                        "error": declined.error,
                    })
                    feedback_blocks[idx] = (
                        f"Tool [{tool}.{operation}] was DECLINED by the user "
                        f"(guarded action: {reason}). Do not retry it; continue "
                        f"without it or tell the user it was cancelled."
                    )
                    continue
            approved.append((idx, tool, operation, params))

        # 2) Run approved calls. Single call: inline (cheaper than a pool).
        if len(approved) == 1:
            idx, tool, operation, params = approved[0]
            feedback_blocks[idx] = self._run_and_report(
                tool, operation, params, turn, on_event, tool_results,
            )
        elif approved:
            workers = min(len(approved), self._TOOL_POOL_SIZE)
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="meteor-tool") as pool:
                futures = {
                    pool.submit(
                        self._run_and_report,
                        tool, operation, params, turn, on_event, tool_results,
                    ): idx
                    for idx, tool, operation, params in approved
                }
                for fut in as_completed(futures):
                    idx = futures[fut]
                    try:
                        feedback_blocks[idx] = fut.result()
                    except Exception as exc:
                        logger.warning("Parallel tool call raised: %s", exc)
                        feedback_blocks[idx] = (
                            f"Tool call at position {idx} crashed: {exc!r}"
                        )

        return [b for b in feedback_blocks if b is not None]

    def _run_and_report(
        self,
        tool: str,
        operation: str,
        params: dict,
        turn: AgentTurn,
        on_event: Event,
        tool_results: list[ToolResult],
    ) -> str:
        """Execute one tool with resilient retries, emit call/result events,
        append the final result to tool_results, and return the feedback block
        for the model — with a recovery hint when the call ultimately failed."""
        on_event("tool_call", {"tool": tool, "operation": operation, "params": params})

        max_retries = max(0, getattr(turn, "max_tool_retries", 0))
        backoff = max(0.0, getattr(turn, "retry_backoff_s", 0.0))
        retry_safe = is_retry_safe(tool, operation)

        attempts = 0
        while True:
            result = self.tools.execute(
                tool=tool, operation=operation,
                params=params, session_id=turn.session_id,
            )
            attempts += 1
            transient = (
                result.status is ToolResultStatus.ERROR
                and is_transient_error(result.error)
            )
            # Retry only pure read/recon ops on a transient blip — never a
            # mutating or offensive op, whose retry could double-fire an effect.
            if (
                result.status is ToolResultStatus.OK
                or attempts > max_retries
                or not (retry_safe and transient)
            ):
                break
            on_event("tool_retry", {
                "tool": tool, "operation": operation,
                "attempt": attempts, "max": max_retries + 1,
                "error": result.error,
            })
            if backoff:
                time.sleep(backoff * attempts)

        tool_results.append(result)
        preview = _truncate(_stringify(result.result), 800)
        on_event("tool_result", {
            "tool": tool,
            "operation": operation,
            "status": result.status.value,
            "duration_ms": result.duration_ms,
            "result_preview": preview,
            "error": result.error,
            "attempts": attempts,
        })

        if result.status is ToolResultStatus.OK:
            return (
                f"Tool [{tool}.{operation}] returned status=ok\n"
                f"result:\n{preview}"
            )
        hint = recovery_hint(result.status.value, tool, operation, result.error, attempts)
        return (
            f"Tool [{tool}.{operation}] FAILED after {attempts} attempt(s) "
            f"(status={result.status.value})\n"
            f"error={result.error!r}\n"
            f"result:\n{preview}\n\n{hint}"
        )


def _parse_tool_calls(text: str) -> list[tuple[str, str, dict]]:
    """Extract every tool call the model requested this turn.

    Supports one call or many: a fenced block may contain a single tool-call
    object OR a JSON array of them, so the model can chain tools in one turn.
    Returns [] when the text is a plain-prose final answer.
    """
    calls: list[tuple[str, str, dict]] = []

    for match in FENCE_BLOCK_RE.finditer(text):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and _looks_like_tool_call(item):
                    calls.append(_normalize_tool_call(item))
        elif isinstance(data, dict) and _looks_like_tool_call(data):
            calls.append(_normalize_tool_call(data))
    if calls:
        return calls

    # Fall back to the single-call parser (bare JSON / array / TOOL: line).
    stripped = text.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            data = json.loads(stripped)
            for item in data:
                if isinstance(item, dict) and _looks_like_tool_call(item):
                    calls.append(_normalize_tool_call(item))
        except json.JSONDecodeError:
            pass
        if calls:
            return calls

    one = _parse_tool_call(text)
    return [one] if one else []


def _parse_tool_call(text: str) -> Optional[tuple[str, str, dict]]:
    """Extract a single tool call from the model's response."""
    for match in TOOL_CALL_JSON_RE.finditer(text):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and _looks_like_tool_call(data):
            return _normalize_tool_call(data)

    # Bare JSON without fence — either the entire text, or a leading object
    # followed by prose commentary (which small models often emit).
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and _looks_like_tool_call(data):
                return _normalize_tool_call(data)
        except json.JSONDecodeError:
            pass
        try:
            decoder = json.JSONDecoder()
            data, _ = decoder.raw_decode(stripped)
            if isinstance(data, dict) and _looks_like_tool_call(data):
                return _normalize_tool_call(data)
        except (json.JSONDecodeError, ValueError):
            pass

    line = TOOL_CALL_LINE_RE.search(text)
    if line:
        tool = line.group(1)
        operation = line.group(2)
        args_str = line.group(3)
        params: dict[str, Any] = {}
        for arg in args_str.split(","):
            arg = arg.strip()
            if "=" in arg:
                k, v = arg.split("=", 1)
                params[k.strip()] = v.strip().strip("'\"")
        return tool, operation, params

    return None


def _looks_like_tool_call(data: dict) -> bool:
    if "tool" in data and "operation" in data:
        return True
    # {"name": "tool.op", "arguments": {...}} shape.
    if "name" in data and isinstance(data.get("name"), str) and "." in data["name"]:
        return True
    # Small models sometimes fold operation into the tool key: {"tool": "process.list"}.
    if isinstance(data.get("tool"), str) and "." in data["tool"]:
        return True
    return False


def _normalize_tool_call(data: dict) -> tuple[str, str, dict]:
    if "tool" in data and "operation" in data:
        return (
            str(data["tool"]),
            str(data["operation"]),
            dict(data.get("params") or data.get("arguments") or {}),
        )
    if isinstance(data.get("tool"), str) and "." in data["tool"]:
        tool, _, operation = str(data["tool"]).partition(".")
        return tool, operation, dict(data.get("params") or data.get("arguments") or {})
    name = str(data["name"])
    tool, _, operation = name.partition(".")
    return tool, operation, dict(data.get("arguments") or data.get("params") or {})


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, default=str, indent=2)[:20_000]
    except (TypeError, ValueError):
        return str(value)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n… [truncated {len(text) - limit} chars]"



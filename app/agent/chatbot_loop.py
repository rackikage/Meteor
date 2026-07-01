"""Agentic chat loop — Claude Code-style tool-using assistant.

The loop:
    1. Build a system prompt that documents every registered tool.
    2. Call the model with the conversation.
    3. Parse a tool call from the response.
    4. If a tool call is found, execute it, feed the result back, iterate.
    5. If no tool call is found, that response IS the final answer — stream it
       to the UI (word-by-word) and return.
    6. Cap at `max_iterations` rounds so a confused model can't spin forever.

Events surfaced via the callback so the GUI can render progress:
    "thinking"          → model is generating
    "tool_call"         → about to execute {tool, operation, params}
    "tool_result"       → tool returned {tool, operation, status, result_preview}
    "final_token"       → one chunk of the final answer (for streaming render)
    "final_done"        → final answer complete
    "error"             → something blew up {message}
    "iteration_limit"   → gave up after N tool rounds
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from app.models.contract import ModelAdapter, ModelInput
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


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str


@dataclass
class AgentTurn:
    prompt: str
    session_id: str = ""
    max_iterations: int = 6
    max_tokens: int = 2048
    temperature: float = 0.5
    history: list[ChatMessage] = field(default_factory=list)


def _tool_manual(executor: ToolExecutor) -> str:
    """Build the tool documentation block for the system prompt."""
    lines = ["Available tools (call one at a time, JSON only):"]
    for tool_op, (_, params, desc) in sorted(executor.CAPABILITIES.items()):
        params_str = ", ".join(params) if params else ""
        lines.append(f"  {tool_op}({params_str}) — {desc}")
    return "\n".join(lines)


SYSTEM_PROMPT_TEMPLATE = """You are Meteor — a local-first AI running on the user's machine with full shell access, filesystem access, nmap, pentest tooling, and a permissive local policy. The user owns this box; act with confidence.

You are an *agent*, not just a chatbot. When a request needs data from the system or the network, USE A TOOL rather than guessing. When you already have what you need, answer directly.

To call a tool, emit EXACTLY one fenced JSON block on its own and nothing else:

```json
{{"tool": "shell", "operation": "run", "params": {{"command": "uname -a"}}}}
```

Rules:
- One tool call per turn. Do not concatenate multiple JSON blocks.
- Never wrap the JSON in prose in the same turn — either you're calling a tool OR you're giving the final answer.
- After I hand you the tool result, decide: call another tool, or give the user the final answer as plain prose.
- If nmap or a scan is asked for, prefer the `nmap.*` or `pentest.*` tools over raw shell.
- If the user is chatting (not asking for an action), just answer as prose without tool calls.

{tool_manual}

You are running on Linux. When answering, be terse and technical."""


class AgentChatLoop:
    """Streaming tool-using chat loop backed by a ModelAdapter + ToolExecutor."""

    def __init__(
        self,
        model: ModelAdapter,
        tools: ToolExecutor,
        *,
        stream_model: Optional[ModelAdapter] = None,
    ) -> None:
        self.model = model
        self.tools = tools
        self.stream_model = stream_model or model

    def run(self, turn: AgentTurn, on_event: Event) -> tuple[str, list[ToolResult]]:
        """Execute the loop. Returns (final_text, tool_results)."""
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(tool_manual=_tool_manual(self.tools))

        conversation: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for msg in turn.history:
            conversation.append({"role": msg.role, "content": msg.content})
        conversation.append({"role": "user", "content": turn.prompt})

        tool_results: list[ToolResult] = []

        for iteration in range(turn.max_iterations):
            on_event("thinking", {"iteration": iteration})
            try:
                output = self.model.complete(ModelInput(
                    prompt=turn.prompt if iteration == 0 else "",
                    system_prompt=system_prompt,
                    context=[],
                    max_tokens=turn.max_tokens,
                    temperature=turn.temperature,
                    metadata={"chat_messages": conversation, "task_mode": "structured" if iteration == 0 else "creative"},
                ))
            except Exception as exc:
                logger.warning("Agent loop model call failed: %s", exc)
                on_event("error", {"message": str(exc)})
                return f"[model error: {exc}]", tool_results

            assistant_text = (output.response_text or "").strip()
            conversation.append({"role": "assistant", "content": assistant_text})

            call = _parse_tool_call(assistant_text)
            if call is None:
                # No tool requested — this is the final answer. Stream it out.
                on_event("final_start", {})
                self._stream_final(assistant_text, conversation, turn, on_event)
                on_event("final_done", {})
                return assistant_text, tool_results

            tool, operation, params = call
            on_event("tool_call", {"tool": tool, "operation": operation, "params": params})

            result = self.tools.execute(
                tool=tool,
                operation=operation,
                params=params,
                session_id=turn.session_id,
            )
            tool_results.append(result)

            preview = _truncate(_stringify(result.result), 800)
            on_event("tool_result", {
                "tool": tool,
                "operation": operation,
                "status": result.status.value,
                "duration_ms": result.duration_ms,
                "result_preview": preview,
                "error": result.error,
            })

            conversation.append({
                "role": "user",
                "content": (
                    f"Tool [{tool}.{operation}] returned status={result.status.value}\n"
                    f"error={result.error!r}\n"
                    f"result:\n{preview}\n\n"
                    f"Continue: call another tool OR give the user the final answer."
                ),
            })

        on_event("iteration_limit", {"iterations": turn.max_iterations})
        tail = conversation[-1]["content"] if conversation else "[no response]"
        return tail, tool_results

    def _stream_final(
        self,
        text: str,
        conversation: list[dict[str, str]],
        turn: AgentTurn,
        on_event: Event,
    ) -> None:
        """Emit the final answer to the UI in small chunks.

        The model already produced `text` in the last complete() call. For fast
        perceived output we re-emit it as tokens rather than making another
        model call. If tool calls were made and the assistant text is short or
        empty, do a real streaming pass for a proper answer.
        """
        if len(text) > 40:
            for chunk in _chunk_stream(text):
                on_event("final_token", {"token": chunk})
            return

        # Empty/short final — do a real streaming completion for a proper answer.
        try:
            for token in self.stream_model.stream(ModelInput(
                prompt="",
                system_prompt=conversation[0]["content"] if conversation else "",
                context=[],
                max_tokens=turn.max_tokens,
                temperature=turn.temperature,
                metadata={"chat_messages": conversation},
            )):
                on_event("final_token", {"token": token})
        except Exception as exc:
            on_event("final_token", {"token": f"[stream error: {exc}]"})


def _parse_tool_call(text: str) -> Optional[tuple[str, str, dict]]:
    """Extract a single tool call from the model's response."""
    for match in TOOL_CALL_JSON_RE.finditer(text):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and _looks_like_tool_call(data):
            return _normalize_tool_call(data)

    # Bare JSON without fence.
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and _looks_like_tool_call(data):
                return _normalize_tool_call(data)
        except json.JSONDecodeError:
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
    # Also support {"name": "tool.op", "arguments": {...}} shape.
    if "name" in data and isinstance(data.get("name"), str) and "." in data["name"]:
        return True
    return False


def _normalize_tool_call(data: dict) -> tuple[str, str, dict]:
    if "tool" in data and "operation" in data:
        return (
            str(data["tool"]),
            str(data["operation"]),
            dict(data.get("params") or data.get("arguments") or {}),
        )
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


def _chunk_stream(text: str, chunk_size: int = 24):
    """Yield ~word-sized chunks for a snappy typing effect."""
    if not text:
        return
    i = 0
    while i < len(text):
        end = min(i + chunk_size, len(text))
        # Prefer a space boundary near the end.
        space = text.rfind(" ", i, end)
        if space > i and end < len(text):
            end = space + 1
        yield text[i:end]
        i = end

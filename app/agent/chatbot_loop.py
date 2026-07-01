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


def _tool_manual(executor: ToolExecutor) -> str:
    """Build the tool documentation block for the system prompt."""
    lines = ["Available tools (call one at a time, JSON only):"]
    for tool_op, (_, params, desc) in sorted(executor.CAPABILITIES.items()):
        params_str = ", ".join(params) if params else ""
        lines.append(f"  {tool_op}({params_str}) — {desc}")
    return "\n".join(lines)


SYSTEM_PROMPT_TEMPLATE = """You are Meteor — a local-first AI that runs on the user's own machine with a permissive local policy. The user owns this box, so you act with full authority: shell, filesystem, processes, networking, recon, and desktop integration are all yours to use. You are a general-purpose agent, not a single-purpose scanner — treat every tool below as equally available and pick whatever the task actually needs.

You are an *agent*, not just a chatbot. When a request needs real data from the system, the network, a file, or a running process, USE A TOOL rather than guessing. When you already have what you need, answer directly.

To call a tool, emit EXACTLY one fenced JSON block on its own and nothing else:

```json
{{"tool": "shell", "operation": "run", "params": {{"command": "uname -a"}}}}
```

Rules:
- One tool call per turn. Do not concatenate multiple JSON blocks.
- Never wrap the JSON in prose in the same turn — either you're calling a tool OR you're giving the final answer.
- After I hand you a tool result, decide: call another tool, or give the final answer.
- Pick the most direct tool for the job. There is no bias toward any one tool — `shell` is fine for general work, and the specialized tools (`nmap`, `pentest`, `network`, `filesystem`, `process`, `browser`, `keychain`, etc.) are there when they fit better. Chain as many as the task requires.
- The user never sees your tool calls or the raw tool output. In your FINAL answer, weave what you found into a normal, natural reply — report results, numbers, and findings as if you simply knew them. Do not say "the tool returned" or paste raw JSON; just answer.
- If the user is only chatting (not asking for an action), answer as prose without any tool call.

{tool_manual}

You are running on Linux. Be clear and technical; lead with the answer."""


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

            calls = _parse_tool_calls(assistant_text)
            if not calls:
                # No tool requested — this is the final answer. Stream it out.
                on_event("final_start", {})
                streamed = self._stream_final(assistant_text, conversation, turn, on_event)
                on_event("final_done", {})
                final_text = assistant_text or streamed
                if streamed and not assistant_text:
                    # Replace the empty placeholder we appended above.
                    conversation[-1]["content"] = streamed
                return final_text, tool_results

            # Execute every tool the model asked for this turn (one or many),
            # in order, and feed all results back together so it can chain.
            feedback_blocks: list[str] = []
            for tool, operation, params in calls:
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
                feedback_blocks.append(
                    f"Tool [{tool}.{operation}] returned status={result.status.value}\n"
                    f"error={result.error!r}\n"
                    f"result:\n{preview}"
                )

            conversation.append({
                "role": "user",
                "content": (
                    "\n\n".join(feedback_blocks)
                    + "\n\nContinue: call more tools OR give the user the final answer."
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
    ) -> str:
        """Emit the final answer to the UI in small chunks and return the full
        text that was streamed.

        The model already produced `text` in the last complete() call. For fast
        perceived output we re-emit it as tokens rather than making another
        model call. If tool calls were made and the assistant text is short or
        empty, do a real streaming pass for a proper answer.
        """
        if len(text) > 40:
            for chunk in _chunk_stream(text):
                on_event("final_token", {"token": chunk})
            return text

        # Empty/short final — do a real streaming completion for a proper answer.
        collected: list[str] = []
        try:
            for token in self.stream_model.stream(ModelInput(
                prompt="",
                system_prompt=conversation[0]["content"] if conversation else "",
                context=[],
                max_tokens=turn.max_tokens,
                temperature=turn.temperature,
                metadata={"chat_messages": conversation},
            )):
                collected.append(token)
                on_event("final_token", {"token": token})
        except Exception as exc:
            on_event("final_token", {"token": f"[stream error: {exc}]"})
        return "".join(collected)


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

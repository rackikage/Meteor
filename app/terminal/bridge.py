"""Terminal bridge — lightweight runtime for interactive terminal sessions.

Builds just enough of the Meteor runtime to drive ``AgentChatLoop`` in a
terminal: config, storage, model registry, tool executor.  Skips FastAPI, the
web GUI, the orchestrator, and the full ``MeteorRuntime`` — this is a thin
path from keyboard to model to tools and back.

Also supports **manual mode** — direct tool invocation without the AI model,
for power users who want to call tools themselves.
"""

from __future__ import annotations

import json
import logging
import shlex
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.agent.chatbot_loop import AgentChatLoop, AgentTurn, ChatMessage
from app.terminal.renderer import TerminalRenderer

logger = logging.getLogger(__name__)

_MAX_HISTORY = 20


@dataclass
class TerminalConfig:
    persona: str = "kitt"
    session_id: str = "terminal"
    max_iterations: int = 12
    max_tokens: int = 2048
    temperature: float = 0.5
    plain: bool = False
    model_profile: Optional[str] = None


class TerminalBridge:
    """Owns the lightweight runtime + agent loop for a terminal session."""

    def __init__(self, config: Optional[TerminalConfig] = None) -> None:
        self.config = config or TerminalConfig()
        self._renderer = TerminalRenderer(plain=self.config.plain)
        self._history: list[ChatMessage] = []
        self._loop: Optional[AgentChatLoop] = None
        self._model_registry = None
        self._tool_executor = None
        self._model_name = "unknown"
        self._tool_count = 0
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return

        from app.bootstrap import bootstrap
        from app.models.registry import build_model_registry
        from app.runtime.tool_executor import ToolExecutor
        from app.storage.sqlite_adapter import build_sqlite_adapter
        from app.tools.bootstrap import bootstrap_tools
        from app.runtime.asset_context import set_asset_context

        result = bootstrap()
        storage = build_sqlite_adapter(result.config.storage, result.repo_root)
        self._model_registry = build_model_registry(result.config, result.repo_root)

        bootstrap_tools(storage=storage)
        self._tool_executor = ToolExecutor()
        self._tool_count = len(ToolExecutor.CAPABILITIES)

        profile_name = self.config.model_profile
        model = self._model_registry.get_adapter(profile_name)
        if profile_name is None:
            profile_name = self._model_registry._effective_default_profile()
        profile = self._model_registry.config.models.profiles.get(profile_name)
        self._model_name = profile.model_path if profile else profile_name

        self._loop = AgentChatLoop(model=model, tools=self._tool_executor)
        self._initialized = True

        self._renderer.print_banner(
            persona=self.config.persona.upper(),
            tool_count=self._tool_count,
            model=self._model_name,
        )

    def run_turn(self, prompt: str) -> str:
        if not self._initialized:
            self.initialize()

        persona = self.config.persona
        max_iter = self.config.max_iterations
        if persona == "loop_freak" and max_iter == 12:
            max_iter = 25

        turn = AgentTurn(
            prompt=prompt,
            session_id=self.config.session_id,
            history=list(self._history)[-12:],
            max_iterations=max_iter,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            persona=persona,
        )

        final_text, _ = self._loop.run(turn, self._renderer.on_event)

        self._history.append(ChatMessage(role="user", content=prompt))
        self._history.append(ChatMessage(role="assistant", content=final_text))
        self._history = self._history[-_MAX_HISTORY:]

        return final_text

    def switch_persona(self, persona: str) -> str:
        valid = ("kitt", "loop_freak")
        if persona not in valid:
            return f"Unknown persona: {persona}. Valid: {', '.join(valid)}"
        self.config.persona = persona
        return f"Switched to {persona.upper()}"

    def switch_model(self, profile: Optional[str] = None) -> str:
        if not self._initialized:
            self.initialize()

        if profile is None:
            profiles = self._model_registry.list_profiles()
            current = self._model_registry._effective_default_profile()
            lines = [f"  {'*' if p == current else ' '} {p}" for p in profiles]
            return f"Model profiles:\n" + "\n".join(lines)

        try:
            model = self._model_registry.get_adapter(profile)
        except (ValueError, KeyError) as exc:
            return f"Unknown profile: {profile} ({exc})"

        self._loop.model = model
        self._loop.stream_model = model
        prof = self._model_registry.config.models.profiles.get(profile)
        self._model_name = prof.model_path if prof else profile
        return f"Switched to {profile} ({self._model_name})"

    def list_tools(self) -> str:
        if not self._initialized:
            self.initialize()
        from app.runtime.tool_executor import ToolExecutor
        groups: dict[str, list[str]] = {}
        for tool_op in sorted(ToolExecutor.CAPABILITIES):
            tool = tool_op.split(".", 1)[0]
            groups.setdefault(tool, []).append(tool_op)
        lines = []
        for tool in sorted(groups):
            lines.append(f"  [{tool}]")
            for op in groups[tool]:
                lines.append(f"    {op}")
        return f"{len(ToolExecutor.CAPABILITIES)} tools:\n" + "\n".join(lines)

    def clear_history(self) -> str:
        self._history.clear()
        return "Session history cleared."

    def get_history(self) -> str:
        if not self._history:
            return "No history yet."
        lines = []
        for msg in self._history[-20:]:
            role = msg.role.upper()
            preview = msg.content[:200]
            lines.append(f"  [{role}] {preview}")
        return "\n".join(lines)

    @property
    def renderer(self) -> TerminalRenderer:
        return self._renderer

    @property
    def model_registry(self):
        return self._model_registry

    def run_tool_direct(self, tool_op: str, params: dict) -> str:
        """Execute a tool directly without the AI model. Returns formatted result."""
        if not self._initialized:
            self.initialize()

        if "." not in tool_op:
            return f"Invalid tool format: {tool_op}. Use tool.operation (e.g., shell.run)"

        tool, operation = tool_op.split(".", 1)

        from app.runtime.tool_executor import ToolResultStatus
        result = self._tool_executor.execute(
            tool=tool,
            operation=operation,
            params=params,
            session_id=self.config.session_id,
        )

        lines = [f"Tool: {tool}.{operation}"]
        lines.append(f"Status: {result.status.value}")
        lines.append(f"Duration: {result.duration_ms:.0f}ms")

        if result.error:
            lines.append(f"Error: {result.error}")

        if result.result:
            try:
                formatted = json.dumps(result.result, indent=2, default=str)
                lines.append(f"Result:\n{formatted}")
            except (TypeError, ValueError):
                lines.append(f"Result: {result.result}")

        return "\n".join(lines)

    def inspect_tool(self, tool_op: str) -> str:
        """Show schema and metadata for a tool operation."""
        if not self._initialized:
            self.initialize()

        from app.runtime.tool_executor import ToolExecutor, CAPABILITY_SCHEMAS

        if tool_op not in ToolExecutor.CAPABILITIES:
            return f"Unknown tool: {tool_op}"

        method, required, desc = ToolExecutor.CAPABILITIES[tool_op]
        schema = CAPABILITY_SCHEMAS.get(tool_op, {})

        lines = [
            f"Tool: {tool_op}",
            f"Method: {method}",
            f"Description: {desc}",
            f"Required params: {', '.join(required) if required else 'none'}",
        ]

        if schema and "properties" in schema:
            lines.append("\nParameters:")
            for param, spec in schema["properties"].items():
                ptype = spec.get("type", "any")
                pdesc = spec.get("description", "")
                req = " (required)" if param in required else ""
                lines.append(f"  {param}: {ptype}{req} — {pdesc}")

        return "\n".join(lines)

    def run_batch(self, commands: list[tuple[str, dict]]) -> str:
        """Execute multiple tools in sequence. Returns combined results."""
        if not self._initialized:
            self.initialize()

        results = []
        for i, (tool_op, params) in enumerate(commands, 1):
            results.append(f"\n=== Command {i}: {tool_op} ===")
            results.append(self.run_tool_direct(tool_op, params))

        return "\n".join(results)

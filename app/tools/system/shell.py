"""Shell Execution Sandbox — run bash/zsh commands with safety controls."""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


class ShellError(Exception):
    def __init__(self, returncode: int, stdout: str, stderr: str, cmd: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.cmd = cmd
        super().__init__(f"Command exited {returncode}: {cmd[:120]}")


@dataclass
class ShellResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    cancelled: bool = False

    @property
    def success(self) -> bool:
        return self.returncode == 0 and not self.timed_out


@dataclass
class ShellConfig:
    default_timeout_s: float = 60.0
    max_timeout_s: float = 3600.0
    max_output_bytes: int = 10 * 1024 * 1024
    allowed_commands: Optional[list[str]] = None
    blocked_commands: list[str] = field(default_factory=lambda: ["sudo", "su", "passwd", "reboot", "shutdown", "halt"])
    work_dir: str = "."


class ShellSandbox:
    def __init__(self, config: Optional[ShellConfig] = None) -> None:
        self.config = config or ShellConfig()
        self._history: list[ShellResult] = []

    async def run(self, command: str, timeout: Optional[float] = None, work_dir: Optional[str] = None, env: Optional[dict] = None, check: bool = False) -> ShellResult:
        cmd = command.strip()
        self._validate_command(cmd)
        effective_timeout = min(timeout or self.config.default_timeout_s, self.config.max_timeout_s)
        start = time.monotonic()

        args = shlex.split(cmd)
        needs_shell = any(token in cmd for token in ["|", ">", "<", ">>", "2>&1", "&&", "||", ";", "$(", "`"])

        try:
            if needs_shell:
                proc = await asyncio.create_subprocess_shell(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=work_dir or self.config.work_dir, env=self._build_env(env), executable="/bin/bash")
            else:
                proc = await asyncio.create_subprocess_exec(*args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=work_dir or self.config.work_dir, env=self._build_env(env))

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=effective_timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                elapsed = (time.monotonic() - start) * 1000
                result = ShellResult(command=cmd, returncode=-1, stdout="", stderr=f"Timed out after {effective_timeout}s", duration_ms=elapsed, timed_out=True)
                self._history.append(result)
                return result
        except asyncio.CancelledError:
            elapsed = (time.monotonic() - start) * 1000
            result = ShellResult(command=cmd, returncode=-2, stdout="", stderr="Cancelled", duration_ms=elapsed, cancelled=True)
            self._history.append(result)
            return result

        elapsed = (time.monotonic() - start) * 1000
        stdout = stdout_bytes.decode("utf-8", errors="replace")[:self.config.max_output_bytes] if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8", errors="replace")[:self.config.max_output_bytes] if stderr_bytes else ""
        result = ShellResult(command=cmd, returncode=proc.returncode or 0, stdout=stdout, stderr=stderr, duration_ms=elapsed)
        self._history.append(result)
        if check and not result.success:
            raise ShellError(result.returncode, result.stdout, result.stderr, cmd)
        return result

    def run_sync(self, command: str, timeout: Optional[float] = None, work_dir: Optional[str] = None) -> ShellResult:
        self._validate_command(command)
        effective_timeout = timeout or self.config.default_timeout_s
        start = time.monotonic()
        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=effective_timeout, cwd=work_dir or self.config.work_dir, env=self._build_env(None), executable="/bin/bash")
            elapsed = (time.monotonic() - start) * 1000
            result = ShellResult(command=command, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr, duration_ms=elapsed)
        except subprocess.TimeoutExpired:
            elapsed = (time.monotonic() - start) * 1000
            result = ShellResult(command=command, returncode=-1, stdout="", stderr=f"Timed out after {effective_timeout}s", duration_ms=elapsed, timed_out=True)
        self._history.append(result)
        return result

    def _validate_command(self, command: str) -> None:
        if not command.strip():
            raise ValueError("Empty command")
        first_word = shlex.split(command)[0]
        base = os.path.basename(first_word)
        for blocked in self.config.blocked_commands:
            if base == blocked or first_word == blocked:
                raise PermissionError(f"Command '{base}' is blocked")
        if self.config.allowed_commands is not None and base not in self.config.allowed_commands:
            raise PermissionError(f"Command '{base}' not in allowed list")

    def _build_env(self, extra_env: Optional[dict]) -> dict:
        env = os.environ.copy()
        env.pop("LD_PRELOAD", None)
        env.pop("LD_LIBRARY_PATH", None)
        env["SHELL"] = "/bin/bash"
        env["PAGER"] = "cat"
        if extra_env:
            env.update(extra_env)
        return env

    def get_history(self, limit: int = 20) -> list[dict]:
        return [{"command": r.command[:200], "returncode": r.returncode, "duration_ms": r.duration_ms, "success": r.success, "timed_out": r.timed_out, "stdout_preview": r.stdout[:200]} for r in self._history[-limit:]]

    def clear_history(self) -> None:
        self._history.clear()

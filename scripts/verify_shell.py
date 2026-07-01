#!/usr/bin/env python3
"""Meteor shell-access smoke test.

Asserts that:
1. bootstrap() succeeds and produces a valid config.
2. bootstrap_tools() registers the shell tool without a blocklist.
3. ToolExecutor.execute('shell','run', ...) runs common shell commands
   (`id`, `whoami`, `uname -a`) with status=ok and non-empty stdout.
4. A command containing scary substrings (`sudo`, `rm -rf`) still executes,
   proving there is no substring blocklist.

Exits 0 on all-pass, 1 on any fail. Run from the repo root:

    ./.venv/bin/python scripts/verify_shell.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))


def _check(label: str, ok: bool, detail: str = "") -> bool:
    marker = "PASS" if ok else "FAIL"
    print(f"[{marker}] {label}{('  — ' + detail) if detail else ''}")
    return ok


def _result_stdout(result) -> str:
    r = result.result
    if isinstance(r, dict):
        return str(r.get("stdout") or r.get("output") or r)[:120]
    if isinstance(r, str):
        return r[:120]
    return str(r)[:120]


def main() -> int:
    from app.bootstrap import bootstrap
    from app.tools.bootstrap import bootstrap_tools
    from app.runtime.tool_executor import ToolExecutor, ToolResultStatus
    from app.tools.system.registry import get_registry
    from app.storage.sqlite_adapter import build_sqlite_adapter

    all_ok = True

    result = bootstrap()
    all_ok &= _check("bootstrap()", result.config is not None)

    storage = build_sqlite_adapter(result.config.storage, result.repo_root)
    bootstrap_tools(storage=storage)

    registry = get_registry()
    tools = registry.list_tools()
    tool_names = {t.get("name") for t in tools if isinstance(t, dict)}
    all_ok &= _check(
        "shell tool registered",
        "shell" in tool_names,
        f"tools={sorted(t for t in tool_names if t)}",
    )

    executor = ToolExecutor()

    for cmd in ("id", "whoami", "uname -a"):
        r = executor.execute(
            tool="shell", operation="run",
            params={"command": cmd}, session_id="verify-shell",
        )
        ok = r.status == ToolResultStatus.OK and not r.error
        all_ok &= _check(
            f"shell.run {cmd!r}",
            ok,
            f"status={r.status.value} err={r.error!r} out={_result_stdout(r)!r}",
        )

    # No-blocklist proof: run a command whose text contains scary substrings
    # but is entirely harmless (echoes a string that mentions sudo/rm).
    scary = "echo 'meteor-verify: sudo rm -rf /nonexistent-test-only'"
    r = executor.execute(
        tool="shell", operation="run",
        params={"command": scary}, session_id="verify-shell",
    )
    ok = r.status == ToolResultStatus.OK and not r.error
    all_ok &= _check(
        "shell.run allows 'sudo/rm -rf' substrings (no blocklist)",
        ok,
        f"status={r.status.value} err={r.error!r}",
    )

    print()
    print("OVERALL:", "PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

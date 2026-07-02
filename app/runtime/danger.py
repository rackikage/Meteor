"""Danger classifier — flags the handful of *super serious* operations that
deserve a quick confirm before Meteor runs them.

Philosophy: full shell access stays frictionless. This is NOT a security
sandbox and NOT an allow/deny policy — the user owns the box. It only catches
the small set of irreversible, machine-wrecking actions (wipe the disk, fork
bomb, power off, recursively delete the filesystem, pipe the internet into a
shell) so a confused model can't nuke the box without one click of consent.

`classify_danger(tool, operation, params)` returns a short human reason string
when the action is catastrophic, or None when it's fine to just run.
"""

from __future__ import annotations

import re
from typing import Optional

# Each pattern is (compiled regex, human reason). Matched against the shell
# command string, case-insensitive.
_SHELL_DANGER: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\brm\s+(?:-\w*\s+)*-\w*[rf]\w*\b.*(?:/\s*$|/\s|\s/\b|~|\*|\$HOME|/etc|/usr|/var|/boot|/bin|/lib)"),
     "recursive force-delete of a broad or system path"),
    (re.compile(r"\brm\s+-[rf]{1,2}\s+/\s*$"), "delete the entire filesystem root"),
    (re.compile(r"\bmkfs(\.\w+)?\b"), "format a filesystem"),
    (re.compile(r"\bwipefs\b"), "wipe filesystem signatures"),
    (re.compile(r"\bshred\b"), "irreversibly shred data"),
    (re.compile(r"\bdd\b.*\bof=/dev/(sd|nvme|mmcblk|vd|hd)"), "raw write to a block device"),
    (re.compile(r">\s*/dev/(sd|nvme|mmcblk|vd|hd)"), "overwrite a raw block device"),
    (re.compile(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"), "fork bomb"),
    (re.compile(r"\b(shutdown|reboot|poweroff|halt)\b"), "power off / reboot the machine"),
    (re.compile(r"\binit\s+[06]\b"), "change runlevel (shutdown/reboot)"),
    (re.compile(r"\bsystemctl\s+(poweroff|reboot|halt)\b"), "power off / reboot via systemd"),
    (re.compile(r"\bchmod\s+(-\w*\s+)*-R\s+0*\s*/"), "recursive chmod on a root path"),
    (re.compile(r"\bchown\s+(-\w*\s+)*-R\b.*\s/(?:\s|$)"), "recursive chown on the filesystem root"),
    (re.compile(r"\b(userdel|deluser)\b"), "delete a user account"),
    (re.compile(r"\bcrontab\s+-r\b"), "wipe all cron jobs"),
    (re.compile(r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba)?sh\b"), "pipe a remote script straight into a shell"),
    (re.compile(r"\biptables\s+-F\b|\bufw\s+disable\b|\bnft\s+flush\b"), "flush firewall rules"),
    (re.compile(r"\bkill\s+-9\s+-1\b|\bkill\s+-KILL\s+-1\b"), "kill every process"),
    (re.compile(r"\b(mkswap|swapoff\s+-a)\b"), "reconfigure swap"),
    (re.compile(r"\bgit\s+.*\bpush\b.*(--force\b|-f\b).*\bmain\b"), "force-push over main"),
    (re.compile(r"\b>\s*/dev/null.*&&.*\brm\b"), "chained destructive redirect + delete"),
]

# Filesystem paths that must never be recursively removed without a nod.
_PROTECTED_PREFIXES = ("/", "/etc", "/usr", "/var", "/boot", "/bin", "/sbin",
                       "/lib", "/lib64", "/home", "/root", "/opt", "/dev", "/sys", "/proc")


def classify_danger(tool: str, operation: str, params: dict) -> Optional[str]:
    """Return a short reason if this action is catastrophic, else None."""
    tool = (tool or "").lower()
    operation = (operation or "").lower()
    params = params or {}

    if tool == "shell":
        cmd = str(params.get("command", ""))
        for pattern, reason in _SHELL_DANGER:
            if pattern.search(cmd):
                return reason
        return None

    if tool == "filesystem" and operation in ("remove", "move"):
        path = str(params.get("path") or params.get("src") or "").rstrip("/")
        if path in _PROTECTED_PREFIXES or path == "":
            return f"{operation} a protected system path ({path or '/'})"
        return None

    # Recursive tree deletion is always worth a nod — one call can wipe a lot.
    if tool == "filesystem" and operation == "remove_tree":
        path = str(params.get("path") or "").rstrip("/")
        if path in _PROTECTED_PREFIXES or path == "":
            return f"recursively delete a protected system path ({path or '/'})"
        return "recursively delete a directory tree"

    if tool == "process" and operation == "kill":
        pid = str(params.get("pid", ""))
        if pid in ("1", "-1"):
            return "kill PID 1 / all processes"
        return None

    # arsenal.run executes an arbitrary installed binary with a raw arg string.
    # Reconstruct the effective command line and run it through the same shell
    # danger patterns so `arsenal.run(tool="rm", args="-rf /")` is caught exactly
    # like `shell.run("rm -rf /")`.
    if tool == "arsenal" and operation == "run":
        cmd = f"{params.get('tool', '')} {params.get('args', '')}".strip()
        for pattern, reason in _SHELL_DANGER:
            if pattern.search(cmd):
                return reason
        return None

    return None

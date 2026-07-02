"""MCP-only policy gates — env-driven scoping for the meteor-mcp server.

These gates live in the MCP projection layer, NOT in the shared tool registry or
the pure danger classifier, so the desktop app's permissive local doctrine
("your machine, your rules") is untouched. Everything here keys off
``METEOR_MCP_*`` environment variables read once at server start.

Default posture (no env set) — "offensive-gated":
    - local, read, and recon tools (filesystem reads, graph, web, nmap,
      arsenal.detect, local posture, network scope) work out of the box;
    - autonomous grinding (`grinder.*`), network weapons (`sqlmap`, `hydra`,
      `nuclei`, …), and the generic `arsenal.run` are REFUSED until an explicit
      target scope (``METEOR_MCP_ALLOWED_CIDR``) or ``METEOR_MCP_ALLOW_DANGER=1``
      is provided.

Env vars:
    METEOR_MCP_READ_ONLY=1        hide + refuse every mutating/active op
    METEOR_MCP_ALLOWED_CIDR=cidr  unlock offensive tools, scoped to this CIDR
    METEOR_MCP_ALLOWED_ROOT=/dir  (applied in server.py) chroot the fs tool
    METEOR_MCP_PROFILE=minimal    coarse filter: local/read only, no active net
    METEOR_MCP_ALLOW_DANGER=1     lift the catastrophic gate AND the offensive gate
"""

from __future__ import annotations

import ipaddress
import os
import socket
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from app.arsenal.weapons import WEAPON_TOOLS

# Weapons that hit a network target — the offensive surface. Local-file /
# offline weapons (exiftool, binwalk, searchsploit) are recon/forensic and are
# NOT gated. "arsenal" (detect/run) is handled explicitly below.
_LOCAL_WEAPONS = {"exiftool", "binwalk", "searchsploit"}
NETWORK_WEAPON_TOOLS = (set(WEAPON_TOOLS) - {"arsenal"}) - _LOCAL_WEAPONS

# Local filesystem mutations.
_FS_WRITE_OPS = {"write", "edit", "append", "mkdir", "remove", "remove_tree", "copy", "move"}

# Non-filesystem ops that change local state / execute code / send active traffic.
_MUTATING_OPS = {
    ("shell", "run"),
    ("process", "kill"),
    ("clipboard", "copy"),
    ("keychain", "store"), ("keychain", "delete"),
    ("scheduler", "add"), ("scheduler", "remove"),
    ("notify", "send"),
    ("browser", "fill"), ("browser", "click"), ("browser", "js"),
    ("pentest", "probe"),
}

# Param names that may carry a network target, in resolution priority order.
_TARGET_PARAMS = ("target", "cidr", "url", "host", "ip", "domain")


def is_offensive(tool: str, operation: str) -> bool:
    """True if the op sends offensive/scan traffic to a target and therefore
    needs an explicit scope before running unattended over MCP."""
    if tool == "grinder":
        return True
    if tool in NETWORK_WEAPON_TOOLS:
        return True
    if tool == "arsenal" and operation == "run":
        return True
    return False


def is_mutating(tool: str, operation: str) -> bool:
    """True if the op writes local state, executes code, or sends active network
    traffic — the set excluded under METEOR_MCP_READ_ONLY=1."""
    if tool == "filesystem" and operation in _FS_WRITE_OPS:
        return True
    if tool == "nmap":  # active port/host scanning
        return True
    if (tool, operation) in _MUTATING_OPS:
        return True
    return is_offensive(tool, operation)


def extract_target(params: dict) -> Optional[str]:
    """Pull a host / IP / CIDR out of a tool's params for scope checking, or
    None when there's nothing IP-scopable (local/file tools, domain-name tools)."""
    for key in _TARGET_PARAMS:
        val = params.get(key)
        if not val:
            continue
        val = str(val)
        if key == "url":
            return urlparse(val if "://" in val else "http://" + val).hostname
        if key == "domain":
            return None  # domain-name tools aren't IP-CIDR-scopable
        return val
    return None


def target_in_cidr(target: str, cidr: str) -> Optional[bool]:
    """True/False if `target` resolves inside `cidr`; None when it can't be
    resolved or the cidr is malformed (caller treats None as 'cannot verify')."""
    try:
        net = ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return None
    # target may itself be a CIDR/IP (grind_subnet, nmap.discover) …
    try:
        sub = ipaddress.ip_network(target, strict=False)
        return sub.subnet_of(net) if sub.version == net.version else False
    except ValueError:
        pass
    # … or a hostname needing DNS resolution.
    try:
        resolved = socket.gethostbyname(target)
        return ipaddress.ip_address(resolved) in net
    except Exception:
        return None


@dataclass
class McpPolicy:
    read_only: bool
    allow_danger: bool
    allowed_cidr: Optional[str]
    allowed_root: Optional[str]
    profile: str  # "full" (default) | "minimal" | "arsenal"

    @classmethod
    def from_env(cls, env: Optional[dict] = None) -> "McpPolicy":
        env = env if env is not None else os.environ

        def _truthy(name: str) -> bool:
            return str(env.get(name, "")).lower() in ("1", "true", "yes")

        return cls(
            read_only=_truthy("METEOR_MCP_READ_ONLY"),
            allow_danger=_truthy("METEOR_MCP_ALLOW_DANGER"),
            allowed_cidr=(env.get("METEOR_MCP_ALLOWED_CIDR") or None),
            allowed_root=(env.get("METEOR_MCP_ALLOWED_ROOT") or None),
            profile=(env.get("METEOR_MCP_PROFILE") or "full").lower(),
        )

    def _profile_hides(self, tool: str, operation: str) -> bool:
        return self.profile == "minimal" and (is_offensive(tool, operation) or tool == "nmap")

    def is_visible(self, tool: str, operation: str) -> bool:
        """Whether a capability should appear in list_tools()."""
        if self.read_only and is_mutating(tool, operation):
            return False
        if self._profile_hides(tool, operation):
            return False
        return True

    def gate(self, tool: str, operation: str, params: dict) -> Optional[str]:
        """Return a refusal reason for env-scoped policy, or None to allow. The
        catastrophic danger classifier is applied separately by the server."""
        if self.read_only and is_mutating(tool, operation):
            return f"'{tool}.{operation}' is disabled under METEOR_MCP_READ_ONLY=1"

        if self._profile_hides(tool, operation):
            return f"'{tool}.{operation}' is not in the 'minimal' MCP profile"

        if is_offensive(tool, operation) and self.allowed_cidr is None and not self.allow_danger:
            return (f"'{tool}.{operation}' is an offensive tool — set "
                    f"METEOR_MCP_ALLOWED_CIDR to a target scope (or "
                    f"METEOR_MCP_ALLOW_DANGER=1) to enable it")

        if self.allowed_cidr:
            target = extract_target(params)
            if target is not None and target_in_cidr(target, self.allowed_cidr) is False:
                return (f"target '{target}' is outside "
                        f"METEOR_MCP_ALLOWED_CIDR={self.allowed_cidr}")

        return None

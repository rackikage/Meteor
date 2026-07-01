"""Meteor arsenal — installed-tool detection + first-class weapon wrappers.

The user owns this box (a pentest distro). The arsenal layer turns the raw
shell into a *discoverable* weapon set: `arsenal.detect` reports which catalog
tools are actually installed (grouped by pipeline phase), `arsenal.run` executes
any of them with structured output, and the heavy hitters (sqlmap, nuclei,
hydra, …) get typed first-class wrappers. Everything registers into the same
tool registry the app and the MCP server read, so a capability added here is
instantly available to Meteor's own loop AND any external AI driving the MCP
server.
"""
from __future__ import annotations

from app.arsenal.weapons import (
    ARSENAL_CAPABILITIES,
    WEAPON_TOOLS,
    register_arsenal,
)

__all__ = ["ARSENAL_CAPABILITIES", "WEAPON_TOOLS", "register_arsenal"]

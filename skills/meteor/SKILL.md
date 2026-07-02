---
name: meteor
description: Drives Meteor's local MCP arsenal (75 tools) for filesystem, shell, nmap, pentest, graph, grinder, and weapon wrappers. Use when the user asks for Meteor, KITT, local recon, network scope, nmap, nuclei, sqlmap, hydra, arsenal detect/run, or mounting meteor-mcp in Cursor.
---

# Meteor MCP Arsenal

Meteor exposes a local stdio MCP server (`meteor-mcp`) projecting the full tool core. Tool names use `__` instead of `.` (e.g. `filesystem__read`, `grinder__grind_subnet`).

For fluid orchestration persona, also load the **kitt** skill.

## When to use

- Local recon, network scope, nmap, pentest posture
- Asset graph queries and autonomous grinding
- Installed security tool inventory and execution
- Full local shell/filesystem when Cursor built-ins are not enough
- User mentions Meteor, meteor-mcp, or KITT

## Workflow (fluid chain)

1. **Inventory:** `arsenal__detect`
2. **Scope:** `network__scope`
3. **Map:** `nmap__*` or `grinder__*` (offensive scope may require `METEOR_MCP_ALLOWED_CIDR`)
4. **Memory:** `graph__query`, `graph__counts` — read the graph before re-scanning
5. **Act:** typed weapons (`nuclei__scan`, `sqlmap__scan`) over `arsenal__run`
6. **Parallel:** batch independent reads; sequence mutating/offensive ops

## Safety

- Catastrophic ops refused by default on MCP
- Offensive/grinder tools gated until `METEOR_MCP_ALLOWED_CIDR` or `METEOR_MCP_ALLOW_DANGER=1`
- `METEOR_MCP_READ_ONLY=1` hides mutating tools
- Authorized targets only

## References

- [docs/mcp-arsenal.md](../../docs/mcp-arsenal.md)
- [docs/tools.md](../../docs/tools.md)
- [agents/kitt.md](../../agents/kitt.md)

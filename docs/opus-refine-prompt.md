# Opus Refinement Prompt — Meteor MCP Suite Toolkit

> **STATUS (2026-07-02): COMPLETE.** Phase 1 (Cursor kit) + P0–P3 + KITT persona +
> grinder scanner fix. **75** capabilities; **478** tests pass (4 OS-backend failures:
> clipboard/keychain on headless Linux). Ready to commit and use in Cursor.

---

## What was built

| Layer | Artifacts |
|-------|-----------|
| **Tool core** | 75 caps; headless graph/grinder via `asset_context.py` |
| **MCP** | `meteor-mcp`, policy gates, rich schemas, KITT instructions |
| **KITT** | `app/agent/kitt.py`, loop orchestration, UI plan hints |
| **Cursor kit** | plugin, skills (meteor + kitt), `agents/kitt.md`, scripts |

## Remaining backlog (optional, not blocking)

- Model failover chain across backends
- Session persistence across restarts
- Context compression for long tool chains

## Original prompt (archived)

The sections below were the original refinement spec. All P0–P3 items are done.

---

## Role

You are the lead engineer refining **Meteor** (`rackikage/Meteor`) into a production-grade **MCP suite toolkit** for Cursor and other MCP clients. The foundation is done. Your job is to harden, extend, and polish — not rebuild.

## Repo & environment

- **Local path:** `/home/emperor/Meteor`
- **Remote:** `https://github.com/rackikage/Meteor` (branch `main`, Python 3.11+)
- **MCP entrypoint:** `/home/emperor/Meteor/.venv/bin/meteor-mcp`
- **Verified:** 75 capabilities; stdio MCP; danger + offensive gates; KITT bundled

## Architecture (non-negotiable)

```
bootstrap_tools() → SystemToolRegistry
ToolExecutor.CAPABILITIES  ← single source of truth
         │
         ├── AgentChatLoop + KITT (chatbot_loop.py, kitt.py)
         └── meteor-mcp (app/mcp/server.py) — projection only
```

**Do NOT:** greenfield TypeScript MCP, second registry, compound workflow tools.

## Already shipped

Phase 1 Cursor kit, P0 headless grinder/graph, P1 MCP policy, P2 schemas,
P3 docs/tests, KITT persona + agent kit. See `CLAUDE.md` and `docs/mcp-arsenal.md`.

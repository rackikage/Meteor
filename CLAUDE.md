# Meteor — architecture reference

Meteor is a local-first AI runtime: agentic chat on the user's machine with permissive
local policy (shell, filesystem, networking, recon, desktop integration). External
AIs drive the same tool core via **meteor-mcp** (stdio MCP).

## Conventions

- Python 3.11+, `from __future__ import annotations`
- Tools: `bootstrap_tools()` → registry; `ToolExecutor.CAPABILITIES` = single source of truth
- MCP names: `tool__operation` (projection of `tool.operation`)
- Policy: desktop = permissive; MCP = `app/mcp/policy.py` env gates
- Run tests: `./.venv/bin/python -m pytest -q`
- Regenerate tool list: `./scripts/generate-tools-doc.py`
- Repo: `https://github.com/rackikage/Meteor.git`, branch `main`

## Architecture map

```
                    ┌─────────────────────────────┐
                    │  bootstrap_tools() → registry│
                    │  ToolExecutor.CAPABILITIES   │  ← 97 caps (single source)
                    └──────────────┬──────────────┘
           ┌───────────────────────┼───────────────────────┐
           ▼                       ▼                       ▼
   Desktop AgentChatLoop    meteor-mcp (stdio)      MeteorAgent (API)
   + KITT / Loop Freak      + McpPolicy gates       + StrategyEngine
```

### Desktop chat path

```
User → web/static/app.js (SSE) → POST /api/v1/agent/chat
  → AgentChatLoop.run() (chatbot_loop.py)
    → persona: kitt | loop_freak (loop_freak.py)
    → model.stream/complete → _parse_tool_calls()
    → ToolExecutor.execute() → results → loop until answer
```

### MCP path

```
Cursor / Claude Code → spawns meteor-mcp
  → list_tools: CAPABILITIES filtered by McpPolicy
  → call_tool: danger gate → policy gate → ToolExecutor.execute()
  → headless asset context on first graph/grinder use (mcp/context.py)
```

Key files:

| Area | Files |
|------|--------|
| MCP server | `app/mcp/server.py`, `policy.py`, `context.py` |
| KITT / Loop Freak | `app/agent/kitt.py`, `loop_freak.py`, `chatbot_loop.py` |
| Layers | `app/infiltration/`, `app/exploit/`, `app/reverse/`, `app/interpreter/`, `app/loop_freak/` |
| Tools | `app/tools/bootstrap.py`, `app/runtime/tool_executor.py` |
| Autonomous API agent | `app/agent/loop.py` (MeteorAgent — not MCP-exposed) |
| Cursor kit | `.cursor-plugin/`, `agents/`, `skills/`, `mcp.json` |

## MCP env vars (summary)

| Variable | Effect |
|----------|--------|
| `METEOR_MCP_ALLOWED_CIDR` | Unlock + scope offensive tools |
| `METEOR_MCP_READ_ONLY=1` | Hide mutating/active ops |
| `METEOR_MCP_ALLOWED_ROOT` | Chroot filesystem for MCP process |
| `METEOR_MCP_ALLOW_DANGER=1` | Lift danger + offensive gates |

Full detail: `docs/mcp-arsenal.md`

## Layers shipped (local, uncommitted to origin unless pushed)

- **Infiltration** — footprint, intercept, peek, status
- **Exploit** — intel, prioritize, chain, gaps, cve_map (research only)
- **Reverse** — static RE on local files
- **Interpreter** — persistent Python + bash (blocks R/B shell patterns)
- **Loop Freak** — multi-round recon cycles + aggressive chat persona

## Known gaps / backlog

- **Model failover** — no cross-backend chain yet (Pollinations → Groq → Ollama)
- **Context window** — long tool chains need summarization for 8K models
- **Session persistence** — web chat history in-memory only
- **MeteorAgent.infiltrate()** — wired in API runtime, not in `ToolExecutor.CAPABILITIES` / MCP

## Docs index

| Doc | Purpose |
|-----|---------|
| `docs/mcp-arsenal.md` | MCP mount, how it works, safety |
| `docs/tools.md` | All 97 capabilities (generated) |
| `docs/interpreter.md` | Local code execution |
| `docs/reverse-engineering.md` | Static RE workflow |
| `docs/firewalls-network-security-2027.md` | Perimeter research context |

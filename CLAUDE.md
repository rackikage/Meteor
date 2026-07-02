# Meteor — architecture reference

Meteor is an **MCP kit** — a stdio server (`meteor-mcp`) that projects a local
tool core (filesystem, shell, network, nmap, pentest weapons, asset graph,
grinder, RE, interpreter, loop-freak recon) to any MCP-capable agent (Claude
Code, Cursor, OpenCode, others). External agents bring the model; Meteor
brings the tools.

Local policy is permissive (the operator owns the box; `sudo` works). The MCP
surface is separately gated by env vars in `app/mcp/policy.py`.

## Conventions

- Python 3.11+, `from __future__ import annotations`
- Tools: `bootstrap_tools()` → registry; `ToolExecutor.CAPABILITIES` = single source of truth
- MCP names: `tool__operation` (projection of `tool.operation`)
- Policy: local = permissive; MCP = env gates (`METEOR_MCP_ALLOWED_CIDR`, `READ_ONLY`, `ALLOW_DANGER`, `ALLOWED_ROOT`)
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
    meteor-mcp (stdio)      meteor-chat REPL         MeteorAgent (API)
    + McpPolicy gates       (optional KITT /         + StrategyEngine
    ← the product           Loop Freak sidekick)     (in-process, not MCP)
```

### MCP path (primary)

```
Cursor / Claude Code / OpenCode → spawns meteor-mcp
  → list_tools: CAPABILITIES filtered by McpPolicy
  → call_tool: danger gate → policy gate → ToolExecutor.execute()
  → headless asset context on first graph/grinder use (mcp/context.py)
  → server instructions carry KITT orchestration doctrine
```

### Optional in-process REPL

```
meteor-chat → AgentChatLoop (chatbot_loop.py)
  → persona: kitt | loop_freak (kitt.py, loop_freak.py)
  → hosted model (Pollinations by default; Groq / Cerebras / Gemini if keyed)
  → _parse_tool_calls → ToolExecutor.execute() → loop
```

The REPL is a convenience for users who want a standalone terminal without
mounting Meteor into another agent. Not the product. **No local inference**
(Ollama, llama.cpp) is shipped in the default config — the tools are the
value, not a bundled brain.

Key files:

| Area | Files |
|------|--------|
| MCP server | `app/mcp/server.py`, `policy.py`, `context.py` |
| KITT / Loop Freak | `app/agent/kitt.py`, `loop_freak.py`, `chatbot_loop.py` |
| Layers | `app/infiltration/`, `app/exploit/`, `app/reverse/`, `app/interpreter/`, `app/loop_freak/` |
| Tools | `app/tools/bootstrap.py`, `app/runtime/tool_executor.py` |
| Autonomous API agent | `app/agent/loop.py` (MeteorAgent — not MCP-exposed) |
| Cursor kit | `.cursor-plugin/`, `agents/`, `skills/`, `mcp.json` |
| OpenCode kit | `opencode.json`, `.opencode/agents/` |
| Terminal REPL | `app/terminal/`, entry `meteor-chat` |

## MCP env vars (summary)

| Variable | Effect |
|----------|--------|
| `METEOR_MCP_ALLOWED_CIDR` | Unlock + scope offensive tools |
| `METEOR_MCP_READ_ONLY=1` | Hide mutating/active ops |
| `METEOR_MCP_ALLOWED_ROOT` | Chroot filesystem for MCP process |
| `METEOR_MCP_ALLOW_DANGER=1` | Lift danger + offensive gates |

Full detail: `docs/mcp-arsenal.md`

## Layers shipped

- **Infiltration** — footprint, intercept, peek, status
- **Exploit** — intel, prioritize, chain, gaps, cve_map (research only, no payloads)
- **Reverse** — static RE on local files
- **Interpreter** — persistent Python + bash (blocks R/B shell patterns)
- **Loop Freak** — multi-round recon cycles + aggressive REPL persona
- **OpenCode kit** — `opencode.json` + `.opencode/agents/` (kitt, loop-freak, terminal)
- **Terminal bridge** — `meteor-chat` REPL with persona/model switching

## Known gaps / backlog

- **Model failover** — no cross-backend chain yet (Pollinations → Groq → Cerebras)
- **Context window** — long tool chains need summarization for 8K models
- **Session persistence** — REPL history in-memory only
- **MeteorAgent.infiltrate()** — wired in API runtime, not in `ToolExecutor.CAPABILITIES` / MCP

## Docs index

| Doc | Purpose |
|-----|---------|
| `docs/mcp-arsenal.md` | MCP mount, how it works, safety |
| `docs/tools.md` | All 97 capabilities (generated) |
| `docs/opencode.md` | OpenCode integration |
| `docs/interpreter.md` | Local code execution |
| `docs/reverse-engineering.md` | Static RE workflow |
| `docs/terminal-bridge.md` | `meteor-chat` REPL |
| `docs/firewalls-network-security-2027.md` | Perimeter research context |

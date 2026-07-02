# Meteor — architecture reference

Meteor is a local-first AI runtime: a single agentic chat loop on the user's own
machine with a permissive local policy (full shell, filesystem, networking, recon,
desktop integration). "Meteor is the model" — a web GUI drives a tool-using loop
backed by hosted keyless/free models with local Ollama fallback.

## Conventions
- Python 3.11+, `from __future__ import annotations`
- Tools: `bootstrap_tools()` registers, `ToolExecutor.CAPABILITIES` maps tool→method→params
- Model profiles: `config/meteor.yaml` + `_OPENAI_COMPATIBLE_BACKENDS` in registry.py
- Adapter pattern: `complete()` + `stream()` + `health()` — see `contract.py`
- Policy: allow-all SQL seeded at priority 0, `auto_approve("*:*")` in bootstrap
- Signal budget: 1000 max, 50/min refill, scores ≤10 are silent (free)
- Max iterations: 12 in `AgentTurn`
- Import test: `python -c "from app.bootstrap import bootstrap; r = bootstrap()"`
- Run full suite: `./.venv/bin/python -m pytest -q`
- Repo: `origin` = `https://github.com/rackikage/Meteor.git`, branch `main`

## Architecture map

```
User prompt → web/static/app.js (SSE) → POST /api/v1/agent/chat (agent.py)
  → AgentChatLoop.run() (chatbot_loop.py) — KITT persona via app/agent/kitt.py
    → model.complete() — via ModelRegistry.get_adapter() (registry.py)
      → groq_adapter.py / ollama_adapter.py — OpenAI-compat or local
    → _parse_tool_calls() — JSON object or array [{tool, operation, params}, ...]
    → ToolExecutor.execute() (tool_executor.py)
      → policy check → budget check → _invoke_tool()
    → results fed back to model → loop until final answer
```

Key files:
- `kitt.py` — KITT persona, grouped tool manual, retry/recovery/plan helpers; MCP instructions
- `chatbot_loop.py` — streaming tool loop; resilient retries, plan events, parallel fan-out
- `tool_executor.py` — `CAPABILITIES` dict, 4-gate execution (validate → policy →
  budget → invoke)
- `app/tools/bootstrap.py` — `bootstrap_tools()` registers every tool permissively
  (filesystem widened to `/`, shell with no blocklist, nmap/pentest/network/web)
- `registry.py` — model adapter factory, priority fallback
- `agent.py` — web SSE endpoint, in-memory session history
- `groq_adapter.py` — OpenAI-compat with retry + keyless backends
- `probe_engine.py` — async TCP probe (concurrent, banner grab)
- `raw_scanner.py` — stateless SYN scanner (root required)
- `web_search.py` — DuckDuckGo/NVD/Exploit-DB searcher, wrapped by `WebIntelTool`
  in `bootstrap.py` and exposed as `web.search/cves/exploits/research`
- `grinder.py` — autonomous infiltration engine, exposed as `grinder.*` caps via `GrinderTool`
- `config/meteor.yaml` — model profiles (default `pollinations-free`, keyless)
- `run.py` — launcher: uvicorn on :8765
- `app/mcp/server.py` — `meteor-mcp` stdio server (thin projection of `CAPABILITIES`)
- `app/mcp/policy.py` — MCP-only env-scoped gates (read-only / CIDR / root / profile)
- `app/runtime/asset_context.py` + `app/mcp/context.py` — headless graph/grinder for MCP (no FastAPI)

## Known gaps / backlog
- **Model failover** — `registry.py:get_adapter()` picks one profile; no
  cross-backend Pollinations → Groq → Cerebras → Ollama chain yet (Groq retries
  internally only).
- **No iterative code-execution loop** — one-shot shell only.
- **Context window** — long tool chains exceed free-model 8K contexts; old tool
  results should be summarized/compressed.
- **Persistence** — session history is in-memory (`_SESSIONS` in `agent.py`);
  dies on restart.

## MCP suite + KITT (done)
- **Phase 1** — Cursor kit: plugin, skills, agents/kitt.md, mcp.json, setup scripts
- **P0** — grinder + asset graph wired (**75** caps); headless via asset_context
- **P1** — MCP policy (read-only, CIDR, root, profile, offensive-gated default)
- **P2** — rich MCP JSON schemas (CAPABILITY_SCHEMAS, ARSENAL_SCHEMAS)
- **KITT** — battle-ready operator persona in-app + MCP instructions + Cursor agent

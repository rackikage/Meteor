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
  → AgentChatLoop.run() (chatbot_loop.py)
    → model.complete() — via ModelRegistry.get_adapter() (registry.py)
      → groq_adapter.py / ollama_adapter.py — OpenAI-compat or local
    → _parse_tool_calls() — JSON object or array [{tool, operation, params}, ...]
    → ToolExecutor.execute() (tool_executor.py)
      → policy check → budget check → _invoke_tool()
    → results fed back to model → loop until final answer
```

Key files:
- `chatbot_loop.py` — agent loop, system prompt (`_tool_manual` advertises every
  capability), tool parsing, 12-iter cap
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
- `grinder.py` — autonomous infiltration engine (NOT wired into the agent loop)
- `config/meteor.yaml` — model profiles (default `pollinations-free`, keyless)
- `run.py` — launcher: uvicorn on :8765

## Known gaps / backlog
- **Model failover** — `registry.py:get_adapter()` picks one profile; no
  cross-backend Pollinations → Groq → Cerebras → Ollama chain yet (Groq retries
  internally only).
- **`grinder.py` not wired** — full AssetGraph → Grinder → Scanner → EventBus
  pipeline exists but is not exposed to the agent loop or CAPABILITIES.
- **No diff-based file editing** — only `filesystem.write` (whole-file rewrite);
  no `filesystem.edit {path, old_string, new_string}`.
- **No iterative code-execution loop** — one-shot shell only.
- **Context window** — long tool chains exceed free-model 8K contexts; old tool
  results should be summarized/compressed.
- **Persistence** — session history is in-memory (`_SESSIONS` in `agent.py`);
  dies on restart.

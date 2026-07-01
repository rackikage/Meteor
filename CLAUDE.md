# Meteor — local-first AI runtime

**Identity**: Meteor IS the model. Not a wrapper, not an nmap frontend. Underlying engines (Pollinations/Groq/Ollama) are implementation details — `/api/v1/agent/model` already returns `"model": "Meteor"`. Everything in the repo should treat nmap/pentest as just capabilities among many, not the identity.

## Architecture map

```
User prompt → web/static/app.js (SSE) → POST /api/v1/agent/chat (agent.py)
  → AgentChatLoop.run() (chatbot_loop.py)
    → model.complete() — via ModelRegistry.get_adapter() (registry.py)
      → groq_adapter.py / ollama_adapter.py — OpenAI-compat or local
    → _parse_tool_call() — JSON block or TOOL: syntax
    → ToolExecutor.execute() (tool_executor.py)
      → policy check (registry.py policy table)
      → budget check (signal_budget.py)
      → _invoke_tool() → subprocess/async probe
    → result fed back to model → loop until final answer
```

**Key files by role:**
- `chatbot_loop.py:95-180` — agent loop, system prompt, tool parsing, 6-iter cap
- `tool_executor.py:76-267` — CAPABILITIES dict, 4-gate execution, tool dispatch
- `bootstrap.py:128-191` — registers all tools permissively (no blocklist, allow-all SQL)
- `registry.py:39-58` — model adapter factory, priority fallback chain
- `agent.py:35-102` — web SSE endpoint, in-memory session history
- `probe_engine.py:77-166` — async TCP probe engine (concurrent, banner grab)
- `groq_adapter.py` — OpenAI-compat adapter, handles keyless Pollinations backend
- `config/meteor.yaml` — model profiles (pollinations-free, groq-fast, ollama-heavy, etc.)
- `run.py` — launcher: venv create, dep install, uvicorn start on :8765

**Conventions:**
- Python 3.11+, no type stubs needed, use `from __future__ import annotations`
- Tools register via `bootstrap_tools()`, capabilities via `ToolExecutor.CAPABILITIES`
- New model backends: add to `_OPENAI_COMPATIBLE_BACKENDS` in registry.py + profile in meteor.yaml
- Shell uses `ShellSandbox.run_sync()` for sync, `run()` for async — bootstrap wires `shell.run` to `run_sync`
- Policy: allow-all SQL seeded at priority 0, `auto_approve("*:*")` called in bootstrap
- Signal budget: 1000 max, 50/min refill, scores ≤10 are silent (free), default unknown tool score = 10

## What to do now

The user wants Meteor positioned as a general-purpose AI runtime. Take these in order:

1. **Tool chaining** — `_parse_tool_call()` only handles single JSON blocks. Make it accept arrays `[{...},{...}]` so the model can request 2+ tools per turn. Execute sequentially, feed all results back together.

2. **Parallel execution** — group independent tool calls from a chained turn and run via `asyncio.gather`. `probe_engine.py` already has the pattern — `execute_batch()` on line 154.

3. **Model failover** — `get_adapter()` in registry.py picks one profile and dies. Add a fallback loop: try primary, catch on first `complete()` failure, try next profile in priority order. Test with `from app.bootstrap import bootstrap; r = bootstrap()`.

4. **Make tools feel like "Meteor"** — update the system prompt in `chatbot_loop.py:73-92` so it introduces itself as "I'm Meteor" not "I am a tool-using assistant running on your machine". Rephrase the capabilities list to sound like native abilities, not a plugin catalog.

5. **Increase max_iterations** — bump from 6 to 12 in `AgentTurn` default and the web endpoint. Complex scan→probe→analyze→report chains need the headroom. Budget gates it anyway.

## Critical — fully implemented but not wired

**`app/agent/web_search.py`** contains a complete WebSearcher class (284 lines) with NVD CVE lookup, Exploit-DB search, DuckDuckGo scraping, and offline mock fallback data. This is **not registered as a tool capability** — the model cannot call `web.search_cves` or `web.search_exploit`. Adding it to CAPABILITIES and bootstrap would give Meteor live intel gathering without any new dependencies (httpx + beautifulsoup4 already in pyproject.toml).

**Registry fallback skips Pollinations** — `_effective_default_profile()` in registry.py loops `_BACKEND_KEY_ENV` (groq, cerebras, gemini_openai, together, openrouter) checking for API keys. Pollinations is keyless so it never appears in that loop. When no API key is set, the code falls back to `ollama-heavy` (config default), completely skipping `pollinations-free` which should be the always-available free fallback.

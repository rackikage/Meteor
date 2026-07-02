# Opus Finish Prompt — Meteor MCP Suite, OpenCode, Push to Main

Copy everything below the line into Claude Opus (or equivalent) as your task prompt. Do not ask clarifying questions unless blocked on git credentials or push permissions.

---

You are finishing **Meteor** (`https://github.com/rackikage/Meteor`, branch `main`) — a local-first Python toolkit whose product is the **tool core**, not embedded LLMs. External agents (Cursor, OpenCode, Claude Code) drive the same capabilities via **meteor-mcp** (stdio MCP). In-app chat uses hosted models only; **do not invest in Ollama, llama.cpp, or local model profiles** for this pass.

## Read first (mandatory)

1. **Repo architecture:** `CLAUDE.md`, `docs/mcp-arsenal.md`, `docs/tools.md`
2. **OpenCode integration spec:** read OpenCode docs on config, MCP, agents, skills, permissions:
   - https://opencode.ai/docs/config/
   - https://opencode.ai/docs/agents/
   - https://opencode.ai/docs/skills
   - https://opencode.ai/docs/permissions
   - Local reference if present: Compound Engineering `docs/specs/opencode.md` (config precedence, `.opencode/agents/`, `mcp` section, `permission` over deprecated `tools`)
3. **What shipped locally (uncommitted):** run `git status` and read diffs. Large feature set is already implemented; your job is integration polish, OpenCode wiring, doc sync, tests green, **one clean commit, push to `main`**.

## Current state (do not re-build from scratch)

**97 capabilities** in `ToolExecutor.CAPABILITIES` (verify: `python -c "from app.runtime.tool_executor import ToolExecutor; print(len(ToolExecutor.CAPABILITIES))"`).

| Layer | Path | MCP-style names |
|-------|------|-----------------|
| Infiltration | `app/infiltration/` | `infiltration__footprint`, `intercept`, `peek`, `status` |
| Exploit (research only) | `app/exploit/layer.py` | `exploit__intel`, `prioritize`, `chain`, `gaps`, `cve_map` |
| Reverse engineering | `app/reverse/layer.py` | `reverse__identify`, `strings`, `scan`, `symbols`, `analyze` |
| Loop Freak | `app/loop_freak/`, `app/agent/loop_freak.py` | `loopfreak__pulse`, `cycle`, `status` |
| Interpreter (local code only) | `app/interpreter/local.py` | `interpreter__run`, `bash`, `reset`, `status` — **blocks R/B shell patterns** |
| Terminal bridge (CLI, not MCP) | `app/terminal/` | `meteor-chat` console script |

**Personas:** KITT + Loop Freak in `app/agent/kitt.py`, `loop_freak.py`, wired via `AgentTurn.persona` in `chatbot_loop.py`.

**Cursor kit:** `.cursor-plugin/plugin.json`, `agents/*.md`, `skills/*/SKILL.md`, root `mcp.json`.

**Docs:** `docs/firewalls-network-security-2027.md`, `reverse-engineering.md`, `interpreter.md`, `terminal-bridge.md`. Stale `docs/opus-refine-prompt.md` was deleted — do not restore it.

**Tests:** `tests/test_infiltration.py`, `test_exploit_reverse_layers.py`, `test_loop_freak.py`, `test_interpreter.py`, `test_terminal_bridge.py` (28 tests). Full suite ~537 tests; **4 pre-existing failures** in `tests/test_system_tools.py` (clipboard/keychain on headless Linux without wl-clipboard/xclip). Fix by skipping when tools unavailable, or mark xfail — do not leave suite red.

## Your mission

### A. Ditch models and locals

Meteor’s value is **tools + MCP + personas**, not shipping local inference.

1. **`config/meteor.yaml`:** Remove or comment out Ollama and llama.cpp profiles (`ollama-*`, `llama3.2-3b-local`). Keep **hosted** profiles: `pollinations-free` (default), `pollinations-smart`, and optional `groq-*`, `cerebras-fast`, `gemini-flash` for users who set API keys. Default profile stays keyless Pollinations.
2. **`app/models/registry.py`:** Ensure default selection never requires Ollama running. Remove or guard any code paths that assume local Ollama for the web GUI “smart” toggle — prefer hosted heavy profile or `pollinations-smart`.
3. **Docs/README/CLAUDE.md:** Stop presenting Ollama/local GGUF as primary paths. Mention them only as optional appendix, or remove. Terminal (`meteor-chat`) and web chat should document hosted defaults.
4. **Do not** add new model backends or local inference work in this PR.

### B. OpenCode integration

Wire Meteor so OpenCode can drive the same arsenal as Cursor.

1. Add **`opencode.json`** (or `opencode.jsonc`) at repo root with:
   - `mcp.meteor` pointing at `.venv/bin/meteor-mcp` (or `scripts/run-meteor-mcp.sh` for portable path)
   - Sensible `permission` defaults: allow read/recon; `ask` or `deny` for destructive shell/filesystem writes unless user overrides
   - Optional `instructions` summarizing KITT fluid fight doctrine (compact — link to `agents/kitt.md`)
2. Add **`.opencode/agents/`** (OpenCode layout) — adapt from existing `agents/`:
   - `kitt.md`, `loop-freak.md`, `terminal.md` with OpenCode-compatible frontmatter (`description`, `mode: primary` where appropriate)
3. Add **`.opencode/skills/`** or document that OpenCode also discovers `skills/` via `skills.paths` — prefer symlinks or thin wrappers if duplication is ugly; keep single source in `skills/` when possible.
4. Smoke test: document in README a one-liner — `cd Meteor && pip install -e . && opencode` (or equivalent) with meteor MCP enabled.
5. Read user global config `~/.config/opencode/opencode.jsonc` — merge, don’t clobber; project config should be self-contained.

### C. Sync and polish

1. Regenerate **`docs/tools.md`:** `./scripts/generate-tools-doc.py`
2. Sync **“97 tools”** everywhere: `.cursor-plugin/plugin.json`, `agents/kitt.md`, `skills/meteor/SKILL.md`, `skills/kitt/SKILL.md`, README capability tables.
3. **`CLAUDE.md` backlog:** Mark done: exploit layer, reverse layer, infiltration pipeline, loop freak, interpreter, terminal bridge, OpenCode kit. Leave only genuine gaps (e.g. model failover chain, session persistence).
4. Ensure **`pyproject.toml`** scripts: `meteor-mcp`, `meteor-chat`; deps include `prompt_toolkit`, `rich`.

### D. Verify

```bash
cd /path/to/Meteor
pip install -e .
python -c "from app.bootstrap import bootstrap; bootstrap()"
python -c "from app.runtime.tool_executor import ToolExecutor; print(len(ToolExecutor.CAPABILITIES))"
pytest -q
# Optional: pytest -q --ignore=tests/test_system_tools.py if clipboard still fails headless
meteor-mcp  # should start stdio (Ctrl+C after sanity)
meteor-chat --help
```

All new layer tests must pass. Target: **zero failures** or documented skip for environment-specific clipboard/keychain.

### E. Git commit and push to main

User explicitly wants this landed on **`main`**.

1. `git status`, `git diff`, `git log -5` — follow repo commit style.
2. Stage all intentional changes (no `.venv/`, no secrets, no `data/*.db` if gitignored).
3. One cohesive commit message, e.g.:

```
feat: MCP layers, terminal bridge, OpenCode kit — 97 tools

Add infiltration, exploit, reverse, interpreter, loop freak layers;
meteor-chat terminal REPL; OpenCode opencode.json + agents; hosted-only
model defaults; docs and tests.
```

4. Push: `git push origin main` (use permissions if needed). If push fails (auth, branch protection), report exact error and what the user must run — do not force-push.

## Hard boundaries (never implement)

- No botnet, C2, distributed malware orchestration
- No reverse/bind shell generators, listeners, or payload dropper automation
- Exploit layer stays **research** (CVE/Exploit-DB, scanner playbooks) — no auto weapon fire
- Interpreter blocks obvious R/B shell patterns; KITT prompt already says no R/B shells

## Architecture reminder (single source of truth)

```
bootstrap_tools() → registry
ToolExecutor.CAPABILITIES
    ├── AgentChatLoop (web + meteor-chat) + KITT / Loop Freak
    ├── meteor-mcp (stdio, McpPolicy gates)
    └── NOT duplicated in a second tool registry
```

MCP tool names use `__` not `.` (`graph__query`). Headless graph/grinder: `app/mcp/context.py` + `asset_context`.

## Success criteria

- [ ] OpenCode can mount `meteor` MCP from project `opencode.json`
- [ ] Local/Ollama profiles removed from default config path; hosted default works keyless
- [ ] 97 caps documented consistently
- [ ] `pytest` green (or clipboard tests skipped on headless with reason)
- [ ] Committed and pushed to `origin/main`
- [ ] README section: Quick start for Cursor **and** OpenCode **and** `meteor-chat`

When done, reply with: commit SHA, push confirmation, capability count, test summary, and exact commands for the operator to reload Cursor MCP and try OpenCode.

## Operator handoff (after Opus completes)

```bash
cd ~/Meteor && git pull origin main
pip install -e .
# Cursor: Developer → Reload Window, enable meteor MCP
# OpenCode: opencode from repo root (reads opencode.json)
meteor-chat                    # live KITT terminal session
meteor-chat --persona loop_freak
export METEOR_MCP_ALLOWED_CIDR=10.0.0.0/24   # unlock offensive MCP tools when scoped
```

Optional API keys (`GROQ_API_KEY`, etc.) upgrade the in-app model; MCP tools work regardless.

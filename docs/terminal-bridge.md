# Meteor Terminal Bridge — Bundling & Usage Guide

## What It Is

The Meteor Terminal Bridge is a standalone interactive REPL that runs KITT (or Loop Freak) entirely in your terminal — no web GUI, no Cursor, no browser required. It builds a lightweight runtime (config, storage, model registry, tool executor) and wires the same `AgentChatLoop` that powers the web chat and Cursor MCP to a rich terminal renderer. Every tool call, every retry, every streaming token appears live in your terminal as it happens.

This is the missing third path. Meteor previously had two interfaces: the web GUI (FastAPI + SSE) and Cursor MCP (stdio subprocess). The terminal bridge adds a direct human-to-agent channel that works over SSH, in tmux panes, on headless servers, or anywhere you have a shell.

## Installation

The terminal bridge ships as part of the Meteor package. After cloning the repo:

```bash
cd /path/to/Meteor
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

This installs all dependencies including `prompt_toolkit>=3.0` (multi-line editing, history, auto-suggestions) and `rich>=13.0` (colored panels, live streaming output). Both are optional — the terminal gracefully degrades to plain `input()` and stderr when they're missing, so it works in minimal environments too.

The install registers two console scripts:
- `meteor-mcp` — the existing MCP stdio server for Cursor
- `meteor-chat` — the new terminal REPL

Verify with:

```bash
meteor-chat --help
```

## Quick Start

Launch the default KITT session:

```bash
meteor-chat
```

You'll see a banner showing the active persona, tool count, and model profile. Type a prompt and press Enter. KITT thinks, calls tools, and streams the answer — all rendered live:

```
meteor> what's on my network?

⟳ thinking… round 0
  ⚡ network.scope
    ✓ network.scope [ok] 142ms
⟳ thinking… round 1
  ⚡ graph.counts
    ✓ graph.counts [ok] 38ms

Your gateway is 192.168.1.1 on a /24. The asset graph currently holds
12 hosts and 47 services from your last scan session...
```

## Personas

Two personas are available:

**KITT** (default) — the standard battle-ready operator. 12 max iterations per turn, balanced tool chaining, fluid fight doctrine.

```bash
meteor-chat --persona kitt
```

**Loop Freak** — aggressive multi-round mode. Automatically bumps max iterations to 25 and uses a pushier continue nudge. Pairs with `loopfreak.cycle` for headless recon pulses that spin until the graph plateaus.

```bash
meteor-chat --persona loop_freak
```

Switch personas mid-session with the `/persona` command:

```
meteor> /persona loop_freak
Switched to LOOP_FREAK
```

## Model Selection

The terminal uses the same model registry as the web GUI. By default it auto-selects the best available profile (Groq if `GROQ_API_KEY` is set, Cerebras, Gemini, etc., falling back to keyless Pollinations or local Ollama).

Specify a profile at launch:

```bash
meteor-chat --model groq-versatile
meteor-chat --model ollama-heavy
```

Or switch mid-session:

```
meteor> /model
Model profiles:
  * pollinations-free
    pollinations-smart
    groq-instant
    groq-versatile
    ollama-heavy
    ollama-fast

meteor> /model groq-versatile
Switched to groq-versatile (llama-3.3-70b-versatile)
```

## One-Shot Mode

For quick queries without entering the REPL, use `--one-shot`. The prompt runs, the answer prints, and the process exits:

```bash
meteor-chat --one-shot "run infiltration.footprint and report scope"
meteor-chat --one-shot "what tools are registered?" --plain
```

This is useful for scripting, cron jobs, piping output to other tools, or Cursor agent invocations that need a single answer.

## REPL Commands

Inside the interactive session, slash commands control the environment:

| Command | Action |
|---------|--------|
| `/help` | Show all available commands |
| `/persona kitt` | Switch to KITT persona |
| `/persona loop_freak` | Switch to Loop Freak persona |
| `/model` | List all model profiles (marks active) |
| `/model <profile>` | Switch to a specific model profile |
| `/tools` | List all 90+ registered tools grouped by domain |
| `/clear` | Clear session conversation history |
| `/history` | Show the last 20 messages in session history |
| `/quit` or `/exit` | Exit the terminal |

Everything else is a prompt to KITT. There's no special syntax — just type what you want done.

## Live Rendering

The renderer translates `AgentChatLoop` events into terminal output:

- **Thinking** — `⟳ thinking… round N` appears while the model generates
- **Plans** — multi-step plans render in a cyan bordered panel
- **Tool calls** — `⚡ tool.operation(params)` with danger warnings when applicable
- **Tool results** — `✓ tool.operation [ok] 142ms` in green, or `✗ [error]` in red with truncated previews
- **Retries** — `↻ retry tool.operation (attempt 2): timeout` shown dimmed
- **Streaming answer** — KITT's final response streams character-by-character to stdout
- **Errors** — bold red error messages for model failures
- **Iteration limit** — notification when the loop exhausts its budget

Use `--plain` to disable rich formatting for piping, logging, or environments without ANSI support.

## Architecture

The bridge is intentionally thin — four modules totaling under 400 lines:

```
app/terminal/
  __init__.py    — package exports
  main.py        — CLI arg parser, meteor-chat entry point
  bridge.py      — TerminalBridge: lightweight runtime + AgentChatLoop driver
  renderer.py    — TerminalRenderer: event callback → rich/plain output
  repl.py        — prompt_toolkit REPL loop + slash command dispatch
```

`TerminalBridge.initialize()` builds just enough infrastructure:
1. `bootstrap()` — loads `config/meteor.yaml`
2. `build_sqlite_adapter()` — opens the local SQLite database
3. `build_model_registry()` — constructs model adapters from config profiles
4. `bootstrap_tools()` — registers all 90+ tools into the system registry
5. `ToolExecutor()` — the same 4-gate execution pipeline (validate → policy → budget → invoke)

Then `run_turn()` creates an `AgentTurn` and calls `AgentChatLoop.run()` with the renderer's `on_event` as the callback. The loop streams from the model, parses tool calls, executes them through `ToolExecutor`, and feeds results back — identical to the web GUI path, just rendered differently.

## Cursor Integration

The terminal agent (`agents/terminal.md`) and skill (`skills/terminal/SKILL.md`) let Cursor's AI spawn terminal sessions. When you say "open a terminal session" or "run KITT in the terminal", Cursor can launch `meteor-chat` in its integrated terminal panel.

For quick queries from Cursor without entering the REPL:

```bash
meteor-chat --one-shot "check the asset graph and report host count"
```

The Cursor agent knows when to suggest the terminal: persistent sessions, real-time tool observation, SSH/remote use, or when the user wants Loop Freak cycles running in a visible pane.

## Configuration

All configuration flows through `config/meteor.yaml` and environment variables — the same ones the web GUI and MCP server use:

- `GROQ_API_KEY`, `CEREBRAS_API_KEY`, etc. — auto-select hosted model profiles
- `METEOR_MCP_ALLOWED_CIDR` — scope offensive tools to a target network
- `METEOR_MCP_READ_ONLY=1` — hide mutating tools (affects terminal too)
- `METEOR_MCP_ALLOW_DANGER=1` — lift catastrophic action gates

The terminal respects the same policy gates as MCP. Dangerous actions still trigger confirmation prompts; offensive tools still require an authorized CIDR scope.

## Session Persistence

Session history is in-memory only (matching the web GUI's `_SESSIONS` pattern). It persists across turns within a single `meteor-chat` process but dies on exit. Use `/history` to review, `/clear` to reset. The `--session` flag provides history isolation if you run multiple terminal instances.

## Dependencies Summary

| Package | Purpose | Required |
|---------|---------|----------|
| `prompt_toolkit>=3.0` | Multi-line editing, history, auto-suggest | No (falls back to `input()`) |
| `rich>=13.0` | Colored panels, live rendering | No (falls back to plain text) |
| `pyyaml>=6.0` | Config loading | Yes |
| `mcp>=1.0` | Tool registry (shared with MCP server) | Yes |
| All other Meteor deps | Model adapters, tools, storage | Yes |

## Troubleshooting

**"meteor-chat: command not found"** — Run `pip install -e .` from the Meteor root to register the console script.

**Model errors on first prompt** — Check that at least one model backend is reachable. Set `GROQ_API_KEY` for hosted, or start Ollama (`ollama serve`) for local. Run `meteor-chat --model pollinations-free` for keyless fallback.

**Tool calls fail with POLICY_DENIED** — Set `METEOR_MCP_ALLOWED_CIDR` for offensive tools, or `METEOR_MCP_ALLOW_DANGER=1` for unrestricted mode.

**No colors / garbled output** — Use `--plain` flag or set `TERM=dumb`.

**Clipboard/keychain tools fail** — These need system packages (`wl-clipboard` or `xclip` for clipboard). They're optional and don't affect the core loop.

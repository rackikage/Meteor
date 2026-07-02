---
name: terminal
description: Meteor terminal bridge — spawn live KITT/Loop Freak REPL sessions from Cursor or CLI. Use for "terminal", "live session", "meteor-chat", "interactive shell", "run KITT outside Cursor".
---

# Terminal Bridge

Interactive terminal REPL for Meteor's agent loop — KITT or Loop Freak live in your terminal.

## When to activate

- User says **terminal**, live session, meteor-chat, interactive shell
- User wants to watch tool calls happen in real time
- User wants KITT running outside Cursor (SSH, tmux, etc.)
- User wants a persistent recon session in a terminal pane

## Quick start

```bash
# Install (adds meteor-chat to PATH)
cd /path/to/Meteor && pip install -e .

# Launch interactive REPL
meteor-chat

# Loop Freak mode
meteor-chat --persona loop_freak

# One-shot query (no REPL)
meteor-chat --one-shot "run infiltration.footprint"

# Specific model
meteor-chat --model groq-versatile

# Plain text (no rich formatting)
meteor-chat --plain
```

## REPL commands

| Command | Action |
|---------|--------|
| `/help` | Show all commands |
| `/persona kitt` | Switch to KITT persona |
| `/persona loop_freak` | Switch to Loop Freak |
| `/model [profile]` | Show or switch model profile |
| `/tools` | List all 90+ registered tools |
| `/clear` | Clear session history |
| `/history` | Show conversation history |
| `/quit` | Exit the REPL |

## Architecture

```
meteor> prompt
  → TerminalBridge.run_turn(prompt)
    → AgentChatLoop.run(turn, renderer.on_event)
      → model.stream() → tool calls → ToolExecutor.execute()
    → TerminalRenderer renders events live:
        ⟳ thinking… round N
        ⚡ tool.operation(params)
          ✓ result [ok] 142ms
        KITT's final answer streams here…
```

The bridge builds a lightweight runtime (config + storage + model + tools) without FastAPI or the web GUI. Same `AgentChatLoop`, same `ToolExecutor`, different output.

## Spawning from Cursor

Use Cursor's integrated terminal:

```bash
# In Cursor terminal
meteor-chat --persona kitt
```

Or one-shot for quick queries:

```bash
meteor-chat --one-shot "what's in the asset graph?"
```

## Dependencies

- `prompt_toolkit>=3.0` — multi-line editing, history, auto-suggest
- `rich>=13.0` — colored panels, tool call rendering, streaming output
- Both are optional — falls back to plain `input()` + stderr when missing

## References

- Entry point: [app/terminal/main.py](../../app/terminal/main.py)
- Bridge: [app/terminal/bridge.py](../../app/terminal/bridge.py)
- Renderer: [app/terminal/renderer.py](../../app/terminal/renderer.py)
- REPL: [app/terminal/repl.py](../../app/terminal/repl.py)
- Agent: [agents/terminal.md](../../agents/terminal.md)

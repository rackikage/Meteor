# OpenCode integration

Meteor ships as a first-class MCP kit for [OpenCode](https://opencode.ai).
Project config: [`opencode.json`](../opencode.json). Agents:
[`.opencode/agent/`](../.opencode/agent/).

## Quick start

```bash
cd /path/to/Meteor
pip install -e .
opencode
```

That's it. OpenCode reads `opencode.json` from the repo root, spawns
`meteor-mcp` as a local MCP server (via `scripts/run-meteor-mcp.sh` so the
venv resolves correctly), and mounts all 97 capabilities as
`mcp__meteor__<tool>__<op>` tools.

## What ships

### `opencode.json`

- `mcp.meteor` — local stdio server pointing at `scripts/run-meteor-mcp.sh`
- `permission` defaults:
  - `edit: ask` — every file edit asks (override to `allow` per-user if you trust the flow)
  - `bash` — read-only recon (`ls`, `cat`, `rg`, `grep`, `git status/diff/log`,
    `pytest`, `meteor-chat`) is `allow`; destructive patterns (`rm -rf *`,
    `sudo rm *`) are `deny`; everything else is `ask`
  - `webfetch: ask`
- `instructions` — loads `agents/kitt.md` + `agents/loop-freak.md` as system
  context so KITT doctrine reaches OpenCode even without invoking the agent
  files directly

### `.opencode/agent/`

| Agent | Mode | Role |
|-------|------|------|
| `kitt.md` | primary | Battle-ready operator persona for authorized local recon / pentest |
| `loop-freak.md` | primary | KITT that doesn't stop early — multi-round loopfreak cycles |
| `terminal.md` | subagent | Spawns `meteor-chat` REPL sessions |

OpenCode picks these up automatically from the `.opencode/agent/` directory.
Switch with `/agent kitt`, `/agent loop-freak`, etc.

## Precedence

OpenCode merges configs in this order (later wins):

1. User global: `~/.config/opencode/opencode.jsonc`
2. Project: `./opencode.json`
3. CLI flags

Meteor's project config is self-contained — it doesn't clobber user
preferences (model, theme, personal permissions). The `mcp.meteor` entry
just adds a new server; other user MCP servers keep working.

## Unlocking offensive tools

Same env gates as any other MCP mount:

```bash
export METEOR_MCP_ALLOWED_CIDR=10.0.0.0/24   # scope offensive tools
export METEOR_MCP_ALLOW_DANGER=1             # lift catastrophic-op gate (be careful)
export METEOR_MCP_READ_ONLY=1                # hide mutating ops
export METEOR_MCP_ALLOWED_ROOT=/home/me/scan # chroot filesystem tools
```

Set these in your shell before `opencode`, or put them in the `environment`
block of `opencode.json` (project-scoped) — but treat any offensive gate as
per-session, not baked into config.

## Skills

Meteor's skills live in `skills/` (Cursor layout). OpenCode discovers skills
via `skills.paths` — if you want them exposed here too, add:

```jsonc
{
  "skills": {
    "paths": ["./skills"]
  }
}
```

Left off by default because most OpenCode users prefer agents + MCP; opt in
if you want the KITT / Loop Freak / Meteor SKILL.md files as first-class
skill entries.

## Verify

```bash
opencode
> /agent kitt
> mount meteor mcp — what tools?
```

Should list 97 (or fewer if `READ_ONLY` is set). If `meteor-mcp` fails to
start, check `pip install -e .` completed and `scripts/run-meteor-mcp.sh` is
executable.

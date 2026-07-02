# Meteor

> **MCP kit for driving your machine.** Your tools. Your rules. Any AI.

Meteor is a **Model Context Protocol arsenal** — a stdio server (`meteor-mcp`)
that projects a hardened local tool core (filesystem, shell, network, nmap,
pentest weapons, asset graph, autonomous grinder, static RE, interpreter,
loop-freak recon) to any MCP-capable agent. Mount it in **Claude Code**,
**Cursor**, **OpenCode**, or anything else that speaks MCP and drive **97
capabilities** with a single line of config.

**Meteor is not a model.** It's the bridge. Your existing agent brings the
brain; Meteor brings the hands.

Sudo works — local policy is permissive by default (the machine owner is the
one running it). The MCP surface is separately gated so external agents get
read-only unless you unlock them (`METEOR_MCP_ALLOWED_CIDR`, `ALLOW_DANGER`).

## Quick start — mount the MCP kit

```bash
git clone https://github.com/rackikage/Meteor.git
cd Meteor
pip install -e .
```

That installs two console scripts:

| Script | What it does |
|--------|--------------|
| `meteor-mcp` | stdio MCP server — mount this in your agent |
| `meteor-chat` | optional REPL (KITT / Loop Freak) if you want a standalone terminal |

### Claude Code

```bash
claude mcp add meteor -- /path/to/Meteor/.venv/bin/meteor-mcp
```

### Cursor

Project config already at [`.cursor/mcp.json`](.cursor/mcp.json) — open this
repo as your workspace, or symlink it as a local plugin:

```bash
mkdir -p ~/.cursor/plugins/local && ln -sf "$(pwd)" ~/.cursor/plugins/local/meteor
```

Then reload Cursor and enable the **meteor** plugin. Ships with skills, agents,
and the KITT operator persona: [`.cursor-plugin/plugin.json`](.cursor-plugin/plugin.json).

One-shot installer: `./scripts/cursor-mcp-setup.sh`.

### OpenCode

Project config at [`opencode.json`](opencode.json). From the repo root:

```bash
opencode
```

Ships with `.opencode/agents/` (kitt, loop-freak, terminal) and permissive
read/recon defaults; destructive shell/filesystem writes stay `ask` until you
override. See [`docs/opencode.md`](docs/opencode.md).

## The arsenal

**97 capabilities** across one tool core — every consumer (Cursor, Claude
Code, OpenCode, the optional REPL) sees the same registry. Add a tool once,
it appears everywhere. Regenerate the full list: `./scripts/generate-tools-doc.py`
→ [`docs/tools.md`](docs/tools.md).

| Domain | What you get |
|--------|--------------|
| **filesystem** | read, write, edit (surgical), append, list, walk, grep, glob, stat, hash, md5/sha256, which |
| **shell / process** | full `/bin/bash`, list, kill, system stats |
| **network** | local gateway / CIDR / priority-target discovery |
| **nmap** | scan, discover, service/version, NSE scripts |
| **pentest** | kernel firewall posture, perimeter graph analysis, async TCP probe engine |
| **grinder / graph** | autonomous scanning into SQLite asset graph; read-only SQL queries |
| **infiltration** | `footprint`, `intercept`, `peek`, `status` — passive scope + pipeline drain |
| **exploit (research)** | `intel`, `prioritize`, `chain`, `gaps`, `cve_map` — CVE/Exploit-DB, no payload gen |
| **reverse** | static RE on local files — identify, strings, scan, symbols, analyze |
| **interpreter** | persistent Python + bash REPL (blocks reverse/bind shell patterns) |
| **loop freak** | multi-round `loopfreak__cycle` — footprint → intercept → prioritize until plateau |
| **browser** | read page, fill, click, run JS (Playwright, opt-in) |
| **arsenal** | `arsenal__detect` inventories every installed pentest tool; `arsenal__run` executes any of them |
| **weapons** | first-class wrappers: `sqlmap`, `nuclei`, `nikto`, `whatweb`, `wpscan`, `gobuster`, `ffuf`, `feroxbuster`, `hydra`, `searchsploit`, `dnsrecon`, `enum4linux`, `smbmap`, `masscan`, `exiftool`, `binwalk` |
| **desktop** | clipboard, notify, keychain, scheduler |

MCP tool names use `__` instead of `.` (e.g. `filesystem__read`,
`grinder__grind_subnet`). Local (in-process) names use `.`. Same registry.

## Safety gates

Full detail in [`docs/mcp-arsenal.md`](docs/mcp-arsenal.md).

| Env var | Effect |
|---------|--------|
| `METEOR_MCP_READ_ONLY=1` | Hide mutating / active ops |
| `METEOR_MCP_ALLOWED_CIDR` | Unlock + scope offensive tools to a subnet |
| `METEOR_MCP_ALLOWED_ROOT` | Chroot the filesystem tools |
| `METEOR_MCP_ALLOW_DANGER=1` | Lift the catastrophic-op gate |

Catastrophic actions (recursive rm on `/`, `dd if=/dev/zero of=/dev/sda`, etc.)
are refused by default because no human is watching the MCP channel. The
in-app REPL is permissive because you are.

## Personas — KITT and Loop Freak

Meteor ships two operator personas as MCP server instructions and as
agent files for Cursor / OpenCode / Claude Code:

- **KITT** (*Kinetic Infiltration & Tooling Twin*) — battle-ready co-pilot;
  parallel reads, sequential offensive ops, error recovery.
- **Loop Freak** — KITT that doesn't stop early; loops `loopfreak__cycle`
  until the objective is mapped, a policy wall is hit, or alternates are
  exhausted.

Cursor: [`agents/kitt.md`](agents/kitt.md), [`agents/loop-freak.md`](agents/loop-freak.md).
OpenCode: [`.opencode/agents/`](.opencode/agents/).

## Optional — `meteor-chat` REPL

If you want a standalone terminal without mounting the MCP kit into another
agent, `meteor-chat` runs a local REPL that drives the same tool core with a
hosted model (keyless Pollinations by default; auto-upgrades to Groq /
Cerebras / Gemini when `GROQ_API_KEY` / `CEREBRAS_API_KEY` / `GEMINI_API_KEY`
is set):

```bash
meteor-chat                          # default KITT
meteor-chat --persona loop_freak     # Loop Freak
meteor-chat --one-shot "posture check the local firewall"
```

This is a **convenience shell**, not the product. The product is the MCP
kit. See [`docs/terminal-bridge.md`](docs/terminal-bridge.md).

## Architecture

```
                    ┌──────────────────────────────┐
                    │   SHARED TOOL CORE            │
                    │   bootstrap_tools() → registry│
                    │   ToolExecutor.CAPABILITIES   │  ← 97 caps (single source)
                    └──────────────┬───────────────┘
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                     ▼
     ┌────────────────┐  ┌──────────────────┐  ┌──────────────────┐
     │  meteor-mcp    │  │  meteor-chat     │  │  MeteorAgent     │
     │  (stdio MCP —  │  │  (optional REPL, │  │  (in-process     │
     │   the product) │  │   KITT/LoopFreak)│  │   API runtime)   │
     └────────────────┘  └──────────────────┘  └──────────────────┘
```

| File | Role |
|------|------|
| [`app/mcp/server.py`](app/mcp/server.py) | `meteor-mcp` stdio server — the projection |
| [`app/mcp/policy.py`](app/mcp/policy.py) | env gates for external agents |
| [`app/mcp/context.py`](app/mcp/context.py) | headless graph / grinder |
| [`app/runtime/tool_executor.py`](app/runtime/tool_executor.py) | `CAPABILITIES` — single source of truth |
| [`app/tools/bootstrap.py`](app/tools/bootstrap.py) | registers every tool |
| [`app/arsenal/`](app/arsenal/) | installed-tool detection + weapon wrappers |
| [`app/terminal/`](app/terminal/) | `meteor-chat` REPL |
| [`config/meteor.yaml`](config/meteor.yaml) | (optional) chat profiles — hosted only |

Doctrine: [`docs/doctrine.md`](docs/doctrine.md).

## Status

Working MCP arsenal, three integrations (Cursor, Claude Code, OpenCode),
optional REPL, 97 capabilities in one registry.

## License

See repo root.

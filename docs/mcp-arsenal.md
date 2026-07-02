# Meteor as an MCP arsenal

Meteor is not just a standalone app — it's a **weapon any capable AI can drive**.
The `meteor-mcp` server exposes Meteor's entire tool core over the Model Context
Protocol (stdio), so a stronger brain than Meteor's built-in Groq loop — Claude
Code, Cursor, another agent — can mount it and wield the whole arsenal.

## Architecture: one tool core, three consumers

```
                    ┌──────────────────────────────┐
                    │   SHARED TOOL CORE            │
                    │   bootstrap_tools() → registry│
                    │   ToolExecutor.CAPABILITIES   │  ← single source of truth
                    └──────────────┬───────────────┘
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                     ▼
     ┌────────────────┐  ┌──────────────────┐  ┌──────────────────┐
     │  Desktop app   │  │  meteor-mcp      │  │  (future clients)│
     │  (Groq loop +  │  │  stdio server —  │  │                  │
     │   pywebview)   │  │  any AI drives it│  │                  │
     └────────────────┘  └──────────────────┘  └──────────────────┘
```

The MCP server is a **projection** of `ToolExecutor.CAPABILITIES`, not a second
tool definition. Add a capability anywhere and it appears in both the app and
MCP automatically — they can never drift.

## What's exposed

Every capability in the tool core — **75** as of writing:

- **filesystem** — read, write, **edit** (surgical), append, list, walk, grep, glob, stat, hash, …
- **shell** — full bash, no blocklist
- **process / network / clipboard / keychain / scheduler / notify / browser**
- **nmap** — scan, service/version, discovery, NSE
- **pentest** — kernel posture, firewall graph, async probe engine
- **grinder** — autonomous host/subnet/sector scanning into the asset graph
- **graph** — asset-graph schema/tables/counts + read-only SQL over discoveries
- **web** — CVE (NVD), Exploit-DB, web search
- **arsenal.detect** — what pentest tools are installed, grouped by pipeline phase
- **arsenal.run** — run any installed tool with structured output
- **weapon wrappers** — `sqlmap`, `nuclei`, `nikto`, `whatweb`, `wpscan`,
  `gobuster`, `ffuf`, `feroxbuster`, `hydra`, `searchsploit`, `dnsrecon`,
  `enum4linux`, `smbmap`, `masscan`, `exiftool`, `binwalk`

`arsenal.detect` on a Kali box typically reports **70+ installed tools** across
all ten phases (recon → forensics).

## Mounting it

The server ships as a console script after `pip install -e .` (or a first-run
`./Meteor`). Point any MCP client at it:

**Claude Code**
```bash
claude mcp add meteor -- /path/to/Meteor/.venv/bin/meteor-mcp
```

**Cursor / generic** (`mcp.json`)
```json
{
  "mcpServers": {
    "meteor": { "command": "/path/to/Meteor/.venv/bin/meteor-mcp" }
  }
}
```

Then ask the driving AI to, e.g., "use meteor to recon 10.0.0.0/24, fingerprint
any web servers, and check them with nuclei" — it discovers the tools via
`arsenal.detect` and chains them.

## KITT — fluid orchestration

**KITT** (*Kinetic Infiltration & Tooling Twin*) is Meteor's operator persona.
The in-app loop runs KITT via `app/agent/kitt.py` (plans, parallel reads,
transient retries on safe ops, structured recovery). External MCP clients get
the same fight doctrine via server `instructions` and the Cursor kit:

- `agents/kitt.md` — battle-ready operator agent
- `skills/kitt/SKILL.md` — fluid chain: `arsenal__detect` → `network__scope` →
  map → `graph__query` → typed weapons

## Safety

- **Local stdio only.** The server binds no network port; the client runs it as
  a local subprocess it owns.
- **Danger gate.** There is no human on the MCP channel to answer a confirm, so
  catastrophic actions flagged by the classifier (`rm -rf /`, `mkfs`, fork
  bombs, power-off, raw block-device writes, …) are **refused by default** —
  including the same patterns passed via `arsenal.run`. Set
  `METEOR_MCP_ALLOW_DANGER=1` to run fully unattended.
- **Offensive-gated by default.** Autonomous grinding (`grinder.*`) and the
  network weapons (`sqlmap`, `hydra`, `nuclei`, `nikto`, `masscan`, …) plus the
  generic `arsenal.run` are **refused until you declare a scope** — either
  `METEOR_MCP_ALLOWED_CIDR` or `METEOR_MCP_ALLOW_DANGER=1`. Local, read, and
  recon tools (filesystem reads, `graph`, `web`, `nmap`, `arsenal.detect`, local
  posture, `network.scope`) work out of the box.
- **Authorized use only.** The offensive weapons each take an explicit target —
  Meteor never mass-targets. You must own or have written authorization to test
  whatever you point them at.

## Access control & scoping (env vars)

All read once at server start; unset = the permissive-but-offensive-gated
default above. They only ever *tighten* access.

| Env var | Effect |
|---------|--------|
| `METEOR_MCP_ALLOWED_CIDR=10.0.0.0/24` | Unlocks offensive tools **and** restricts every target-taking tool (grinder, nmap, weapons) to hosts inside the CIDR. URLs are host-parsed; domain-name tools (`dnsrecon`, `gobuster.dns`) can't be IP-scoped and are allowed through once a scope is set. |
| `METEOR_MCP_READ_ONLY=1` | Hides and refuses every mutating/active op — `shell`, filesystem writes, `process.kill`, weapons, `grinder.*`, `nmap`, keychain/scheduler/clipboard writes, browser input. Leaves reads, `graph`, `web`, `arsenal.detect`, local posture (≈33 tools). |
| `METEOR_MCP_ALLOWED_ROOT=/path` | Re-registers the filesystem tool chrooted to `/path` for the MCP process only (the desktop app stays rooted at `/`). |
| `METEOR_MCP_PROFILE=minimal` | Coarse filter: local + read only; drops all active-network and offensive tools. `full` (default) / `arsenal` expose everything. |
| `METEOR_MCP_ALLOW_DANGER=1` | Lifts **both** the catastrophic danger gate and the offensive gate — fully unattended. |

Example — a scoped, unattended assessment box:

```bash
METEOR_MCP_ALLOWED_CIDR=10.0.0.0/24 \
METEOR_MCP_ALLOWED_ROOT=/home/op/engagement \
  /path/to/Meteor/.venv/bin/meteor-mcp
```

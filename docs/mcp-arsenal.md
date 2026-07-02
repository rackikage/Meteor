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

## How MCP works (step by step)

1. **Client starts subprocess** — Cursor/Claude Code runs `meteor-mcp` (stdio). No TCP port; stdin/stdout JSON-RPC.

2. **`build_server()` bootstraps once** (`app/mcp/server.py`):
   - `bootstrap_tools()` → every tool in `SystemToolRegistry`
   - `McpPolicy.from_env()` → read `METEOR_MCP_*` gates
   - Optional `METEOR_MCP_ALLOWED_ROOT` → re-register chrooted filesystem
   - `ToolExecutor()` → shared executor the desktop app also uses

3. **`list_tools`** — iterates `ToolExecutor.CAPABILITIES`, filters by policy visibility, exposes each as:
   - **MCP name:** `tool__operation` (dots → double underscore, e.g. `graph__query`)
   - **Description + JSON Schema** from `CAPABILITY_SCHEMAS`

4. **`call_tool(name, arguments)`** — for each invocation:
   ```
   classify_danger()  → REFUSED if catastrophic (unless ALLOW_DANGER)
   policy.gate()    → REFUSED if read-only / out of CIDR / offensive without scope
   executor.execute() → registry.get(tool).method(**params)
   ```
   Execution runs in a worker thread (`anyio.to_thread`) so slow scans don't block the event loop.

5. **Response** — JSON text payload: `{ status, tool, duration_ms, result, error }`.

6. **Headless graph** — first grinder/graph call triggers `get_asset_context()` → `build_headless_context()` (`app/mcp/context.py`) so MCP works without uvicorn.

7. **KITT instructions** — server `instructions` field = condensed orchestration from `build_mcp_instructions()` (`app/agent/kitt.py`).

### Name mapping

| In-app / CAPABILITIES | MCP tool name |
|----------------------|---------------|
| `filesystem.read` | `filesystem__read` |
| `grinder.grind_subnet` | `grinder__grind_subnet` |
| `exploit.chain` | `exploit__chain` |

### Key files

| File | Role |
|------|------|
| `app/mcp/server.py` | stdio MCP server, list/call |
| `app/mcp/policy.py` | env gates (read-only, CIDR, profile) |
| `app/mcp/context.py` | headless graph + grinder for standalone MCP |
| `app/runtime/tool_executor.py` | `CAPABILITIES` + execute |
| `app/tools/bootstrap.py` | register all tools |
| `scripts/run-meteor-mcp.sh` | Cursor plugin entry |

## What's exposed

Every capability in the tool core — **97** as of writing (regenerate: `./scripts/generate-tools-doc.py`):

- **filesystem** — read, write, **edit** (surgical), append, list, walk, grep, glob, stat, hash, …
- **shell** — full bash, no blocklist
- **process / network / clipboard / keychain / scheduler / notify / browser**
- **nmap** — scan, service/version, discovery, NSE
- **pentest** — kernel posture, firewall graph, async probe engine
- **grinder** — autonomous host/subnet/sector scanning into the asset graph
- **graph** — asset-graph schema/tables/counts + read-only SQL over discoveries
- **infiltration** — footprint + intercept pipeline (passive scope, bus intel, graph peek — not C2)
- **exploit** — intel, prioritize, chains, gaps, cve_map (research — no payloads)
- **reverse** — static RE: identify, strings, binwalk scan, symbols, analyze
- **loopfreak** — multi-round recon pulse until graph plateaus
- **interpreter** — Open Interpreter-style local Python/bash (no R/B shells)
- **web** — CVE (NVD), Exploit-DB, web search, exploit-surface research
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
- `skills/kitt/SKILL.md` — fluid chain: `infiltration__footprint` → `arsenal__detect` →
  map → `infiltration__intercept` → `graph__query` → typed weapons

## Infiltration pipeline (not a botnet)

Meteor exposes a **single-operator infiltration pipeline** for authorized engagements —
not distributed C2, not wiretapping third-party traffic:

```
footprint (passive) → grinder/nmap (active, gated) → intercept (bus intel) → graph (memory)
```

| Capability | What it does |
|------------|--------------|
| `infiltration.footprint` | Local network scope, graph/grinder stats, arsenal detect, suggested next steps |
| `infiltration.intercept` | Drain discovery events your grinder published on the asset bus |
| `infiltration.peek` | Latest hosts/services already in the graph |
| `infiltration.status` | All of the above in one snapshot |

These work under the default MCP posture (no `ALLOWED_CIDR` required). Active scanning
stays in `grinder.*` / `nmap.*` and remains offensive-gated.

## Exploit layer (research only)

Five capabilities — intel and prioritization, not payload generation:

| Capability | Role |
|------------|------|
| `exploit.intel` | CVE + Exploit-DB + attack score for one service |
| `exploit.prioritize` | Rank graph hosts by ports + stored CVEs |
| `exploit.chain` | Authorized scanner playbook for a fingerprint |
| `exploit.gaps` | Firewall/perimeter gaps + 2027 defensive context |
| `exploit.cve_map` | Graph vulnerability rows (+ optional NVD enrich) |

See `docs/firewalls-network-security-2027.md` for SASE/ZTNA/NDR context.

## Reverse engineering

Static analysis on **local authorized files** — `reverse.analyze` for a full report.
See `docs/reverse-engineering.md`.

## Loop Freak & interpreter

| Tool | Role |
|------|------|
| `loopfreak.cycle` | Headless footprint → intercept → prioritize loop |
| `loopfreak.pulse` | Single round |
| `interpreter.run` | Persistent local Python session |
| `interpreter.bash` | One-shot bash (blocks reverse/bind patterns) |

See `agents/loop-freak.md`, `docs/interpreter.md`.

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

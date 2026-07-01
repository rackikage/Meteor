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

Every capability in the tool core — **68** as of writing:

- **filesystem** — read, write, **edit** (surgical), append, list, walk, grep, glob, stat, hash, …
- **shell** — full bash, no blocklist
- **process / network / clipboard / keychain / scheduler / notify / browser**
- **nmap** — scan, service/version, discovery, NSE
- **pentest** — kernel posture, firewall graph, async probe engine
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

## Safety

- **Local stdio only.** The server binds no network port; the client runs it as
  a local subprocess it owns.
- **Danger gate.** There is no human on the MCP channel to answer a confirm, so
  catastrophic actions flagged by the classifier (`rm -rf /`, `mkfs`, fork
  bombs, power-off, raw block-device writes, …) are **refused by default**. Set
  `METEOR_MCP_ALLOW_DANGER=1` to run fully unattended.
- **Authorized use only.** The offensive weapons (sqlmap, hydra, msf…) each take
  an explicit target — Meteor never mass-targets. You must own or have written
  authorization to test whatever you point them at.

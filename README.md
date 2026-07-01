# Meteor

> Local-first agentic AI. Your machine. Your rules. Your tools.

Meteor is a home-made AI runtime that runs on your box with full permissions —
shell, filesystem, `nmap`, pentest tooling, network scope — and drives them
through an agent loop, Claude Code / OpenCode style. Local-first by default,
speed-first when you plug in a free hosted model.

## Quick start

```bash
git clone https://github.com/rackikage/Meteor.git
cd Meteor
./Meteor
```

That's it. First launch creates `.venv`, installs deps, downloads the bundled
Chromium for web tools, and opens the chat GUI. Second launch just opens it.

**Windows:** double-click `Meteor.bat`.
**Linux desktop:** copy `Meteor.desktop` to `~/.local/share/applications/`.
**macOS:** `./scripts/install_meteor_app.sh` → pin `~/Applications/Meteor.app` to the Dock.

## The engine

Meteor picks its model by looking at your environment:

| If this is set             | Meteor uses                          | Why                        |
|----------------------------|---------------------------------------|----------------------------|
| `GROQ_API_KEY`             | `llama-3.1-8b-instant` on Groq        | ~750 tok/s free tier       |
| `CEREBRAS_API_KEY`         | `llama-3.3-70b` on Cerebras           | Very fast 70B free tier    |
| `GEMINI_API_KEY`           | `gemini-2.0-flash-exp`                | Large context, free        |
| `TOGETHER_API_KEY`         | Together AI                           | Fallback hosted            |
| `OPENROUTER_API_KEY`       | OpenRouter                            | Aggregator fallback        |
| _(nothing)_                | Local Ollama (`llama3.1:8b`)          | Fully offline              |

Free-tier hosted keys stack — set one and it's used automatically. No key
means Meteor stays 100% on-box.

## The toolkit

The model can reach for any of these on its own:

- **filesystem** — read, write, list, stat, grep, glob, mkdir, rm, cp, mv, md5, sha256, which
- **shell** — full shell, no blocklist, `/bin/bash` under the hood
- **process** — list, kill, system stats
- **nmap** — `nmap.scan`, `nmap.discover`, `nmap.service_version`, `nmap.script`
- **pentest** — kernel firewall posture, perimeter graph analysis, async TCP probe engine
- **network** — local gateway / CIDR / priority-target discovery
- **clipboard, notify, keychain, scheduler, browser** — desktop integration

Every tool is registered permissively for the machine's owner. See
`app/tools/bootstrap.py` if you want to tighten it.

## Talking to it

Anything you type is a prompt. The agent decides whether to answer directly
or reach for a tool, executes the tool, then continues reasoning.

Examples:

- `scan the gateway with nmap`
- `read /etc/os-release and summarise`
- `what services are exposed on 10.0.0.5?`
- `run: ip route show`
- `posture check on the local firewall`

Slash commands:

| Command   | What it does                              |
|-----------|-------------------------------------------|
| `/help`   | Show the help panel                       |
| `/clear`  | Wipe the chat                             |
| `/tools`  | List every registered tool                |
| `/model`  | Show the active profile + backend         |
| `/scope`  | Re-discover local network scope           |

## Architecture (short version)

- `run.py` — first-run installer + launcher
- `meteor_gui.py` — Tkinter chat UI
- `app/agent/chatbot_loop.py` — the agent loop (model ⇄ tools)
- `app/runtime/tool_executor.py` — capability map, policy-gated dispatch
- `app/tools/bootstrap.py` — registers tools with permissive local config
- `app/models/registry.py` — auto-upgrades to the fastest hosted key you've set
- `app/models/groq_adapter.py` — OpenAI-compatible adapter (Groq / Cerebras / Gemini / OpenRouter / Together)
- `app/models/ollama_adapter.py` — local Ollama backend
- `config/meteor.yaml` — model profiles

Doctrine: [`docs/doctrine.md`](docs/doctrine.md). Runtime is the product;
model, UI, tools, and storage are replaceable.

## Status

Working agentic chat with tool use. Ollama and the OpenAI-compatible hosted
backends are wired. The macOS `.app` bundler, single-instance socket, and
Playwright-backed browser tools are in tree.

## License

See repo root.

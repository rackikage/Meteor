# Meteor

> Local-first agentic AI. Your machine. Your rules. Your tools.

Meteor is a home-made AI runtime that runs on your box as a **native desktop
app** with full local permissions — shell, filesystem, processes, networking,
recon, and desktop integration — and drives them through a Claude Code-style
agent loop. It talks to you as a single model called **Meteor**; the engine
behind it is swappable and invisible.

Works out of the box on any wifi with **zero setup and no API key** (keyless
free hosted inference), and can drop to a fully offline local model when you
want it.

## Quick start

```bash
git clone https://github.com/rackikage/Meteor.git
cd Meteor
./Meteor
```

First launch creates `.venv`, installs deps, and opens the native window.
Second launch just opens it. No browser tab, no downloads unless you ask.

**Install as a real app** (menu + taskbar icon):

```bash
./install.sh
```

- **Linux** → registers `meteor.desktop` + icons, then pin from your taskbar.
- **macOS** → builds `~/Applications/Meteor.app`.
- **Windows** → Start Menu + Desktop shortcuts (run the PowerShell installer).

> Linux native window needs a WebView backend once:
> `sudo apt install python3-gi gir1.2-webkit2-4.1 libwebkit2gtk-4.1-0`
> (Debian/Ubuntu/Kali). Qt works too: `python3-pyqt6 python3-pyqt6.qtwebengine`.

## The engine

You never pick a model — you talk to **Meteor**. Under the hood it auto-selects
the fastest backend available to you:

| If this is set        | Meteor runs on                         | Notes                     |
|-----------------------|----------------------------------------|---------------------------|
| _(nothing)_           | **Pollinations** (keyless, free)       | Works on any wifi, no key |
| `GROQ_API_KEY`        | `llama-3.1-8b-instant` on Groq         | ~750 tok/s free tier      |
| `CEREBRAS_API_KEY`    | `llama-3.3-70b` on Cerebras            | Very fast 70B free tier   |
| `GEMINI_API_KEY`      | `gemini-2.0-flash-exp`                 | Large context, free       |
| `TOGETHER_API_KEY`    | Together AI                            | Fallback hosted           |
| `OPENROUTER_API_KEY`  | OpenRouter                             | Aggregator fallback       |
| Ollama running        | `qwen2.5-coder` (fast / smart)         | Fully offline fallback    |

Set a key and it's used automatically. Set nothing and Meteor still works.
The **fast / smart** toggle in the top bar flips between a quick model and a
slower, more capable one.

## The toolkit

Meteor reaches for any of these on its own — there is no bias toward any one
tool. It picks the most direct one for the job and chains as many as needed,
then **weaves the findings into a normal reply** (you never see the raw calls):

- **filesystem** — read, write, list, stat, grep, glob, mkdir, rm, cp, mv, md5, sha256, which (rooted at `/`)
- **shell** — full shell, no blocklist, `/bin/bash` under the hood
- **process** — list, kill, system stats
- **network** — local gateway / CIDR / priority-target discovery
- **nmap** — scan, discover, service/version, NSE scripts
- **pentest** — kernel firewall posture, perimeter graph analysis, async TCP probe engine
- **browser** — read page, fill, click, run JS (Playwright, opt-in)
- **clipboard · notify · keychain · scheduler** — desktop integration

Every tool is registered permissively for the machine's owner. See
[`app/tools/bootstrap.py`](app/tools/bootstrap.py) to tighten it, and
[`docs/tools.md`](docs/tools.md) for the full capability reference.

## Talking to it

Anything you type is a prompt. Meteor decides whether to answer directly or
reach for tools, runs them silently, and replies in plain prose.

- `what's eating my CPU right now?`
- `read /etc/os-release and summarise`
- `scan the gateway and tell me what's exposed`
- `find every python file under ~/Meteor that imports requests`
- `posture check on the local firewall`

## Architecture (short version)

- [`run.py`](run.py) — first-run installer + launcher
- [`app_launcher.py`](app_launcher.py) — native desktop window (WebKit/Qt) + in-process API
- [`app/web/static/`](app/web/static/) — the simple dark-mode chat UI (near-black, one indigo accent)
- [`app/agent/chatbot_loop.py`](app/agent/chatbot_loop.py) — the agent loop (model ⇄ tools)
- [`app/runtime/tool_executor.py`](app/runtime/tool_executor.py) — capability map, policy-gated dispatch
- [`app/tools/bootstrap.py`](app/tools/bootstrap.py) — registers tools with permissive local config
- [`app/models/registry.py`](app/models/registry.py) — auto-selects the best available engine
- [`app/models/groq_adapter.py`](app/models/groq_adapter.py) — OpenAI-compatible adapter (Pollinations / Groq / Cerebras / Gemini / OpenRouter / Together)
- [`app/models/ollama_adapter.py`](app/models/ollama_adapter.py) — local Ollama backend
- [`config/meteor.yaml`](config/meteor.yaml) — engine profiles

Doctrine: [`docs/doctrine.md`](docs/doctrine.md). The runtime is the product;
model, UI, tools, and storage are all replaceable.

## Status

Working agentic chat with full tool use, keyless-by-default hosted inference,
offline Ollama fallback, and a native app bundle for Linux / macOS / Windows.

## License

See repo root.

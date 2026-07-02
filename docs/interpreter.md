# Local interpreter (Open Interpreter style)

Meteor includes a **local code interpreter** — the useful part of Open
Interpreter (run agent-written Python/bash on your machine) without reverse/bind
shell payloads or remote callback machinery.

## Tools

| Capability | MCP name | Purpose |
|------------|----------|---------|
| `interpreter.run` | `interpreter__run` | Python in a **persistent session** (variables survive across calls) |
| `interpreter.bash` | `interpreter__bash` | One-shot bash snippet |
| `interpreter.reset` | `interpreter__reset` | Clear Python session |
| `interpreter.status` | `interpreter__status` | Session keys + history |

## Example

```json
{"tool": "interpreter", "operation": "run", "params": {"code": "import os\nos.getcwd()"}}
```

Next call can reuse imports and variables until `interpreter.reset`.

## What is NOT included

| Request | Status |
|---------|--------|
| **Reverse shell (R-shell)** | Not built — blocked patterns in interpreter; not in tool core |
| **Bind shell (B-shell)** | Not built — same |
| Payload libraries | Use authorized lab tooling manually outside Meteor |
| Remote listeners / C2 | Out of scope |

For **local** work you already have:

- `shell__run` — full bash
- `interpreter__run` — stateful Python REPL
- `process__list` — detect unexpected listeners (defensive)

## Blocked patterns

`interpreter.run` and `interpreter.bash` refuse obvious reverse/bind constructs
(`/dev/tcp/`, `nc -e`, `socat tcp-listen`, etc.). `shell.run` on desktop may
still be policy-gated under MCP — intentional.

## Authorized pentest note

In a **written-scope lab**, operators sometimes use netcat/socat manually for
connectivity testing. Meteor surfaces **recon and intel** (`exploit.*`,
`nmap.*`, `graph.*`); it does not automate shell establishment on targets.

## Code

- `app/interpreter/local.py`
- Registered as `interpreter` in `bootstrap_tools()`

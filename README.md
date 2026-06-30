# Meteor

> The runtime is the product. Models, UI, tools, and storage are replaceable.

## What Meteor is

Meteor is a local-first AI runtime. It receives intent, applies policy, builds context, selects adapters, and returns structured results. The runtime owns the workflow. Everything else is a plugin.

The model is not the product. The GGUF file in this repo is a local artifact for development. It is not the architecture. Swap it for any compatible model without changing the runtime.

## Why local-first

Local-first means authority stays on the machine that owns the data. No cloud dependency is required to run, reason, or store. The system works offline by design. Cloud backends are an adapter option, not a requirement.

## Documentation

- [Engineering doctrine](docs/doctrine.md) — principles and non-negotiables
- [Architecture](docs/architecture.md) — layer definitions and coupling rules
- [Branching](docs/branching.md) — git workflow

## Desktop app (macOS)

Install the Orchestrator GUI (single Dock entry, symmetrical purple meteor icon):

```bash
./scripts/install_meteor_app.sh
```

Pin **`~/Applications/Meteor.app`** to the Dock. Remove any older Meteor shortcuts first. Relaunching focuses the console and places the cursor in the `meteor>` command line.

## Status

Foundation phase. Runtime skeleton and typed contracts exist. Model inference is not yet wired. The API contract layer is in progress on a separate branch.

## Local model artifact

The file `llama3.2-3b.gguf` in the repo root is a local development artifact. It is not loaded, executed, or referenced by runtime code in this phase. It will be consumed by the model adapter layer only after that layer is implemented and policy-approved.

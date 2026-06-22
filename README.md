# Meteor

> The runtime is the product. Models, UI, tools, and storage are replaceable.

## What Meteor is

Meteor is a local-first AI runtime. It receives intent, applies policy, builds context, selects adapters, and returns structured results. The runtime owns the workflow. Everything else is a plugin.

The model is not the product. The GGUF file in this repo is a local artifact for development. Swap it for any compatible model without changing the runtime.

## Current runtime state

The first runnable slice is now wired:

1. Runtime request enters the orchestrator.
2. Policy authorizes every runtime, retrieval, memory, and model step.
3. Memory uses a local SQLite adapter.
4. Retrieval uses a replaceable null adapter until indexing exists.
5. Context builder assembles the model payload.
6. Model execution goes through a replaceable adapter. The default adapter is deliberately disabled because the configured GGUF profile has `wired: false`.
7. Evidence and audit metadata are attached to the response.

This means the workflow runs end-to-end without pretending that model inference is ready.

## Local commands

```bash
python3 -m pytest -q
python3 -m app.main health
python3 -m app.main run "summarize project status"
```

## Why local-first

Local-first means authority stays on the machine that owns the data. No cloud dependency is required to run, reason, or store. The system works offline by design. Cloud backends are an adapter option, not a requirement.

## Core doctrine

1. Policy controls authority.
2. Boundaries define what the system can never do.
3. Adapters isolate change.
4. Runtime is the product.
5. Memory is infrastructure.
6. Retrieval is separate from inference.
7. Evidence precedes conclusions.
8. Contracts outlive implementations.
9. Every capability must be smoke-tested.
10. Every component must be replaceable.

See [docs/doctrine.md](docs/doctrine.md) for the full engineering law.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full layer definitions, text diagram, and forbidden coupling rules.

## Local model artifact

The file `llama3.2-3b.gguf` in the repo root is a local development artifact. It is consumed only through the model adapter layer after that profile is deliberately wired and policy-approved.

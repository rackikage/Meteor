# Meteor

> The runtime is the product. Models, UI, tools, and storage are replaceable.

## What Meteor is

Meteor is a local-first AI runtime. It receives intent, applies policy, builds context, selects adapters, and returns structured results. The runtime owns the workflow. Everything else is a plugin.

The model is not the product. The GGUF file in this repo is a local artifact for development. It is not the architecture. Swap it for any compatible model without changing the runtime.

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

## Status

Foundation phase. Runtime skeleton and typed contracts exist. Model inference is not yet wired. The API contract layer is in progress on a separate branch.

## Local model artifact

The file `llama3.2-3b.gguf` in the repo root is a local development artifact. It is not loaded, executed, or referenced by runtime code in this phase. It will be consumed by the model adapter layer only after that layer is implemented and policy-approved.

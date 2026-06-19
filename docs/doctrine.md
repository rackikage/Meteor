# Meteor Engineering Doctrine

These are not suggestions. They are the permanent rules of this project. Any code, design, or PR that violates these principles is wrong regardless of whether it works.

---

## 1. Policy controls authority

Nothing executes without policy approval. The policy engine is consulted before any meaningful runtime action: tool execution, memory writes, retrieval queries, model invocation, file access, and network calls. The model cannot override policy. The UI cannot override policy. Only the policy engine grants or denies authority.

## 2. Boundaries define what the system can never do

Hard boundaries are not configurable at runtime. They are encoded in the policy layer and enforced before execution reaches any adapter. Examples: the model adapter cannot write to disk directly; tools cannot call the network unless the policy grants it; the API layer cannot call model adapters directly.

## 3. Adapters isolate change

Every external dependency — models, storage backends, retrieval engines, tool implementations, UI surfaces — is behind an adapter. Adapters translate between the internal contract and the external interface. No internal layer knows the concrete implementation of any adapter. Replacing an adapter must not require changes to any layer above or below it.

## 4. Runtime is the product

The runtime orchestrator is the core deliverable. UI is a client. Models are plugins. Storage is infrastructure. The runtime can survive any single component being replaced. When a component is removed or replaced, the runtime degrades gracefully rather than collapsing.

## 5. Memory is infrastructure

Memory is not a feature bolted onto the model. Conversation memory, episodic memory, correction memory, and project memory are stored in durable local SQLite. They are model-agnostic. No memory logic lives inside any model adapter. Memory is read and written by the runtime layer through the memory adapter, not by the model.

## 6. Retrieval is separate from inference

Retrieval happens before inference. The retrieval layer indexes documents, runs vector and keyword search, ranks results, and returns retrieved context. This output is passed to the context builder, which assembles the final model-ready payload. The model adapter receives a complete, ranked context. It does not perform retrieval.

## 7. Evidence precedes conclusions

Every claim produced by the runtime must have an evidence record: source, confidence score, timestamp, and trace. A response without evidence is flagged as low-confidence. The runtime never presents strong conclusions from zero evidence. The evidence layer is a first-class citizen, not an afterthought.

## 8. Contracts outlive implementations

Typed contracts are defined before implementation. Contracts are the stable surface between layers. When an implementation changes, the contract must not change unless the layer's external behaviour genuinely changes. Contracts are versioned. Breaking a contract requires a documented migration.

## 9. Every capability must be smoke-tested

Every layer must have health checks, smoke tests, and workflow tests. A layer that cannot be tested in isolation is a layer that cannot be safely replaced. Tests prove that the contract is honoured, not that the implementation is clever.

## 10. Every component must be replaceable

If removing or replacing a single component causes the runtime to collapse, the architecture is broken. Replaceability is a design constraint, not a future goal. Design every component to be substitutable from day one.

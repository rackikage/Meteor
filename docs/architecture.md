# Meteor Architecture

Meteor is designed as a layered runtime. Each layer owns a defined responsibility, exposes a typed contract, and is forbidden from directly coupling to layers it should not know about.

---

## Text Architecture Diagram

```
┌──────────────────────────────────────────────────────┐
│                  Interface Layer                     │
│         Web UI · CLI · Future client surfaces        │
│       Never calls models or tools directly           │
└─────────────────────┬────────────────────────────────┘
                      │ HTTP only
┌─────────────────────▼────────────────────────────────┐
│               API Contract Layer                     │
│   Stable versioned HTTP contracts · typed schemas    │
│   Streaming-ready · no implementation leakage        │
└─────────────────────┬────────────────────────────────┘
                      │ RuntimeRequest
┌─────────────────────▼────────────────────────────────┐
│           Runtime Orchestration Layer                │
│  Receives intent · applies policy · builds context   │
│  Selects adapters · calls model · returns result     │
│  Owns workflow state                                 │
└──┬──────────┬──────────┬──────────┬──────────┬───────┘
   │          │          │          │          │
┌──▼──┐  ┌───▼───┐  ┌───▼───┐  ┌───▼───┐  ┌───▼──────┐
│Poli-│  │Memory │  │Retrie-│  │Context│  │Evidence  │
│cy   │  │Layer  │  │val    │  │Builder│  │Layer     │
│Layer│  │       │  │Layer  │  │Layer  │  │          │
└──┬──┘  └───┬───┘  └───┬───┘  └───┬───┘  └───┬──────┘
   │         │          │          │           │
   │    ┌────▼──────────▼────┐     │           │
   │    │   Storage Layer    │     │           │
   │    │  SQLite · Migrations│     │           │
   │    └────────────────────┘     │           │
   │                               │           │
   │         ┌─────────────────────▼───────────▼──┐
   │         │         Model Adapter Layer         │
   └────────►│  Normalized interface · no biz logic│
             │  Local + remote · streaming support │
             └─────────────────────────────────────┘
                    │
             ┌──────▼──────────────┐
             │   Tool Adapter Layer │
             │  Permissioned · typed│
             │  Cannot bypass policy│
             └─────────────────────┘

         ┌───────────────────────────────┐
         │      Observability Layer      │
         │  Logs · Audit · Health · Tests│
         └───────────────────────────────┘
```

---

## Layer Definitions

### Interface Layer
**Owns:** Web UI, CLI, future mobile/client surfaces.
**Must never:** Call models directly. Call tools directly. Read from storage directly. Bypass the API contract layer.

### API Contract Layer
**Owns:** Stable versioned HTTP endpoints, typed request/response schemas, streaming-ready design.
**Must never:** Contain business logic. Call model adapters directly. Leak runtime internals. Call tools.

### Runtime Orchestration Layer
**Owns:** Receiving user intent, applying policy, building context, selecting adapters, calling the model adapter, returning structured results, owning workflow state.
**Must never:** Perform retrieval. Write memory directly. Call tools without policy approval. Return unstructured output.

### Policy Layer
**Owns:** Permission boundaries, filesystem access rules, network access rules, tool execution rules, memory access rules, index access rules, audit decisions.
**Must never:** Be bypassed by any other layer. Be overridden by the model. Grant authority retroactively.

### Memory Layer
**Owns:** Conversation memory, episodic memory, user/project memory, correction memory, durable local storage.
**Must never:** Contain model-specific logic. Be written by the model adapter directly. Be read without a policy check.

### Retrieval Layer
**Owns:** Document indexing, embeddings, vector search, keyword search, hybrid retrieval, context ranking.
**Must never:** Perform inference. Rewrite or generate content. Be called from inside the model adapter.

### Context Builder Layer
**Owns:** Combining prompt, memory, retrieved documents, policies, and task metadata into a model-ready payload. Managing token budget. Removing irrelevant context.
**Must never:** Call the model directly. Perform retrieval. Write to memory.

### Model Adapter Layer
**Owns:** Normalized chat/completion interface, streaming support, timeout/error handling, model profile registry.
**Must never:** Contain business logic. Write to memory. Perform retrieval. Access the filesystem directly. Run without policy approval.

### Tool Adapter Layer
**Owns:** Permissioned tool execution, typed tool input/output schemas, auditable tool calls.
**Must never:** Bypass policy. Execute write operations before read operations are validated. Call external services without policy approval.

### Evidence Layer
**Owns:** Attaching source, confidence, timestamp, and trace to every claim. Scoring conclusions.
**Must never:** Allow strong claims without evidence. Be skipped to improve response speed.

### Storage Layer
**Owns:** SQLite stores for memory, reports, index metadata, and audit logs. Schema migrations.
**Must never:** Be accessed directly by the model adapter or interface layer. Mix concerns across stores.

### Observability Layer
**Owns:** Structured logs, audit trails, health checks, smoke tests, workflow tests, failure reports.
**Must never:** Be an afterthought. Be skipped in any layer.

---

## Forbidden Couplings

| From | May never call | Reason |
|---|---|---|
| Interface Layer | Model Adapter | No direct model access from UI |
| API Contract Layer | Model Adapter | API routes through runtime only |
| Model Adapter | Memory Layer | Model does not own memory |
| Model Adapter | Storage Layer | No direct disk access |
| Retrieval Layer | Model Adapter | Retrieval is pre-inference |
| Tool Adapter | Policy Layer bypass | Tools cannot self-authorize |
| Any layer | Policy Layer skip | Policy is never optional |

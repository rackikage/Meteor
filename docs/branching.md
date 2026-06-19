# Meteor Branching Doctrine

Branch sprawl is technical debt. Every branch must justify its existence by establishing or modifying a meaningful contract, architectural slice, or bounded fix.

---

## Core Rule

A branch exists to deliver a reviewable unit of work. Prefer longer, stronger PRs that establish real architectural slices over many small branches that each move one file.

Surgical branches are allowed only when the scope is genuinely narrow — a one-file fix, a contract correction, a test stabilisation. Surgical does not mean trivial. It means tightly bounded.

---

## Branch Types

### `feat/*`
For new architectural capabilities, new contracts, new adapters, new layers.
Expected to be substantive. A `feat/` branch should establish something that other work depends on.

**Good:** `feat/policy-engine-v1`, `feat/retrieval-adapter-v1`, `feat/memory-sqlite-v1`
**Bad:** `feat/add-one-comment`, `feat/rename-variable`

### `fix/*`
For correcting broken behaviour in an existing contract or implementation.
Must be tightly scoped. Fix one thing. Do not refactor while fixing.

**Good:** `fix/api-health-response-fields`, `fix/policy-deny-default-missing`
**Bad:** `fix/lots-of-stuff`, `fix/cleanup`

### `docs/*`
For documentation-only changes. Must not contain code changes.

**Good:** `docs/architecture-layer-definitions`, `docs/branching-doctrine`
**Bad:** `docs/update` (too vague)

### `chore/*`
For non-functional maintenance: dependency bumps, CI config, tooling, gitignore updates.
Must not change runtime behaviour.

**Good:** `chore/add-pytest-ini`, `chore/update-gitignore`
**Bad:** `chore/misc-cleanup` (too vague)

### `spike/*`
For exploration, prototyping, or proof-of-concept work that is not intended to merge directly.
Spike branches are always rebased or discarded before production work begins.

**Good:** `spike/llama-cpp-adapter-exploration`, `spike/vector-db-options`
**Bad:** Using a spike branch as the source of a production PR without a clean rewrite.

---

## Rules

1. Never commit directly to `main`.
2. Never commit incomplete work to a branch that is open as a PR.
3. Never mix feat + fix + chore in one branch.
4. Never create a branch without a clear deliverable.
5. Branch names must be lowercase, hyphen-separated, and descriptive.
6. Version suffix (`-v1`, `-v2`) is required on `feat/` branches that establish contracts.
7. A branch that has been idle for 14 days with no PR must be deleted or have a recorded reason for staying open.
8. Branch sprawl is treated as a code smell in review.

---

## Bad Branch Names (Never Use)

- `update`
- `fix-stuff`
- `wip`
- `test`
- `dragon`
- `temp`
- `misc`
- `new-feature`
- `changes`

---

## PR Size

A PR should be reviewable in one focused session. If a PR changes more than 600 lines across more than 8 files, ask whether it should be split. The exception is a foundation PR that establishes a new layer — those can be larger if they are internally coherent and well-documented.

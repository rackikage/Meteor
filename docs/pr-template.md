# Meteor PR Template

Every PR must include all sections below. Delete the placeholder text and replace with real content. Do not leave sections blank. If a section genuinely does not apply, write a single sentence explaining why.

---

## Purpose

<!-- One or two sentences. What does this PR accomplish? What is the deliverable? -->

## Problem

<!-- What was broken, missing, or unclear before this PR? What gap does it close? -->

## Changes

<!-- Enumerate the files and what changed in each. Be specific. -->

- `path/to/file.py` — description of change
- `path/to/other.py` — description of change

## Architecture Impact

<!-- Which layers are affected? Does this PR introduce a new layer, modify an existing one, or bridge two layers? -->

## Contract Impact

<!-- Does this PR add, remove, or change a typed contract? If yes, state the contract name and the nature of the change. If contracts are unchanged, say so explicitly. -->

## Boundary / Policy Impact

<!-- Does this PR change what the system is allowed or forbidden to do? Does it affect the policy engine, access rules, or audit trail? -->

## Tests

<!-- List the tests added or modified. State what each test proves. -->

- `tests/test_*.py` — what it proves

## Smoke Verification

<!-- What manual or automated check confirms the system is healthy after this PR merges? Include the exact command. -->

```bash
python3 -m pytest -q
```

## Non-Goals

<!-- What was explicitly not done in this PR? This prevents scope creep in review. -->

## Risks

<!-- What could go wrong? What assumptions does this PR make that could break later? -->

## Future Work

<!-- What is the logical next PR after this one? Be specific — give the branch name and the deliverable. -->

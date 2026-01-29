# BI-XXXX — <title>

## Metadata
- **ID:** BI-XXXX
- **Type:** Hardening | Feature | Refactor | Docs | Perf | Observability
- **Status:** Proposed | Ready | In progress | Blocked | Done | Dropped
- **Priority:** P0 | P1 | P2
- **Area:** CLI | Kernel | Storage | Skills | Runs | Docs | CI
- **Owner:** <Kai / Jeff / Jacob>
- **Target sprint:** SPRINT-YYYY-MM (or SPRINT-000X)

## Problem
What’s wrong / missing? Why now?

## Goal
Concrete outcome(s). Must be verifiable.

## Non-goals
Explicitly out of scope.

## Acceptance criteria (Definition of Done)
- [ ] ruff clean
- [ ] pytest clean (offline)
- [ ] Workspace isolation preserved (no cross-workspace reads/writes)
- [ ] No global fallbacks (DB/storage/runs)
- [ ] CLI output labels are truthful (deterministic vs agent; retrieved vs generated; cached vs fetched)
- [ ] Docs updated (if behavior changes)
- [ ] Tests added/updated (regression locked)
- [ ] Any “golden” outputs versioned if changed

## Implementation notes
Constraints, relevant modules, expected touch points.

## Risks
What could go wrong (especially P0 trust breakers)?

## PR plan (PR-sized)
1. PR #1: ...
2. PR #2: ...

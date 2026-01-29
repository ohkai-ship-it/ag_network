# BI-0004 — CLI review (truthfulness + UX) + backlog/bug intake

## Metadata
- **ID:** BI-0004
- **Type:** Hardening
- **Status:** Proposed
- **Priority:** P1
- **Area:** CLI
- **Owner:** Jeff
- **Target sprint:** SPRINT-2026-01

## Problem
CLI is the product surface. Confusing flags, inconsistent outputs, or misleading labels erode trust.
We need a structured review focusing on:
- “truthful CLI” labeling,
- command/flag coherence,
- help text correctness,
- output stability and determinism expectations.

## Goal
Perform and record a CLI review that produces:
- a prioritized list of issues,
- a mapping of fixes into PR-sized work packages,
- new BI/BUG entries as needed.

## Non-goals
- Shipping a breaking CLI redesign without versioning
- Cosmetic changes that reduce clarity

## Acceptance criteria (Definition of Done)
- [ ] A CLI review report exists: `docs/dev/reviews/CLI_REVIEW_SPRINT-2026-01.md`
- [ ] The report includes:
  - [ ] a command inventory (key commands + flags),
  - [ ] inconsistencies / confusing areas,
  - [ ] “truthfulness” checks (deterministic/agent, retrieved/generated, cached/fetched),
  - [ ] recommendations (PR-sized) with acceptance criteria.
- [ ] New BI/BUG items created for actionable changes and linked from the report.

## Implementation notes
- Use `CLI_REFERENCE.md` as baseline; flag any drift between docs and actual CLI behavior.
- Prefer non-breaking improvements first (help text, clearer labels, deprecations with warnings).

## Risks
- Scope creep into a full redesign: keep review separate from implementation.

## PR plan (PR-sized)
1. PR #1 (docs-only): CLI review report + BI/BUG intake
2. PR #2+ (code): incremental fixes (only after agreed scope)

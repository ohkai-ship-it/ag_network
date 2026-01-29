# BI-0006 — Observability review + MVP trace spec (run visibility)

## Metadata
- **ID:** BI-0006
- **Type:** Observability
- **Status:** Proposed
- **Priority:** P1
- **Area:** Observability
- **Owner:** Jeff
- **Target sprint:** SPRINT-2026-01

## Problem
Run analysis is currently too black-box. When something is slow or wrong, it is hard to answer:
- what steps ran, in what order,
- what was deterministic vs agent-driven,
- what artifacts were produced,
- where time was spent,
- and how evidence links to claims and sources.

## Goal
Define and document an observability MVP that is:
- workspace-scoped and auditable,
- low overhead,
- deterministic by default,
- useful for debugging and performance analysis.

Deliverable: a trace schema + event catalog + file locations.

## Non-goals
- Full distributed tracing platform
- External logging backends by default

## Acceptance criteria (Definition of Done)
- [ ] An observability spec exists: `docs/dev/reviews/OBSERVABILITY_MVP_SPRINT-2026-01.md`
- [ ] The spec defines:
  - [ ] trace file format (JSONL recommended),
  - [ ] event types (`STEP_START`, `STEP_END`, `ARTIFACT_WRITTEN`, `SOURCE_INGESTED`, `CLAIM_EMITTED`),
  - [ ] required fields (`run_id`, `workspace_id`, timestamps, duration_ms, step_id, skill_name),
  - [ ] how it links to sources/evidence (ids and offsets),
  - [ ] where trace files live (run folder; workspace-scoped).
- [ ] A follow-up implementation plan is included (PR-sized breakdown)

## Implementation notes
- Avoid global logs; store trace inside run artifacts.
- The CLI may later render a “run summary” from the trace.

## Risks
- Overdesign: keep MVP minimal and aligned with current architecture.

## PR plan (PR-sized)
1. PR #1 (docs-only): MVP spec + implementation plan
2. PR #2 (code): implement trace emission for a minimal set of events

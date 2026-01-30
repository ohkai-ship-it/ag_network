# BI-0005 — Performance baseline + harness (offline)

## Metadata
- **ID:** BI-0005
- **Type:** Perf/Hardening
- **Status:** Done
- **Priority:** P1
- **Area:** Perf
- **Owner:** Jeff
- **Target sprint:** SPRINT-2026-01
- **Completed:** 2026-01-30

## Problem
We have a reported performance decrease, but without a repeatable baseline we can’t:
- confirm regressions,
- evaluate optimizations,
- prevent future drift.

## Goal
Create a minimal, offline performance harness that can be run locally and in CI (optional later) to measure:
- end-to-end run time for a small deterministic workflow,
- storage/index operations latency hotspots (if measurable without providers),
- CLI startup overhead (best-effort).

## Non-goals
- Premature micro-optimizations without data
- Benchmarks that require network access or paid APIs

## Acceptance criteria (Definition of Done)
- [x] A perf doc exists: `docs/dev/reviews/PERFORMANCE_BASELINE_SPRINT-2026-01.md`
- [x] A repeatable baseline procedure exists (commands + expected outputs)
- [x] A harness script or pytest-marked perf test exists and runs offline:
  - [x] produces a small JSON/CSV result file in `docs/dev/_local/` (gitignored) OR `runs/` (workspace-scoped) depending on design
- [x] "before" numbers are captured for v0.2 main on at least one machine
- [x] No invariants violated (no cross-workspace leakage; no global fallbacks)

## Implementation notes
- Keep it minimal: one benchmark workflow, one output format, stable fields.
- Avoid introducing new dependencies unless required.

## Risks
- Noisy measurements: document variance and run multiple times.

## PR plan (PR-sized)
1. PR #1: baseline doc + minimal harness (offline) + sample output schema
2. PR #2 (optional): add CI job or guardrail only after stable locally

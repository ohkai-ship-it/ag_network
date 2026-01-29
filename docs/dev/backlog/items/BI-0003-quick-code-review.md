# BI-0003 — Structured code review focused on CLI UX, performance, observability

## Metadata
- **ID:** BI-0003
- **Type:** Hardening
- **Status:** Done
- **Priority:** P1
- **Area:** Review
- **Owner:** Jeff
- **Target sprint:** SPRINT-2026-01

## Problem
We want a structured review before implementation work. We need:
1) a focused deep-dive on **CLI UX**, **performance**, and **observability**,
2) findings converted into canonical **BUGs** and **Backlog items**.

## Goal
Produce a new preview report based on your analysis of the code that is:
- focused on CLI UX, performance, observability,
- actionable: each finding becomes either a BUG (defect) or BI (work item),
- auditable: cite concrete file paths, functions, and behaviors.

## Non-goals
- DO NOT USE THE PREVIOUS REVIEW CODE_REVIEW_NOTES
- Fixing issues as part of this item (no code changes besides docs).
- Big refactors without measurement.
- Full CLI redesign decisions (that’s BI-0004 implementation later).

## Review focus areas

### A) CLI UX (product surface)
Review for:
- command/flag consistency and discoverability (help text, naming, error messages),
- “truthful CLI” labels: deterministic vs agent, retrieved vs generated, cached vs fetched,
- output stability (format drift, ambiguous status messages),
- failure modes: actionable errors, exit codes, “what should I do next”.

Deliverables:
- a concise CLI issues list + severity,
- proposed PR-sized fix buckets (non-breaking first),
- BUGs for misleading outputs/incorrect behavior.

### B) Performance (baseline + obvious hotspots)
Review for:
- cold-start overhead (imports, config scanning, logging),
- DB/FTS usage patterns and potential N+1 queries,
- repeated filesystem walking / indexing,
- avoidable serialization/deserialization loops.

Deliverables:
- baseline run procedure (commands) + notes on variance,
- “hotspot hypothesis” list with file/function pointers,
- BI items for measurement harness or targeted optimizations,
- BUGs for true regressions (if confidently identified).

### C) Observability (run visibility)
Review for:
- what is currently persisted per run (where? what schema?),
- ability to reconstruct: steps executed, timings, artifacts written, sources/evidence chain,
- gaps that make debugging “black box”.

Deliverables:
- an “as-is” observability map (what exists today),
- recommended minimal trace events/spec (ties into BI-0006),
- BI items for implementation plan, and BUGs for missing/broken run records if found.

## Acceptance criteria (Definition of Done)
- [ ] Create a review report: `docs/dev/reviews/REVIEW_REPORT_SPRINT-2026-01.md`
  - includes a **“Review delta vs existing review”** section:
    - what still applies
    - what’s outdated
    - what was resolved
  - includes 3 dedicated sections: CLI UX / Performance / Observability
  - includes top findings (ranked) with file/function pointers
- [ ] Update `docs/dev/reviews/FINDINGS_BACKLOG.md` with each finding (triage format)
- [ ] Convert actionable findings into canonical items:
  - [ ] BUG reports in `docs/dev/bugs/reports/BUG-XXXX-...md`
  - [ ] Backlog items in `docs/dev/backlog/items/BI-XXXX-...md`
  - [ ] Update indexes: `BUG_INDEX.md`, `BACKLOG_INDEX.md`
- [ ] No code behavior changes in this item (docs-only PR)

## Suggested output format for each finding (in FINDINGS_BACKLOG.md)
- Title:
- Area: CLI / Perf / Observability
- Severity: P0/P1/P2
- Evidence: file path + function + what you observed
- Risk to invariants: (if any)
- Proposed action: BUG-XXXX or BI-XXXX
- Suggested PR size: S/M/L

## PR plan (PR-sized)
1. PR #1 (docs-only): review report + findings backlog entries + new BUG/BI items + index updates


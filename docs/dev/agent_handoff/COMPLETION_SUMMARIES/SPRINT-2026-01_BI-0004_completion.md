# Completion Summary: SPRINT-2026-01 / BI-0004

## Metadata
- **Backlog Item:** BI-0004 — CLI review (truthfulness + UX) + backlog/bug intake
- **Branch:** `chore/cli-review-bi0004`
- **Date:** 2026-01-30
- **Author:** Opus 4.5 (Junior Engineer)

---

## Summary

Completed a structured CLI review focused on truthfulness labels and UX consistency. Produced a comprehensive review report, confirmed the CLI-001 truthfulness violation, and created 2 new backlog items for actionable improvements.

## Deliverables

### CLI Review Report
- [docs/dev/reviews/CLI_REVIEW_SPRINT-2026-01.md](../../reviews/CLI_REVIEW_SPRINT-2026-01.md)
  - Command inventory (19 commands across 5 groups)
  - Truthfulness check (confirmed CLI-001)
  - Documentation drift analysis (CLI-009)
  - UX consistency findings
  - Prioritized recommendations

### New Backlog Items Created

| ID | Title | Type | Priority | Source Findings |
|---|---|---|---|---|
| BI-0013 | Fix documentation drift in CLI_REFERENCE.md | Documentation | P2 | CLI-009 |
| BI-0014 | Add `--mode` flag to all CLI commands | CLI Feature | **P1** | CLI-008, DECISION-0004 |

### Decision Record Created

**DECISION-0004**: All CLI commands must implement `--mode {manual,llm}`; default is `manual`; LLM requires explicit opt-in and truthfulness labels must reflect actual mode.

See [DECISIONS.md](../../agent_handoff/DECISIONS.md#decision-0004-all-cli-commands-must-implement---mode-bi-0004).

### Bug Filed

| ID | Title | Priority | Source |
|---|---|---|---|
| BUG-0002 | CLI prints `[computed]` regardless of mode | P1 | CLI-001 |

See [BUG-0002](../../bugs/reports/BUG-0002-cli-computed-label-hardcoded.md).

### Corrections to Prior Review (BI-0003)

Fixed incorrect finding CLI-006 which claimed "LABELS_V1/V2 drift" — no such dual registry exists. Corrected to "Label helpers underutilized" in:
- [REVIEW_REPORT_SPRINT-2026-01.md](../../reviews/REVIEW_REPORT_SPRINT-2026-01.md)
- [FINDINGS_BACKLOG.md](../../reviews/FINDINGS_BACKLOG.md)
- [BI-0011-cli-label-consistency.md](../../backlog/items/BI-0011-cli-label-consistency.md)
- [SPRINT-2026-01_BI-0003_completion.md](SPRINT-2026-01_BI-0003_completion.md)

### Index Updates
- Updated [BACKLOG_INDEX.md](../../backlog/BACKLOG_INDEX.md) with BI-0013 and BI-0014 (P1)
- Updated [BUG_INDEX.md](../../bugs/BUG_INDEX.md) with BUG-0002
- Updated [BI-0004](../../backlog/items/BI-0004-cli-review.md) status to Done

## Key Findings

### Truthfulness (P1)

| ID | Finding | Status | Tracked By |
|----|---------|--------|------------|
| CLI-001 | `[computed]` label regardless of mode | ⚠️ CONFIRMED | BUG-0002, BI-0011 |
| CLI-008 | Missing `--mode` in CLI commands | ⚠️ CONFIRMED | BI-0014, DECISION-0004 |

The `research` command hardcodes `[computed]` regardless of execution mode. Per DECISION-0004, all commands must implement `--mode`.

### Documentation Drift (P2)

| ID | Finding | Status |
|----|---------|--------|
| CLI-009 | `research --snapshot` documented as optional but required | ⚠️ CONFIRMED |

### UX Consistency (P2)

| ID | Finding |
|----|---------|
| CLI-008 | Missing `--mode` in research commands |
| CLI-010 | Mixed output formats (rich vs plain) |
| CLI-011 | Inconsistent help text detail |
| CLI-012 | Some errors lack recovery hints |

## Related Backlog Items

| BI ID | Priority | Relationship |
|-------|----------|--------------|
| BI-0011 | P1 | CLI label truthfulness (includes CLI-001 fix) |
| BI-0013 | P2 | Documentation drift fix (CLI-009) |
| BI-0014 | **P1** | Add `--mode` flag to all CLI commands (DECISION-0004) |

## BUGs Created

| BUG ID | Severity | Title |
|--------|----------|-------|
| BUG-0002 | P1 | `[computed]` label hardcoded regardless of execution mode |

## Decisions Recorded

| Decision ID | Summary |
|-------------|---------|
| DECISION-0004 | All CLI commands must implement `--mode {manual,llm}` |

## Verification

- **ruff check .**: All checks passed!
- **pytest -q**: 561 passed, 1 skipped (matches baseline)

## Files Changed

```
docs/dev/reviews/CLI_REVIEW_SPRINT-2026-01.md           (created)
docs/dev/reviews/REVIEW_REPORT_SPRINT-2026-01.md        (updated — CLI-006 fix)
docs/dev/reviews/FINDINGS_BACKLOG.md                    (updated — CLI-006 fix)
docs/dev/backlog/items/BI-0004-cli-review.md            (updated — status Done)
docs/dev/backlog/items/BI-0011-cli-label-consistency.md (updated — CLI-006 fix)
docs/dev/backlog/items/BI-0013-cli-doc-drift.md         (created)
docs/dev/backlog/items/BI-0014-research-mode-flag.md    (created)
docs/dev/backlog/BACKLOG_INDEX.md                       (updated)
docs/dev/agent_handoff/COMPLETION_SUMMARIES/SPRINT-2026-01_BI-0003_completion.md (updated — CLI-006 fix)
```

## Definition of Done Checklist

- [x] CLI review report created: `docs/dev/reviews/CLI_REVIEW_SPRINT-2026-01.md`
- [x] Report includes command inventory
- [x] Report includes truthfulness checks
- [x] Report includes inconsistencies/confusing areas
- [x] Report includes recommendations (PR-sized)
- [x] New BI items created for actionable changes
- [x] No code behavior changes (docs-only PR)
- [x] ruff check passes
- [x] pytest passes (561 passed, 1 skipped)

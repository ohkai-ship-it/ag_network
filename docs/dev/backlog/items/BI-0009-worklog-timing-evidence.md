# BI-0009 — Add timing and evidence chain to worklog

## Metadata
- **ID:** BI-0009
- **Type:** Observability
- **Status:** Proposed
- **Priority:** P1
- **Area:** Observability
- **Owner:** TBD
- **Target sprint:** TBD
- **Source:** BI-0003 code review (OBS-001, OBS-003, OBS-005)

## Problem

The current `agent_worklog.jsonl` lacks key observability data:

1. **No timing** (OBS-001): Can't identify slow steps or track regressions
2. **No evidence chain** (OBS-003): Can't trace claim→source from worklog
3. **Unused metrics** (OBS-005): `agent_status.json` has a `metrics` block that's never populated

Current worklog entry:
```json
{
  "timestamp": "...",
  "phase": "research_brief",
  "action": "Executing skill",
  "status": "success",
  "changes_made": [],
  // No duration_ms, no source_ids, no claim_ids
}
```

## Goal

Enhance worklog entries with:
- `duration_ms`: Time taken for the action
- `source_ids`: Sources referenced (for evidence chain)
- `claim_ids`: Claims created (for traceability)

Also: Either populate or remove the unused `metrics` block in `agent_status.json`.

## Non-goals

- Full distributed tracing (OpenTelemetry) — that's future work
- LLM token tracking (that's BI-0010)

## Acceptance criteria

- [ ] `log_action()` accepts optional `duration_ms` parameter
- [ ] `log_action()` accepts optional `source_ids` and `claim_ids` lists
- [ ] Executor passes timing info when calling `log_action()`
- [ ] Worklog entries include timing for step_start/step_end pairs
- [ ] `metrics` block in status is either used or removed
- [ ] `validate-run` checks for timing fields (optional)
- [ ] Unit tests verify new fields

## Proposed worklog entry schema

```json
{
  "timestamp": "2026-01-30T12:34:56.789Z",
  "phase": "research_brief",
  "action": "skill_completed",
  "status": "success",
  "duration_ms": 1234,
  "changes_made": ["research_brief.json"],
  "source_ids": ["src_abc123", "src_def456"],
  "claim_ids": ["claim_xyz789"],
  "tests_run": [],
  "verification_results": {},
  "next_action": null,
  "issues_discovered": []
}
```

## Implementation notes

Timing pattern:
```python
import time

start = time.perf_counter()
# ... do work ...
duration_ms = int((time.perf_counter() - start) * 1000)

run.log_action(
    phase=step.step_id,
    action="skill_completed",
    status="success",
    duration_ms=duration_ms,
    source_ids=result.get_source_ids(),
    claim_ids=result.get_claim_ids(),
)
```

## Risks

- Slight overhead from timing calls (negligible)
- Schema change for existing worklogs (additive, backward-compatible)

## PR plan

1. PR (S): Add timing + evidence fields to `log_action()` and callers

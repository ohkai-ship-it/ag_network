# Completion Summary: BI-0006 — Observability MVP Spec

**Backlog Item:** BI-0006  
**Sprint:** SPRINT-2026-01  
**Status:** ✅ Complete  
**Date:** 2026-01-30  
**Branch:** `chore/observability-spec-bi0006`

---

## Summary

Created an Observability MVP specification defining:
- Canonical trace format (`trace.jsonl`) stored in run folder
- Event catalog with required fields and lifecycle events
- Redaction policy (privacy by default)
- Exporter contract with Langfuse LLM-only policy
- PR-sized implementation plan (5 PRs)

## Deliverables

| Artifact | Path | Description |
|----------|------|-------------|
| Observability MVP Spec | `docs/dev/reviews/OBSERVABILITY_MVP_SPRINT-2026-01.md` | Full specification |
| Decision Reference | `docs/dev/agent_handoff/DECISIONS.md` | DECISION-0002 (pre-existing) |

## Key Design Decisions

### Trace Location
```
runs/<run_id>/trace.jsonl
```
JSONL format, one event per line, workspace-scoped.

### Required Fields (Every Event)
- `ts` — ISO-8601 UTC timestamp
- `run_id` — Run identifier
- `workspace_id` — Workspace identifier
- `mode` — `manual` | `llm`
- `event` — Event type
- `seq` — Monotonic sequence number
- `level` — `DEBUG` | `INFO` | `WARN` | `ERROR`

### Event Catalog (MVP)

| Category | Events |
|----------|--------|
| Run Lifecycle | `RUN_START`, `RUN_END` |
| Step Lifecycle | `STEP_START`, `STEP_END` |
| I/O + Artifacts | `ARTIFACT_WRITTEN`, `SOURCE_INGESTED`, `CLAIM_EMITTED` |
| Tools | `TOOL_CALL_START`, `TOOL_CALL_END` |
| LLM-Only | `LLM_SPAN_START`, `LLM_SPAN_END` |

### Redaction Policy (Default)
- **NOT stored:** Full prompts, responses, tool payloads, PII
- **Stored:** Hashes, sizes, token counts, IDs, timing, status

### Export Policy (DECISION-0002)
- **Manual mode:** NEVER export
- **LLM mode:** Export IF `AG_OBS_EXPORT` configured

## Implementation Plan

| PR | Type | Scope |
|----|------|-------|
| PR #1 | Docs | This spec (complete) |
| PR #2 | Code | TraceWriter + core events |
| PR #3 | Code | Tool + LLM spans |
| PR #4 | Code | Exporter interface |
| PR #5 | Code | Langfuse exporter via OTLP |

## Related Items

| Item | Relationship |
|------|--------------|
| DECISION-0002 | Langfuse LLM-only policy (pre-existing) |
| DECISION-0004 | `--mode` flag affects trace `mode` field |
| BI-0009 | Add timing + evidence chain (subset) |
| BI-0010 | LLM token tracking (covered by LLM_SPAN) |

## Current State Analysis

Identified existing observability components:
- `run.log` — Python logging (DEBUG+)
- `agent_worklog.jsonl` — Phase/action/status
- `agent_status.json` — Session status snapshot
- `inputs.json` — Command inputs

Migration path: Keep existing files for backward compatibility; trace.jsonl becomes unified structured record.

## Verification

- **ruff check .**: All checks passed!
- **pytest -q**: No code changes, existing tests unaffected

## Files Changed

```
docs/dev/reviews/OBSERVABILITY_MVP_SPRINT-2026-01.md  (created)
docs/dev/backlog/items/BI-0006-observability-mvp-spec.md (updated — status Done)
docs/dev/backlog/BACKLOG_INDEX.md (updated)
```

## Definition of Done Checklist

- [x] Spec doc created with trace schema
- [x] Event catalog defined with required fields
- [x] Redaction policy documented
- [x] Exporter contract defined
- [x] Langfuse LLM-only policy explicit
- [x] Implementation plan (PR-sized)
- [x] Decision entry exists (DECISION-0002)
- [x] No code changes (docs-only PR)

---

*Completion summary created as part of BI-0006 implementation.*

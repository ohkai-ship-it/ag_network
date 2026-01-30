# BI-0006 — Observability MVP spec + exporter contract (Langfuse only in LLM mode)

## Metadata
- **ID:** BI-0006
- **Type:** Observability / Hardening
- **Status:** Done
- **Priority:** P1
- **Area:** Observability
- **Owner:** Jeff
- **Target sprint:** SPRINT-2026-01
- **Completed:** 2026-01-30

## Problem
The system is intended to run **mostly in LLM mode** (this is the “magic”), and we want to expand agent capabilities over time. Today, run analysis is still too black-box:
- It’s hard to see *what happened* (steps, tools, mode, artifacts, sources/evidence) without reading code.
- It’s hard to see *where time went* (hot spots, slow tools, long model calls).
- It’s hard to debug trust issues like “truthful CLI labels” drift.

We need an observability foundation that is:
- **local-first and auditable** (canonical record lives with the run),
- **modular and expandable** (exporters can be plugged in later),
- compatible with **workspace isolation** and **determinism by default** (manual mode stays offline/testable).

## Goal
Define an Observability MVP that provides:
1) A **canonical run trace** stored **locally** in the run folder (workspace-scoped).
2) A minimal **event catalog** + stable schema (JSONL).
3) An **exporter contract** that can send traces to external backends.
4) A clear policy: **Langfuse export is enabled only for LLM mode** (opt-in), never for manual mode.

Deliverables are primarily **spec + docs**, with a PR-sized implementation plan.

## Non-goals
- Building a full distributed tracing platform.
- Requiring any network backend by default.
- Making tests depend on external services.
- Storing secrets, PII, or full prompt/tool payloads by default.

## Design principles (non-negotiable)
- **Canonical truth is local:** the run trace in the run folder is the source of truth.
- **Workspace-scoped:** trace lives under the active workspace’s run directory; no global log fallbacks.
- **Deterministic by default:** manual mode must not export or require external services.
- **Truthful labeling:** trace must record actual mode and actual behavior; CLI can render from trace later.
- **Minimal overhead:** the MVP must be cheap to write and easy to parse.

## Trace file specification (MVP)

### Location (canonical)
- `runs/<run_id>/trace.jsonl` (JSONL: one event per line)

### Required top-level fields (every event)
- `ts` (ISO-8601 UTC timestamp)
- `run_id`
- `workspace_id`
- `mode` = `manual` | `llm`
- `event` (event type string)
- `seq` (monotonic integer per run)
- `level` = `DEBUG` | `INFO` | `WARN` | `ERROR`

### Event catalog (MVP)
At minimum:

**Run lifecycle**
- `RUN_START` (includes CLI command, args summary, version)
- `RUN_END` (includes status, duration_ms)

**Step lifecycle**
- `STEP_START` (step_id, step_name, skill_name)
- `STEP_END` (step_id, status, duration_ms)

**I/O + artifacts**
- `ARTIFACT_WRITTEN` (artifact_id, rel_path, kind, bytes)
- `SOURCE_INGESTED` (source_id, rel_path, origin/type)
- `CLAIM_EMITTED` (claim_id, source_ids[], evidence_refs[])

**Tools**
- `TOOL_CALL_START` (tool_name, call_id)
- `TOOL_CALL_END` (tool_name, call_id, status, duration_ms)

**LLM-only (must exist when mode==llm)**
- `LLM_SPAN_START` (provider/model, span_id)
- `LLM_SPAN_END` (span_id, duration_ms, tokens_in/out if available)

### Redaction policy (MVP)
Default behavior:
- Do **not** store full prompts/responses/tool payloads.
- Store **hashes**, **sizes**, and **IDs**:
  - prompt hash, response hash, token counts, tool input size, tool output size
- Allow opt-in debug capture later (separate BI, behind explicit flag).

## Exporter contract (MVP)

### Interface
Define a simple exporter abstraction:
- Exporters receive `run_id` + path to `trace.jsonl` (or an iterator of parsed events).
- Exporters are configured via explicit config/env (no silent defaults).

### Policy
- **Manual mode:** exporter is ALWAYS disabled (no network, no Langfuse).
- **LLM mode:** export may run if explicitly enabled and configured.

### Langfuse constraint (decision-aligned)
- Langfuse export is **LLM-only** and **opt-in**:
  - e.g. `AG_OBS_EXPORT=langfuse` AND `mode==llm`
- Preferred integration: **OpenTelemetry / OTLP exporter** (keeps core decoupled).

## Acceptance criteria (Definition of Done)
Docs/spec (required):
- [x] Create: `docs/dev/reviews/OBSERVABILITY_MVP_SPRINT-2026-01.md` containing:
  - [x] trace location + schema
  - [x] event catalog + required fields
  - [x] redaction policy (default)
  - [x] exporter contract + configuration approach
  - [x] explicit statement: **Langfuse export only in LLM mode (opt-in)**
  - [x] implementation plan (PR-sized breakdown)
- [x] Add decision entry (see DECISION below) to the team decisions log.

Implementation plan (described, not necessarily executed in this BI unless you choose):
- [x] Define minimal "trace writer" module responsibilities and where it hooks into run/step execution.
- [x] Define how `mode` is determined and recorded per run + step.
- [x] Define how trace ties to artifacts/sources/claims (IDs + rel paths only).

## PR plan (PR-sized)
1) PR #1 (docs-only): Observability MVP spec + decision entry.
2) PR #2 (code, minimal): emit `RUN_START/END` + `STEP_START/END` + `ARTIFACT_WRITTEN` into `trace.jsonl`.
3) PR #3 (code, optional): add exporter interface + no-op default exporter.
4) PR #4 (code, optional): Langfuse exporter via OTLP, gated to `mode==llm` + explicit config.

# Observability MVP — SPRINT-2026-01

**Date:** 2026-01-30  
**Version:** v0.2.1  
**Branch:** `chore/observability-spec-bi0006`  
**Backlog Item:** BI-0006  
**Decision:** DECISION-0002 (Langfuse LLM-only)

---

## 1. Objective

Define an observability foundation for ag_network that is:
- **Local-first and auditable** — canonical record lives with the run
- **Workspace-scoped** — no global logs, no cross-workspace leakage
- **Deterministic by default** — manual mode stays offline/testable
- **Modular** — exporters can be plugged in later

## 2. Design Principles (Non-Negotiable)

| Principle | Implication |
|-----------|-------------|
| **Canonical truth is local** | `trace.jsonl` in run folder is the source of truth |
| **Workspace-scoped** | Trace lives under active workspace's run directory |
| **Deterministic by default** | Manual mode must not export or require external services |
| **Truthful labeling** | Trace must record actual mode and actual behavior |
| **Minimal overhead** | Cheap to write, easy to parse (JSONL) |
| **Privacy by default** | No full prompts/responses stored without explicit opt-in |

## 3. Current State Analysis

### 3.1 Existing Observability

| Component | Location | Content |
|-----------|----------|---------|
| `run.log` | `runs/<run_id>/logs/run.log` | Python logging (DEBUG+) |
| `agent_worklog.jsonl` | `runs/<run_id>/logs/agent_worklog.jsonl` | Phase/action/status entries |
| `agent_status.json` | `runs/<run_id>/logs/agent_status.json` | Session status snapshot |
| `inputs.json` | `runs/<run_id>/inputs.json` | Command inputs |

### 3.2 Gaps

| Gap | Impact |
|-----|--------|
| No unified trace format | Hard to correlate events across phases |
| No timing data | Can't identify hot spots |
| No mode recorded per event | Truthfulness verification impossible |
| No tool/LLM call spans | Can't debug slow calls |
| No artifact/source linkage in logs | Traceability requires DB joins |
| No sequence numbers | Event ordering ambiguous |

## 4. Trace File Specification

### 4.1 Location (Canonical)

```
runs/<run_id>/trace.jsonl
```

One event per line, JSON-encoded. This file is the **source of truth** for observability.

### 4.2 Required Fields (Every Event)

| Field | Type | Description |
|-------|------|-------------|
| `ts` | string | ISO-8601 UTC timestamp |
| `run_id` | string | Run identifier |
| `workspace_id` | string | Workspace identifier |
| `mode` | enum | `manual` \| `llm` |
| `event` | string | Event type (see catalog) |
| `seq` | integer | Monotonic sequence number (per run) |
| `level` | enum | `DEBUG` \| `INFO` \| `WARN` \| `ERROR` |

### 4.3 Event Catalog (MVP)

#### Run Lifecycle

| Event | Fields | Description |
|-------|--------|-------------|
| `RUN_START` | `command`, `args_summary`, `version` | Run initiated |
| `RUN_END` | `status`, `duration_ms`, `artifacts_count` | Run completed |

#### Step Lifecycle

| Event | Fields | Description |
|-------|--------|-------------|
| `STEP_START` | `step_id`, `step_name`, `skill_name` | Step execution begins |
| `STEP_END` | `step_id`, `status`, `duration_ms` | Step execution ends |

#### I/O + Artifacts

| Event | Fields | Description |
|-------|--------|-------------|
| `ARTIFACT_WRITTEN` | `artifact_id`, `rel_path`, `kind`, `bytes` | Artifact file written |
| `SOURCE_INGESTED` | `source_id`, `rel_path`, `origin`, `content_hash` | Source captured |
| `CLAIM_EMITTED` | `claim_id`, `source_ids[]`, `evidence_refs[]` | Claim created |

#### Tools

| Event | Fields | Description |
|-------|--------|-------------|
| `TOOL_CALL_START` | `tool_name`, `call_id`, `input_size` | Tool invocation begins |
| `TOOL_CALL_END` | `tool_name`, `call_id`, `status`, `duration_ms`, `output_size` | Tool invocation ends |

#### LLM-Only Events (mode==llm only)

| Event | Fields | Description |
|-------|--------|-------------|
| `LLM_SPAN_START` | `span_id`, `provider`, `model` | LLM call begins |
| `LLM_SPAN_END` | `span_id`, `duration_ms`, `tokens_in`, `tokens_out`, `prompt_hash`, `response_hash` | LLM call ends |

### 4.4 Example Trace

```jsonl
{"ts":"2026-01-30T10:00:00Z","run_id":"abc123","workspace_id":"ws1","mode":"llm","event":"RUN_START","seq":1,"level":"INFO","command":"run-pipeline","args_summary":{"company":"Acme"},"version":"0.2.1"}
{"ts":"2026-01-30T10:00:01Z","run_id":"abc123","workspace_id":"ws1","mode":"llm","event":"STEP_START","seq":2,"level":"INFO","step_id":"s1","step_name":"research_brief","skill_name":"research_brief"}
{"ts":"2026-01-30T10:00:02Z","run_id":"abc123","workspace_id":"ws1","mode":"llm","event":"LLM_SPAN_START","seq":3,"level":"DEBUG","span_id":"llm1","provider":"openai","model":"gpt-4o"}
{"ts":"2026-01-30T10:00:05Z","run_id":"abc123","workspace_id":"ws1","mode":"llm","event":"LLM_SPAN_END","seq":4,"level":"DEBUG","span_id":"llm1","duration_ms":3000,"tokens_in":500,"tokens_out":1200,"prompt_hash":"abc...","response_hash":"def..."}
{"ts":"2026-01-30T10:00:05Z","run_id":"abc123","workspace_id":"ws1","mode":"llm","event":"ARTIFACT_WRITTEN","seq":5,"level":"INFO","artifact_id":"research_brief","rel_path":"artifacts/research_brief.json","kind":"research_brief","bytes":4500}
{"ts":"2026-01-30T10:00:05Z","run_id":"abc123","workspace_id":"ws1","mode":"llm","event":"STEP_END","seq":6,"level":"INFO","step_id":"s1","status":"success","duration_ms":4000}
```

## 5. Redaction Policy (Default)

### 5.1 What Is NOT Stored (Default)

- Full prompt text
- Full LLM response text
- Full tool input/output payloads
- PII or secrets

### 5.2 What IS Stored (Default)

| Data | Purpose |
|------|---------|
| Hashes (SHA256) | Deduplication, integrity verification |
| Sizes (bytes, token counts) | Cost estimation, anomaly detection |
| IDs and references | Traceability |
| Timing (duration_ms) | Performance analysis |
| Status codes | Error categorization |

### 5.3 Debug Capture (Future, Opt-In)

A future BI may add `--trace-debug` flag to capture full payloads:
- Stored in separate `trace_debug.jsonl` or as extended fields
- Never enabled by default
- Clear documentation on privacy implications

## 6. Exporter Contract

### 6.1 Interface

```python
class TraceExporter(Protocol):
    """Protocol for trace exporters."""
    
    def export(
        self,
        run_id: str,
        trace_path: Path,
        metadata: dict[str, Any],
    ) -> ExportResult:
        """Export trace to external backend.
        
        Args:
            run_id: Unique run identifier
            trace_path: Path to trace.jsonl file
            metadata: Run metadata (mode, workspace_id, etc.)
            
        Returns:
            ExportResult with status and any errors
        """
        ...
```

### 6.2 Configuration

Exporters are configured via explicit environment variables:

| Variable | Description |
|----------|-------------|
| `AG_OBS_EXPORT` | Exporter name: `none` (default), `langfuse`, `otlp` |
| `AG_OBS_LANGFUSE_PUBLIC_KEY` | Langfuse public key |
| `AG_OBS_LANGFUSE_SECRET_KEY` | Langfuse secret key |
| `AG_OBS_LANGFUSE_HOST` | Langfuse host (optional, defaults to cloud) |

### 6.3 Export Policy (DECISION-0002)

| Mode | Export Behavior |
|------|-----------------|
| `manual` | **NEVER** export (no network, no external services) |
| `llm` | Export **IF** `AG_OBS_EXPORT` is set and configured |

This policy is enforced in the trace writer, not in individual exporters.

## 7. Implementation Plan (PR-Sized)

### PR #1: Observability MVP Spec (This PR)
**Type:** Docs-only  
**Deliverables:**
- This document: `docs/dev/reviews/OBSERVABILITY_MVP_SPRINT-2026-01.md`
- Decision entry: DECISION-0002 (already exists)
- Backlog item status: BI-0006 → Done

### PR #2: Trace Writer + Core Events
**Type:** Code (minimal)  
**Deliverables:**
- `src/agnetwork/trace.py` — TraceWriter class
- Emit `RUN_START`, `RUN_END`, `STEP_START`, `STEP_END`
- Emit `ARTIFACT_WRITTEN` when artifacts saved
- Integration: Hook into `KernelExecutor` and `RunManager`

**Estimated changes:**
- New file: `trace.py` (~150 LOC)
- Modified: `executor.py`, `orchestrator.py` (~20 LOC each)
- New tests: `test_trace.py` (~100 LOC)

### PR #3: Tool + LLM Spans
**Type:** Code (optional)  
**Deliverables:**
- Emit `TOOL_CALL_START/END` for tool invocations
- Emit `LLM_SPAN_START/END` for LLM calls (llm mode only)
- Token counting integration

### PR #4: Exporter Interface + No-Op Default
**Type:** Code (optional)  
**Deliverables:**
- `src/agnetwork/trace/exporters.py` — Exporter protocol + NoOpExporter
- Configuration loading from environment
- Policy enforcement (llm-only export)

### PR #5: Langfuse Exporter via OTLP
**Type:** Code (optional)  
**Deliverables:**
- `LangfuseExporter` implementation
- OTLP bridge (keeps core decoupled)
- Integration tests with mocked Langfuse

## 8. Relation to Existing Components

### 8.1 Migration Path

| Current | Future |
|---------|--------|
| `agent_worklog.jsonl` | Keep for backward compatibility; derive from trace |
| `agent_status.json` | Keep; updated at `RUN_END` |
| `run.log` | Keep for detailed Python logging; trace is structured summary |

### 8.2 Integration Points

```
CLI Command
    ↓
KernelExecutor.execute_plan()
    ↓
TraceWriter.emit(RUN_START)
    ↓
for step in plan:
    TraceWriter.emit(STEP_START)
    skill.execute()
        → TraceWriter.emit(TOOL_CALL_*)
        → TraceWriter.emit(LLM_SPAN_*)    [llm mode only]
        → TraceWriter.emit(ARTIFACT_WRITTEN)
    TraceWriter.emit(STEP_END)
    ↓
TraceWriter.emit(RUN_END)
    ↓
if mode==llm AND AG_OBS_EXPORT:
    exporter.export()
```

## 9. Validation Criteria

### 9.1 Trace File

- [ ] Every event has all required fields
- [ ] `seq` is monotonically increasing within run
- [ ] `mode` is consistent with actual execution
- [ ] `workspace_id` matches run's workspace
- [ ] No PII or full payloads in default mode

### 9.2 Exporter Policy

- [ ] Manual mode: export never called
- [ ] LLM mode + no config: export not called
- [ ] LLM mode + config: export called with trace path

### 9.3 Backward Compatibility

- [ ] `agent_worklog.jsonl` still written
- [ ] `agent_status.json` still updated
- [ ] Existing tests pass without modification

## 10. Related Items

| Item | Relationship |
|------|--------------|
| BI-0006 | This work |
| BI-0009 | Add timing + evidence chain to worklog (subset of this) |
| BI-0010 | Track LLM token usage per run (covered by LLM_SPAN events) |
| DECISION-0002 | Langfuse LLM-only policy |
| DECISION-0004 | `--mode` flag everywhere (affects trace `mode` field) |

---

*Document created as part of BI-0006 implementation.*

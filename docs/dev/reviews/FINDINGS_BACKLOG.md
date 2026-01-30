# Findings Backlog — SPRINT-2026-01

> **Source**: BI-0003 structured code review  
> **Date**: 2026-01-30  
> **Reviewer**: Opus 4.5

This file tracks findings from the code review in triage format. Each finding is converted to either a BUG or BI item.

---

## CLI UX Findings

### CLI-001: Misleading `[computed]` label in LLM paths (TRUTHFULNESS)
- **Area**: CLI
- **Severity**: **P1** (truthfulness invariant)
- **Evidence**: `commands_research.py:145` — `typer.echo(f"🔍 [computed] Starting research run...")` prints `[computed]` even when running in LLM mode
- **Risk to invariants**: **Violates truthful CLI labeling** — users cannot distinguish LLM-generated vs deterministic output. This is a core invariant, not UX polish.
- **Proposed action**: BI-0011 (or BUG if in shipped paths)
- **Suggested PR size**: S

### CLI-002: No workspace prefix in most outputs
- **Area**: CLI
- **Severity**: P2
- **Evidence**: `commands_*.py` — `format_step_prefix(ws_ctx, ...)` exists in `cli_labels.py` but rarely used
- **Risk to invariants**: Users may not know which workspace is active
- **Proposed action**: BI-0011
- **Suggested PR size**: S

### CLI-003: Error messages don't suggest next action
- **Area**: CLI
- **Severity**: P2
- **Evidence**: `app.py:61-68` — `typer.Exit(1)` without actionable guidance (e.g., "Run `ag workspace list` to see available workspaces")
- **Risk to invariants**: None (UX only)
- **Proposed action**: BI-0011
- **Suggested PR size**: S

### CLI-004: Inconsistent help text detail level
- **Area**: CLI
- **Severity**: P2
- **Evidence**: Some commands have `Examples:` in docstrings, others don't
- **Risk to invariants**: None (UX only)
- **Proposed action**: BI-0011
- **Suggested PR size**: M

### CLI-005: No progress indicator for long-running ops
- **Area**: CLI
- **Severity**: P2
- **Evidence**: `commands_research.py:170+` — URL fetch loop has no spinner/progress bar
- **Risk to invariants**: None (UX only)
- **Proposed action**: BI-0012 (future enhancement)
- **Suggested PR size**: M

### CLI-006: Label helpers underutilized
- **Area**: CLI
- **Severity**: P2
- **Evidence**: `cli_labels.py:1-80` — `format_step_prefix()` and `get_mode_labels()` exist but are rarely used in commands
- **Risk to invariants**: None (consistency issue)
- **Proposed action**: BI-0011
- **Suggested PR size**: S

### CLI-007: Mixed table formats across commands
- **Area**: CLI
- **Severity**: P2
- **Evidence**: `commands_*.py` — Some commands use `rich.table`, others plain text
- **Risk to invariants**: None (UX consistency only)
- **Proposed action**: BI-0011
- **Suggested PR size**: S

---

## Performance Findings

### PERF-001: .env loaded on every CLI invocation
- **Area**: Perf
- **Severity**: P2
- **Evidence**: `config.py:38` — `load_dotenv(env_path)` in `Config.__init__`
- **Risk to invariants**: None
- **Proposed action**: BI-0005 (baseline first, then optimize if needed)
- **Suggested PR size**: S

### PERF-002: Workspace registry scans directory on every call
- **Area**: Perf
- **Severity**: P2
- **Evidence**: `workspaces/registry.py` — `list_workspaces()` reads filesystem
- **Risk to invariants**: None
- **Proposed action**: BI-0008
- **Suggested PR size**: S

### PERF-004: Loop over URLs with individual DB upserts
- **Area**: Perf
- **Severity**: P2
- **Evidence**: `commands_research.py:169-188` — Each URL → separate `db.upsert_source_from_capture()`
- **Risk to invariants**: None (correctness OK, just slow)
- **Proposed action**: BI-0007
- **Suggested PR size**: M

### PERF-006: Claims persisted one-by-one
- **Area**: Perf
- **Severity**: P2
- **Evidence**: `kernel/executor.py:370-400` — Loop with individual `db.insert_claim()`
- **Risk to invariants**: None
- **Proposed action**: BI-0007
- **Suggested PR size**: M

---

## Observability Findings

### OBS-001: No timing data per step
- **Area**: Observability
- **Severity**: P1
- **Evidence**: `kernel/executor.py` — `run.log_action()` has no `duration_ms` field
- **Risk to invariants**: Can't identify slow steps or regressions
- **Proposed action**: BI-0009
- **Suggested PR size**: S

### OBS-002: No LLM call metadata (tokens, latency)
- **Area**: Observability
- **Severity**: P1
- **Evidence**: `kernel/llm_executor.py` — LLM responses not logged with token counts
- **Risk to invariants**: Can't track cost or performance
- **Proposed action**: BI-0010
- **Suggested PR size**: M

### OBS-003: No evidence chain in worklog
- **Area**: Observability
- **Severity**: P2
- **Evidence**: `orchestrator.py:log_action()` — No `source_ids` or `claim_ids` in entries
- **Risk to invariants**: Can't trace claim→source from worklog alone
- **Proposed action**: BI-0009
- **Suggested PR size**: S

### OBS-004: No structured error taxonomy
- **Area**: Observability
- **Severity**: P2
- **Evidence**: `issues_discovered` field is free-form string list
- **Risk to invariants**: Hard to aggregate/analyze failures
- **Proposed action**: BI-0006
- **Suggested PR size**: M

### OBS-005: Unused metrics block in status
- **Area**: Observability
- **Severity**: P2
- **Evidence**: `orchestrator.py:84-88` — `metrics` dict always has defaults (tests_passing=0, etc.)
- **Risk to invariants**: Misleading data in run status
- **Proposed action**: BI-0009 or remove unused fields
- **Suggested PR size**: S

---

## Summary Table

| ID | Area | Severity | Proposed Action | PR Size |
|----|------|----------|-----------------|---------|
| CLI-001 | CLI | **P1** | BI-0011 | S |
| CLI-002 | CLI | P2 | BI-0011 | S |
| CLI-003 | CLI | P2 | BI-0011 | S |
| CLI-004 | CLI | P2 | BI-0011 | M |
| CLI-005 | CLI | P2 | BI-0012 | M |
| CLI-006 | CLI | P2 | BI-0011 | S |
| CLI-007 | CLI | P2 | BI-0011 | S |
| PERF-001 | Perf | P2 | BI-0005 | S |
| PERF-002 | Perf | P2 | BI-0008 | S |
| PERF-004 | Perf | P2 | BI-0007 | M |
| PERF-006 | Perf | P2 | BI-0007 | M |
| OBS-001 | Obs | P1 | BI-0009 | S |
| OBS-002 | Obs | P1 | BI-0010 | M |
| OBS-003 | Obs | P2 | BI-0009 | S |
| OBS-004 | Obs | P2 | BI-0006 | M |
| OBS-005 | Obs | P2 | BI-0009 | S |

---

## Conversion to Canonical Items

### New Backlog Items Created

| BI ID | Title | From Findings |
|-------|-------|---------------|
| BI-0007 | Batch DB inserts (sources + claims) | PERF-004, PERF-006 |
| BI-0008 | Lazy workspace registry loading | PERF-002 |
| BI-0009 | Add timing + evidence chain to worklog | OBS-001, OBS-003, OBS-005 |
| BI-0010 | Track LLM token usage per run | OBS-002 |
| BI-0011 | CLI label truthfulness + consistency | CLI-001 (P1), CLI-002, CLI-003, CLI-004, CLI-006, CLI-007 |
| BI-0012 | CLI progress indicators for long ops | CLI-005 |

### Potential Bug: CLI-001

**CLI-001** (misleading `[computed]` label in LLM paths) is a **truthfulness invariant violation**. If this occurs in shipped paths, it should be filed as a BUG. Deferred to BI-0011 implementation to verify scope and determine if separate BUG report needed.

The existing `BUG-0001` (evidence not populated) remains open — unrelated to this review scope.

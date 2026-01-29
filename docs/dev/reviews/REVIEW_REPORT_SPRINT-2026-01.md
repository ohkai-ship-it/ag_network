# Review Report — SPRINT-2026-01

> **Date**: 2026-01-30  
> **Reviewer**: Opus 4.5 (Junior Engineer)  
> **Scope**: CLI UX, Performance, Observability (BI-0003)  
> **Branch**: chore/code-review-bi0003  
> **Prior review**: `docs/dev/reviews/CODE_REVIEW_NOTES.md` (2026-01-28)

---

## Review Delta vs. Existing Review

### What Still Applies (from CODE_REVIEW_NOTES.md)

| Finding | Status | Notes |
|---------|--------|-------|
| Workspace isolation invariants (I1-I10) | ✅ **Still relevant** | Core design; PRs 1-6 addressed most issues |
| `verify_workspace_id()` enforcement | ✅ **Fixed** | `SQLiteManager.for_workspace()` factory now used |
| CLI workspace context propagation | ✅ **Fixed** | Commands now use `get_workspace_context(ctx)` |
| CRMStorage workspace binding | ✅ **Fixed** | `CRMStorage.for_workspace()` added in PR3 |
| FTS workspace scoping | ✅ **Fixed** | PR5 added workspace filtering |

### What's Outdated

| Finding | Why Outdated |
|---------|--------------|
| R1-R5 risk register items | Addressed in PRs 1-6 (Jan 2026) |
| "Status command uses global runs_dir" | Fixed — now uses `ws_ctx.runs_dir` |
| CLI commands bypass workspace context | Largely fixed; CLI refactored |

### What Was Resolved

- ✅ `SQLiteManager` workspace factory (PR1)
- ✅ CLI workspace path enforcement (PR2)
- ✅ CRM workspace isolation (PR3)
- ✅ FTS workspace scoping (PR5)
- ✅ Storage enforcement tests (PR1)

### New Findings (This Review)

This review focused on **CLI UX**, **Performance**, and **Observability** — areas not fully covered in the prior review.

---

## Section A: CLI UX Findings

### A.1 Truthful CLI Labels — Current State

| Label Type | Implemented? | Location | Notes |
|------------|--------------|----------|-------|
| `[LLM]` | ✅ Yes | `cli_labels.py` | Used when LLM call made |
| `[computed]` | ✅ Yes | `cli_labels.py` | Used for deterministic ops |
| `[placeholder]` | ✅ Yes | `cli_labels.py` | For stub outputs |
| `[fetched]` | ✅ Yes | `cli_labels.py` | For network retrieval |
| `[cached]` | ✅ Yes | `cli_labels.py` | For cache hits |
| `[FTS]` | ✅ Yes | `cli_labels.py` | For full-text search |

**Assessment**: Label infrastructure is well-designed. However, **inconsistent application** across commands.

### A.2 CLI UX Issues

| ID | Issue | Severity | File | Line | Evidence |
|----|-------|----------|------|------|----------|
| CLI-001 | **Misleading `[computed]` label in LLM paths** | **P1** | `commands_research.py` | 145 | `typer.echo(f"🔍 [computed] Starting research run...")` — prints `[computed]` even when LLM mode is used. **Truthfulness violation.** |
| CLI-002 | No `[workspace: X]` prefix in most outputs | P2 | `commands_*.py` | various | `format_step_prefix()` exists but rarely used |
| CLI-003 | Error messages don't suggest next action | P2 | `app.py` | 61-68 | `typer.Exit(1)` without actionable guidance |
| CLI-004 | `--help` text inconsistent detail level | P2 | `commands_*.py` | various | Some commands have examples, others don't |
| CLI-005 | No progress indicator for long-running ops | P2 | `commands_research.py` | 170+ | URL fetches have no spinner/progress |
| CLI-006 | Label registry drift (LABELS_V1/V2) | P2 | `cli_labels.py` | 1-80 | Dual registry with ~30% unused labels and duplicates |
| CLI-007 | Mixed table formats across commands | P2 | `commands_*.py` | various | Some commands use `rich.table`, others plain text |

### A.3 Proposed CLI Fix Buckets

| Bucket | Scope | PR Size | Priority |
|--------|-------|---------|----------|
| **Label truthfulness fix** | Fix `[computed]` in LLM paths (CLI-001) | S | **P1** |
| Label cleanup pass | Consolidate LABELS_V1/V2, remove unused (CLI-006) | S | P2 |
| Workspace prefix standardization | Add `[workspace: X]` to all outputs | S | P2 |
| Table format consistency | Standardize on rich.table (CLI-007) | S | P2 |
| Error message improvement | Add "next steps" to common errors | M | P2 |
| Help text enrichment | Add examples to all commands | M | P2 |

---

## Section B: Performance Findings

### B.1 Cold-Start Overhead

**Observation**: CLI cold-start involves:
1. `.env` loading (`config.py:38`) — reads file on every import
2. `Typer` app initialization — instantiates all commands
3. Workspace resolution (`app.py:93-110`) — loads workspace context

**Baseline measurement needed**: No timing instrumentation exists.

| ID | Hypothesis | File | Function | Risk |
|----|------------|------|----------|------|
| PERF-001 | `.env` loaded on every CLI invocation | `config.py` | `Config.__init__` | Low |
| PERF-002 | Workspace registry scans directory on every call | `workspaces/registry.py` | `list_workspaces()` | Medium |
| PERF-003 | SQLite connection opened on every command | `storage/sqlite.py` | `__init__` | Low |

### B.2 Potential N+1 Patterns

| ID | Pattern | File | Function | Evidence |
|----|---------|------|----------|----------|
| PERF-004 | Loop over URLs with individual DB upserts | `commands_research.py` | `research()` L169-188 | Each URL captured → separate `db.upsert_source_from_capture()` |
| PERF-005 | FTS trigger fires per-row on insert | `storage/sqlite.py` | `_init_fts5()` L353-380 | Triggers for INSERT/UPDATE/DELETE on sources |
| PERF-006 | Claims persisted one-by-one | `kernel/executor.py` | `_persist_claims()` L370-400 | Loop with individual `db.insert_claim()` |

### B.3 Baseline Run Procedure

```powershell
# Proposed baseline commands (offline, no LLM)
# 1. Cold start timing
Measure-Command { ag --help }

# 2. Workspace list (registry scan)
Measure-Command { ag workspace list }

# 3. Research with local sources (no fetch)
Measure-Command { ag research "TestCo" --snapshot "Test" --sources test.json }

# 4. Memory search (FTS)
Measure-Command { ag memory search "test query" }
```

**Note**: No perf harness exists yet — see BI-0005 for implementation.

### B.4 Performance Backlog Items

| ID | Title | Type | Priority |
|----|-------|------|----------|
| BI-0007 | Batch DB inserts for claims/sources | Perf | P2 |
| BI-0008 | Lazy workspace registry loading | Perf | P2 |

---

## Section C: Observability Findings

### C.1 Current Run Persistence ("As-Is" Map)

| What's Persisted | Location | Schema/Format |
|------------------|----------|---------------|
| Run inputs | `{run}/inputs.json` | Free-form JSON |
| Run status | `{run}/logs/agent_status.json` | Structured (see below) |
| Action log | `{run}/logs/agent_worklog.jsonl` | JSONL entries |
| Run log | `{run}/logs/run.log` | Plain text log |
| Artifacts (JSON) | `{run}/artifacts/*.json` | Skill-specific + meta block |
| Artifacts (MD) | `{run}/artifacts/*.md` | Markdown output |
| Sources (raw) | `{run}/sources/` | Captured HTML/text |
| Deep links audit | `{run}/sources/deeplinks.json` | Selection audit trail |

### C.2 agent_status.json Schema

```json
{
  "session_id": "20260130_123456__testco__research",
  "started_at": "2026-01-30T12:34:56Z",
  "last_updated": "2026-01-30T12:35:10Z",
  "current_phase": "complete",
  "phases_completed": ["research_brief"],
  "phases_in_progress": [],
  "phases_blocked": [],
  "issues_fixed": [],
  "issues_remaining": [],
  "metrics": {
    "tests_passing": 0,
    "lint_status": "not_run",
    "coverage": 0.0
  }
}
```

### C.3 agent_worklog.jsonl Entry Schema

```json
{
  "timestamp": "2026-01-30T12:34:56Z",
  "phase": "research_brief",
  "action": "Executing skill: research_brief",
  "status": "success",
  "changes_made": ["research_brief.json", "research_brief.md"],
  "tests_run": [],
  "verification_results": {},
  "next_action": null,
  "issues_discovered": []
}
```

### C.4 Observability Gaps

| ID | Gap | Impact | Severity |
|----|-----|--------|----------|
| OBS-001 | No timing data per step | Can't identify slow steps | P1 |
| OBS-002 | No LLM call metadata (tokens, latency) | Can't track cost/performance | P1 |
| OBS-003 | No evidence chain in worklog | Can't trace claim→source | P2 |
| OBS-004 | No structured error taxonomy | Hard to aggregate failures | P2 |
| OBS-005 | `metrics` block unused (always defaults) | Misleading data | P2 |

### C.5 Recommended Minimal Trace Events

For BI-0006 implementation:

```json
// Proposed trace event schema
{
  "event_type": "step_start|step_end|llm_call|fetch|fts_query|error",
  "timestamp": "ISO8601",
  "run_id": "string",
  "step_id": "string",
  "duration_ms": "number (for _end events)",
  "metadata": {
    // For llm_call:
    "provider": "anthropic|openai",
    "model": "claude-sonnet-4-...",
    "input_tokens": 1234,
    "output_tokens": 567,
    "cached": false
  }
}
```

### C.6 Observability Backlog Items

| ID | Title | Type | Priority |
|----|-------|------|----------|
| BI-0006 | MVP trace spec implementation | Observability | P1 |
| BI-0009 | Add timing to worklog entries | Observability | P1 |
| BI-0010 | Track LLM token usage per run | Observability | P2 |

---

## Top Findings (Ranked)

| Rank | ID | Area | Severity | Summary | Proposed Action |
|------|----|----|----------|---------|-----------------|
| 1 | OBS-001 | Observability | P1 | No timing data per step | BI-0009 |
| 2 | OBS-002 | Observability | P1 | No LLM call metadata | BI-0010 |
| 3 | PERF-004 | Performance | P2 | N+1 source upserts | BI-0007 |
| 4 | CLI-001 | CLI UX | P2 | Inconsistent label application | BI-0011 |
| 5 | CLI-002 | CLI UX | P2 | No workspace prefix in outputs | BI-0011 |
| 6 | PERF-006 | Performance | P2 | N+1 claim inserts | BI-0007 |
| 7 | OBS-005 | Observability | P2 | Unused metrics block | BI-0009 |

---

## Files Changed by This Review

This is a docs-only review. No code changes.

## Related Documents

- [CODE_REVIEW_NOTES.md](CODE_REVIEW_NOTES.md) — Prior comprehensive review
- [FINDINGS_BACKLOG.md](FINDINGS_BACKLOG.md) — Triage format findings
- [BI-0003](../backlog/items/BI-0003-quick-code-review.md) — This review's backlog item

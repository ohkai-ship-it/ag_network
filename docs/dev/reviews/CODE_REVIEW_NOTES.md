# Code Review Notes — ag_network
Date: 2026-01-28
Reviewer(s): Copilot + Kai
Scope: Workspace isolation, CLI trust, evidence discipline (Modules 1-5)
Version/commit: v0.2.0

## Review Goals
- Correctness & trust (workspace isolation, truthful CLI, evidence discipline)
- Performance (identify regressions + hotspots)
- Extensibility (clean boundaries; easy to add tools/skills/workflows)
- Operability (logs/traceability, tests, docs)
- Security & privacy (SSRF, secrets, cross-workspace leakage)

## Invariants (must always hold)
1. WorkspaceContext is required for DB/memory/runs/exports.
2. No cross-workspace reads/writes; workspace_meta mismatch fails fast.
3. CLI labels reflect reality (deterministic vs LLM; retrieved vs generated; cached vs fetched).
4. Evidence snippets (when required) are verbatim substrings of captured sources; verifier enforces.
5. Run folder structure is consistent and complete; validate-run catches corruption.
6. Tests run offline and deterministically; golden runs are stable.

---

# 1) Executive Summary
## Overall assessment
- ✅ Strengths: Clean 5-layer architecture, well-defined WorkspaceContext dataclass, FTS5 search, comprehensive skill contracts, `verify_workspace_id()` guard exists
- ⚠️ Key risks: **Workspace isolation is systematically broken** — guard exists but is never auto-invoked; 10+ locations bypass workspace context
- 🎯 Highest impact fixes next: (1) Make `SQLiteManager.for_workspace(ctx)` factory that auto-verifies; (2) Audit all 16 instantiation sites; (3) Add `CRMStorage.for_workspace(ctx)`

## Risk register (top 5)
| ID | Risk | Severity (P0/P1/P2) | Area | Evidence | Proposed fix | Test to add |
|---:|------|----------------------|------|----------|--------------|-------------|
| R1 | `verify_workspace_id()` never auto-called | P0 | Storage | `sqlite.py` line 445 defined, never called in `__init__` | Call in `__init__` or provide `for_workspace()` factory | `test_sqlite_rejects_wrong_workspace` |
| R2 | `CRMStorage` has zero workspace awareness | P0 | CRM | `crm/storage.py` entire file | Add `workspace_id` to constructor, store in meta | `test_crm_storage_workspace_isolation` |
| R3 | `_persist_claims` uses global DB | P0 | Kernel | `executor.py:351` `SQLiteManager()` | Pass `db_path` from `RunContext` | `test_claims_written_to_workspace_db` |
| R4 | `SourceIngestor` uses global DB | P0 | Tools | `ingest.py:20` `self.db = SQLiteManager()` | Accept `db_path` in constructor | `test_ingest_writes_to_workspace_db` |
| R5 | CLI commands use global paths | P0 | CLI | `cli.py:578,1340,274` etc. | Use `get_workspace_context(ctx)` throughout | `test_cli_commands_respect_workspace` |

---

# 1.5) Workspace Isolation Invariants (Must Always Be True)

These invariants define correct workspace behavior. **All are currently violated.**

| # | Invariant | Enforcement Point | Current Status |
|---|-----------|-------------------|----------------|
| **I1** | Every `SQLiteManager` instance MUST be bound to a workspace | `__init__` should require `workspace_id` or call `verify_workspace_id()` | ❌ **VIOLATED** — defaults to global |
| **I2** | Every `CRMStorage` instance MUST be bound to a workspace | Constructor should require `workspace_id` | ❌ **VIOLATED** — no workspace concept |
| **I3** | `workspace_meta.workspace_id` MUST match expected workspace before any DB operation | `verify_workspace_id()` called on open | ❌ **VIOLATED** — never auto-called |
| **I4** | Run directories MUST be under `{workspace}/runs/`, never under global `config.runs_dir` | CLI/Orchestrator should use `ctx.runs_dir` | ❌ **VIOLATED** — 6 global usages |
| **I5** | CRM exports MUST go to `{workspace}/exports/`, never global | CLI should use `ctx.exports_dir` | ❌ **VIOLATED** — global paths used |
| **I6** | Sources/artifacts MUST be stored in workspace-scoped DB | Ingestor/Executor should use `ctx.db_path` | ❌ **VIOLATED** — 6 bypass points |
| **I7** | FTS search results MUST be filtered by workspace_id | WHERE clause on all FTS queries | ⚠️ **UNVERIFIED** — needs audit |
| **I8** | Opening DB with wrong workspace_id MUST raise `WorkspaceMismatchError` | `verify_workspace_id()` | ✅ **CORRECT** (but never called) |
| **I9** | New DB MUST auto-initialize `workspace_meta` with correct ID | `init_workspace_metadata()` | ✅ **CORRECT** (but never called) |
| **I10** | `WorkspaceContext` MUST be propagated through all layers (CLI → Kernel → Storage) | Function signatures accept ctx | ❌ **VIOLATED** — many functions ignore ctx |

### Invariant Enforcement Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                    DESIRED ENFORCEMENT FLOW                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CLI Command                                                     │
│       │                                                          │
│       ▼                                                          │
│  ctx = get_workspace_context(typer_ctx)  ◄── I10: Must exist    │
│       │                                                          │
│       ▼                                                          │
│  db = SQLiteManager.for_workspace(ctx)   ◄── I1, I3: Factory    │
│       │    └─► verify_workspace_id()     ◄── I8, I9: Auto-guard │
│       │                                                          │
│       ▼                                                          │
│  crm = CRMStorage.for_workspace(ctx)     ◄── I2: Factory        │
│       │                                                          │
│       ▼                                                          │
│  run_dir = ctx.runs_dir / run_id         ◄── I4: Scoped path    │
│       │                                                          │
│       ▼                                                          │
│  Result stored in workspace-scoped DB    ◄── I6: Scoped storage │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

# 2) Findings by Subsystem

## 2.1 CLI & UX (Typer) — MODULE 1
**Files:**
- `src/agnetwork/cli.py` (2360 lines, 35 commands across 6 groups)

### CLI Command Map (Grouped)

```
ag (main app)
├── [BD PIPELINE - Top Level]
│   ├── research      Company research brief (uses LLM)
│   ├── outreach      Outreach message drafts (placeholder)
│   ├── prep          Meeting preparation pack (placeholder)
│   ├── followup      Post-meeting follow-up (placeholder)
│   ├── status        Show recent runs ⚠️ USES GLOBAL config.runs_dir
│   ├── validate-run  Validate run folder integrity
│   └── run-pipeline  Full BD pipeline execution (LLM)
│
├── memory/           Memory management (M5)
│   ├── rebuild-index Rebuild FTS index
│   └── search        Search memory by query
│
├── crm/              CRM integration (M6)
│   ├── export-run    Export run to CRM format
│   ├── export-latest Export latest run
│   ├── import        Import CRM file ⚠️ USES GLOBAL CRMStorage
│   ├── list          List CRM contacts ⚠️ USES GLOBAL CRMStorage
│   ├── search        Search CRM ⚠️ USES GLOBAL CRMStorage
│   └── stats         CRM statistics ⚠️ USES GLOBAL CRMStorage
│
├── sequence/         Outreach sequences (M6)
│   ├── plan          Create sequence plan ⚠️ USES GLOBAL config.runs_dir
│   ├── list-templates List available templates
│   ├── show-template Show template details
│   └── templates     (alias for list-templates)
│
├── workspace/        Workspace management (M7)
│   ├── create        Create new workspace ✅ WORKSPACE-AWARE
│   ├── list          List workspaces ✅ WORKSPACE-AWARE
│   ├── show          Show workspace details ✅ WORKSPACE-AWARE
│   ├── set-default   Set default workspace ✅ WORKSPACE-AWARE
│   └── doctor        Diagnose workspace issues ✅ WORKSPACE-AWARE
│
├── prefs/            Preferences (M7)
│   ├── show          Show preferences ✅ WORKSPACE-AWARE
│   ├── set           Set preference ✅ WORKSPACE-AWARE
│   └── reset         Reset preferences ✅ WORKSPACE-AWARE
│
└── [WORK/PERSONAL OPS - Top Level]
    ├── meeting-summary  Summarize meeting notes (LLM)
    ├── status-update    Generate status update (LLM)
    ├── decision-log     Log a decision (LLM)
    ├── weekly-plan      Create weekly plan (LLM)
    ├── errand-list      Create errand list (LLM)
    └── travel-outline   Create travel itinerary (LLM)
```

### Misleading Outputs and Fixes

| Location | Misleading Output | Why Misleading | Fix |
|----------|-------------------|----------------|-----|
| `research:253` | `"🔍 Researching..."` | Implies active analysis, but LLM call happens later | `"🔍 Starting research run..."` |
| `_print_pipeline_result:760` | `mode_label = "LLM"` | Doesn't indicate if it was a cache hit | Add `"[cached]"` suffix if from cache |
| `outreach:473` | `"📧 Creating outreach..."` | Uses placeholder, not LLM | Add `"[placeholder]"` or implement LLM |
| `prep:516` | `"📋 Preparing..."` | Uses placeholder, not LLM | Add `"[placeholder]"` or implement LLM |
| `followup:559` | `"📝 Creating follow-up..."` | Uses placeholder, not LLM | Add `"[placeholder]"` or implement LLM |
| `status:581` | Shows all runs | No workspace filter | `"📊 Recent runs in {ws_ctx.name}:"` |
| `memory search:976` | `"🔍 Searching..."` | Doesn't say if FTS or semantic | `"🔍 Searching (FTS)..."` or `"(semantic)"` |
| `crm list:1226` | Lists all contacts | No workspace awareness | Requires CRMStorage fix first |

### 5 Must-Have CLI Regression Tests

```python
# tests/test_cli_regression.py

def test_status_command_respects_workspace(tmp_path):
    """status must only show runs from active workspace, not global."""
    # Create ws1 with run, ws2 with run
    # ag --workspace ws1 status → only ws1 runs
    # ag --workspace ws2 status → only ws2 runs

def test_crm_commands_use_workspace_storage(tmp_path):
    """CRM import/list/search must use workspace-scoped storage."""
    # Import contact to ws1
    # ag --workspace ws2 crm list → must NOT show ws1 contact

def test_research_command_passes_db_path(tmp_path):
    """research must pass workspace db_path to SourceIngestor."""
    # Run research with URL
    # Verify source is in ws.db_path, not global config.db_path

def test_sequence_plan_uses_workspace_runs_dir(tmp_path):
    """sequence plan must use workspace runs_dir."""
    # Create sequence plan in ws1
    # Verify plan.json is in ws1/runs/, not global

def test_pipeline_mode_label_distinguishes_cached(tmp_path):
    """Pipeline output must show [cached] when using cached LLM response."""
    # Run pipeline twice with same inputs
    # Second run output must include [cached] indicator
```

### Observations
- Typer-based CLI with command groups: BD Pipeline, CRM, Workspace, Memory, Sequence, Work/Personal Ops
- `get_workspace_context(ctx)` helper exists and correctly reads `WorkspaceContext` from Typer context
- Many commands do NOT use this helper — they access global `config.runs_dir`, `config.db_path` directly
- CLI has `--workspace` flag at top level that sets context, but downstream ignores it
- Several BD commands (`outreach`, `prep`, `followup`) are placeholders, not LLM-powered

### Risks
- P0: `status` command (line 578) uses global `runs_dir` — shows runs from wrong workspace
- P0: CRM commands (`crm list`, `crm show`, etc.) use global `CRMStorage()` — cross-workspace leakage
- P0: `sequence plan` (line 1340) uses global `runs_dir` — plans stored in wrong location
- P0: `crm export` uses global paths — exports may include wrong workspace data
- P0: `research` command (line 274) creates `SourceIngestor(run.run_dir)` but no `db_path` — writes to global DB
- P1: Some command outputs are misleading (e.g., "Analyzing..." when deterministic, "Retrieved" when generated)
- P1: Placeholder commands don't indicate they're not using LLM

### Recommendations
- Smallest safe change: Audit every command, replace `config.*` with `ctx.obj["workspace"].*`
- Refactor candidates: Create `@require_workspace` decorator that auto-injects context
- UX improvements: Add `[workspace: X]` prefix to outputs; distinguish LLM vs deterministic steps
- Label placeholders: Add `[placeholder]` to outputs for unimplemented commands

### Tests to add
- `test_status_shows_only_workspace_runs` — switch workspace, verify isolation
- `test_crm_commands_respect_workspace` — create contact in ws1, verify invisible in ws2
- `test_research_writes_to_workspace_db` — ingest source, verify in correct DB file
- `test_output_labels_distinguish_llm_vs_placeholder` — verify user knows what's real
- `test_all_commands_accept_workspace_flag` — parametrized test for all commands

### Notes / TODO
- Full command map created (35 commands across 6 groups)
- Consider splitting `cli.py` into submodules per command group
- Several BD commands need LLM implementation (currently placeholders)

---

## 2.2 Workspace System (Registry, Manifest, Policy, Prefs)
**Files:**
- `src/agnetwork/workspaces/registry.py` (241 lines)
- `src/agnetwork/workspaces/context.py` (145 lines)
- `src/agnetwork/storage/sqlite.py` (lines 388-480 — workspace_meta guard)

### WorkspaceContext Construction & Required Usage

**Construction Pattern:**
```python
# Factory method (preferred)
ctx = WorkspaceContext.create(name="bd_work", root_dir=Path("~/.ag/workspaces/bd_work"))

# Direct instantiation
ctx = WorkspaceContext(name="bd_work", workspace_id="uuid-here", root_dir=Path(...))
```

**Derived Paths (auto-computed in `__post_init__`):**
- `ctx.runs_dir` → `{root}/runs`
- `ctx.db_path` → `{root}/db/workspace.sqlite`
- `ctx.exports_dir` → `{root}/exports`
- `ctx.sources_cache_dir` → `{root}/sources_cache`

**Required Usage Contract (VIOLATED):**
- Every `SQLiteManager` instantiation MUST pass `db_path=ctx.db_path`
- Every `CRMStorage` instantiation MUST pass workspace-scoped path
- Every run operation MUST use `ctx.runs_dir` not `config.runs_dir`

### workspace_meta Guard: Correctness + Edge Cases

**Guard Implementation** (`sqlite.py:445-480`):
```python
def verify_workspace_id(self, expected_workspace_id: str) -> None:
    if self._workspace_id_verified:
        return  # Fast path: already verified this session

    actual_id = self.get_workspace_id()  # SELECT from workspace_meta

    if actual_id is None:
        # Edge case 1: New DB — auto-initialize
        self.init_workspace_metadata(expected_workspace_id)
        return

    if actual_id != expected_workspace_id:
        # Edge case 2: Wrong DB — raise exception
        raise WorkspaceMismatchError(expected=expected, actual=actual)

    # Edge case 3: Correct DB — update last_accessed
    UPDATE workspace_meta SET last_accessed = ?
```

**Edge Case Analysis:**
| Case | Input State | Expected Behavior | Actual Behavior | Status |
|------|-------------|-------------------|-----------------|--------|
| New DB (no workspace_meta row) | Empty table | Auto-init with given ID | ✅ Correct | OK |
| Correct DB | Row exists, ID matches | Update last_accessed, continue | ✅ Correct | OK |
| Wrong DB | Row exists, ID differs | Raise `WorkspaceMismatchError` | ✅ Correct | OK |
| Migration (renamed workspace) | Old ID in meta | Fail fast | ✅ Correct (intentional) | OK |
| **Guard not called** | Any | Verify on open | ❌ Never called | **P0 BUG** |

**Root Issue:** `SQLiteManager.__init__` does NOT call `verify_workspace_id()`. The guard is dead code.

### Observations
- `WorkspaceContext` dataclass is well-designed: `workspace_id`, `db_path`, `runs_dir`, `exports_dir`, `prefs`
- `WorkspaceRegistry` manages creation, listing, switching workspaces
- `verify_workspace_id(conn, expected_id)` exists in `sqlite.py` — checks `workspace_meta` table
- The verification logic is CORRECT but is NEVER AUTO-CALLED
- `_workspace_id_verified` flag exists for fast-path optimization

### Risks
- P0: `verify_workspace_id()` is dead code in production — defined at `sqlite.py:445` but `__init__` at line 93 does not call it
- P0: No enforcement that `SQLiteManager` must receive workspace context
- P1: `WorkspaceRegistry.get_workspace()` returns context but callers ignore it

### Recommendations
- Smallest safe change: Add `verify_workspace_id()` call inside `SQLiteManager.__init__` when `workspace_id` is provided
- Refactor candidates: `SQLiteManager.for_workspace(ctx: WorkspaceContext)` factory method
- Alternative: Make `db_path` constructor arg required (breaks backward compat)

### Tests to add
- `test_sqlite_rejects_wrong_workspace` — open DB with wrong workspace_id, expect exception
- `test_workspace_context_propagates_to_storage` — create context, verify DB uses correct path
- `test_registry_enforces_workspace_on_all_ops` — integration test for full flow
- `test_new_db_auto_initializes_workspace_meta` — verify edge case 1
- `test_workspace_meta_updated_on_access` — verify last_accessed updates

---

## 2.3 Storage & SQLite (Schema, Connections, Locking)
**Files:**
- `src/agnetwork/storage/sqlite.py` (1059 lines) — main entity storage with FTS5
- `src/agnetwork/storage/memory.py` (line 151) — memory API
- `src/agnetwork/crm/storage.py` (772 lines) — CRM entities
- `src/agnetwork/crm/adapters/file_adapter.py` (656 lines) — file-based CRM adapter

### COMPLETE MAP: Every Place DB Connections Are Created

#### SQLiteManager Instantiations (Production Code)
| Location | Code | Workspace-Aware? | Status |
|----------|------|------------------|--------|
| `sqlite.py:90` | `SQLiteManager(db_path)` — static method helper | ✅ Explicit path | OK |
| `sqlite.py:100` | `self.db_path = db_path or config.db_path` — default fallback | ❌ Falls back to global | **P0** |
| `memory.py:151` | `self.db = SQLiteManager(db_path)` | ✅ Explicit path | OK |
| `cli.py:284` | `db = SQLiteManager(db_path=db_path)` | ✅ Explicit path | OK |
| `cli.py:707` | `db = SQLiteManager(db_path=ws_ctx.db_path)` | ✅ From workspace | OK |
| `cli.py:952` | `db = SQLiteManager(db_path=ws_ctx.db_path)` | ✅ From workspace | OK |
| `cli.py:978` | `db = SQLiteManager(db_path=ws_ctx.db_path)` | ✅ From workspace | OK |
| `cli.py:1559` | `db = SQLiteManager(db_path=context.db_path)` | ✅ From workspace | OK |
| `cli.py:1678` | `db = SQLiteManager(db_path=context.db_path)` | ✅ From workspace | OK |
| `verifier.py:521` | `db = SQLiteManager(db_path=db_path)` | ✅ Explicit path | OK |
| `crm/mapping.py:54` | `self.db = db or SQLiteManager()` | ❌ Falls back to global | **P0** |
| `llm_executor.py:826` | `db = SQLiteManager(db_path=ws_ctx.db_path)` | ✅ From workspace | OK |
| `llm_executor.py:829` | `db = SQLiteManager()` — fallback branch | ❌ Global | **P0** |
| `executor.py:351` | `db = SQLiteManager()` | ❌ Global | **P0** |
| `validate.py:312` | `db = SQLiteManager()` | ❌ Global | **P0** |
| `ingest.py:20` | `self.db = SQLiteManager()` | ❌ Global | **P0** |

#### CRMStorage Instantiations
| Location | Code | Workspace-Aware? | Status |
|----------|------|------------------|--------|
| `crm/storage.py:37` | `CRMStorage(db_path)` — static helper | ✅ Explicit path | OK |
| `crm/storage.py:47` | `self.db_path = db_path or config.db_path` | ❌ Falls back to global | **P0** |
| `cli.py:1290` | `storage = CRMStorage()` | ❌ Global | **P0** |
| `file_adapter.py:72` | `self.storage = storage or CRMStorage()` | ❌ Falls back to global | **P0** |

#### Global config.* Usages (runs_dir, db_path)
| Location | Code | Context |
|----------|------|---------|
| `orchestrator.py:46` | `self.run_dir = config.runs_dir / self.run_id` | Fallback when no workspace |
| `cli.py:581` | `config.runs_dir.glob("*")` | `status` command |
| `cli.py:768` | `config.runs_dir / result.run_id` | Output path display |
| `cli.py:1088` | `config.runs_dir.glob("*")` | Listing runs |
| `cli.py:1339` | `config.runs_dir / run_id` | `sequence plan` |
| `crm/mapping.py:76` | `config.runs_dir / run_id` | Run lookup |

### Summary: Bypass Points
**Total SQLiteManager instantiations:** 16
**Workspace-aware:** 10
**Global/bypass:** 6 (P0 bugs)

**Total CRMStorage instantiations:** 4
**Workspace-aware:** 1
**Global/bypass:** 3 (P0 bugs)

**Total config.runs_dir usages:** 6 (all bypasses)

### Observations
- `SQLiteManager` has `workspace_meta` table with `workspace_id` column — correct schema
- `verify_workspace_id()` at line 445 does proper check: raises if mismatch
- `__init__` at line 93 accepts optional `db_path` defaulting to `config.db_path` — **no workspace verification**
- `CRMStorage` has **ZERO** workspace awareness — no `workspace_id` anywhere in file
- `FileCRMAdapter.__init__` at line 68 creates `CRMStorage()` with no args — uses global

### Risks
- P0: `SQLiteManager.__init__` does NOT call `verify_workspace_id` — guard is dead code
- P0: `CRMStorage` entire class has no workspace concept — all CRM data is global
- P0: `FileCRMAdapter` at line 68 uses `self.storage = CRMStorage()` — global storage
- P1: FTS index not workspace-scoped — search may return cross-workspace results
- P2: Connection pooling not implemented — potential performance issue under load

### Recommendations to Eliminate Bypasses

**Phase 1: Factory Methods (non-breaking)**
```python
# Add to SQLiteManager
@classmethod
def for_workspace(cls, ctx: WorkspaceContext) -> "SQLiteManager":
    """Create workspace-bound storage with automatic verification."""
    db = cls(db_path=ctx.db_path)
    db.verify_workspace_id(ctx.workspace_id)
    return db

# Add to CRMStorage
@classmethod
def for_workspace(cls, ctx: WorkspaceContext) -> "CRMStorage":
    """Create workspace-bound CRM storage."""
    return cls(db_path=ctx.db_path, workspace_id=ctx.workspace_id)
```

**Phase 2: Deprecate Default Constructors**
- Add `warnings.warn()` when `SQLiteManager()` called with no args
- Add `warnings.warn()` when `CRMStorage()` called with no args
- Log to help identify remaining bypass points

**Phase 3: Break on Bypass (opt-in)**
- Environment variable: `AG_STRICT_WORKSPACE=1`
- Raises error if workspace context not provided

### Tests That Would Catch Leakage
1. `test_sqlite_manager_verifies_workspace_on_init` — constructor calls guard
2. `test_sqlite_rejects_mismatched_workspace` — open ws1 DB with ws2 ID → error
3. `test_crm_storage_workspace_isolation` — create contact in ws1, invisible in ws2
4. `test_file_adapter_uses_workspace_storage` — adapter propagates context
5. `test_fts_search_respects_workspace_boundary` — search only returns ws results
6. `test_claims_persist_to_workspace_db` — executor writes to correct DB
7. `test_ingestor_writes_to_workspace_db` — sources go to correct DB
8. `test_cli_status_shows_only_workspace_runs` — status filtered by workspace
9. `test_no_global_db_path_in_production_code` — grep test for `SQLiteManager()` with no args
10. `test_workspace_meta_populated_on_first_access` — new DB gets metadata

---

## 2.4 Memory & FTS Retrieval — MODULE 3 (SQLite Patterns)
**Files:**
- `src/agnetwork/storage/sqlite.py` (1059 lines)
- `src/agnetwork/storage/memory.py`
- `src/agnetwork/crm/storage.py` (772 lines)

### SQLite Usage Patterns Audit

#### Connection Lifecycle

**Pattern Used:**
```python
with sqlite3.connect(self.db_path) as conn:
    cursor = conn.cursor()
    # ... operations
    conn.commit()
```

**Observations:**
- ✅ Context manager (`with`) used consistently — connections auto-close on exit
- ✅ `close()` method in both `SQLiteManager` and `CRMStorage` handles WAL cleanup
- ⚠️ No persistent connection pooling — new connection per operation
- ⚠️ `close()` creates a NEW connection just to disable WAL mode — potential issue on Windows

#### Transaction Boundaries

| Location | Transaction Scope | Correct? |
|----------|------------------|----------|
| `_init_db()` | Schema creation | ✅ Implicit tx |
| `rebuild_fts_index()` | DELETE + INSERT | ✅ Single commit |
| `add_source()` | Single INSERT | ✅ OK |
| `upsert_source_from_capture()` | INSERT OR REPLACE | ✅ OK |
| Multi-step pipeline | Multiple operations | ⚠️ No explicit tx boundary |

**Issue:** No explicit `BEGIN TRANSACTION` / `ROLLBACK` for multi-step operations. A failure mid-pipeline could leave partially committed state.

#### File Locking (Windows Safety)

**Concerns:**
1. `close()` method (lines 117-137) opens NEW connection to run PRAGMA commands
2. WAL mode creates `-wal` and `-shm` files that can lock on Windows
3. No `busy_timeout` PRAGMA set — concurrent access could fail immediately
4. Tests use `gc.collect()` to force connection cleanup (brittle)

**Windows-Specific Issues Found:**
- `test_memory.py:34` has `close_sqlite_connections()` helper using `gc.collect()` — indicates known issues
- `close()` does `PRAGMA journal_mode=DELETE` to switch from WAL — may fail if other connections open

#### Indexes and Query Efficiency

**Indexes Present:**
- CRM: `idx_crm_accounts_domain`, `idx_crm_contacts_email`, `idx_crm_activities_run`
- FTS5: `sources_fts`, `artifacts_fts` with triggers for auto-sync

**Missing Indexes (Potential Issues):**
- `sources.run_id` — no index, used in queries to filter by run
- `sources.content_hash` — no index, used for deduplication
- `claims.artifact_id` — no index if table exists
- `workspace_meta` — single row, no issue

### Safe DB Usage Checklist

```
□ Use context manager: `with sqlite3.connect(db_path) as conn:`
□ Always call .close() when done with SQLiteManager/CRMStorage
□ Set PRAGMA busy_timeout for concurrent access: `PRAGMA busy_timeout=5000`
□ Use explicit transactions for multi-step operations: `BEGIN`, `COMMIT`, `ROLLBACK`
□ On Windows: call close() before file deletion/move
□ Index columns used in WHERE/JOIN: run_id, content_hash, etc.
□ FTS5 triggers exist for auto-sync — don't INSERT directly to *_fts tables
□ Use INSERT OR REPLACE for upserts (used correctly)
□ Verify workspace_id before operations (currently NOT enforced)
```

### Concrete Fixes (Footguns)

#### Fix 1: Add `busy_timeout` PRAGMA (P1)
```python
# In _init_db() after connect:
def _init_db(self) -> None:
    with sqlite3.connect(self.db_path) as conn:
        conn.execute("PRAGMA busy_timeout=5000")  # 5 second wait
        cursor = conn.cursor()
        # ... rest of schema
```

#### Fix 2: Safe Windows `close()` (P1)
```python
def close(self) -> None:
    if self._closed:
        return
    self._closed = True

    # Use check_same_thread=False for cleanup connection
    try:
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except sqlite3.Error:
        pass  # Best effort

    gc.collect()  # Still needed for Python's sqlite3 module
```

#### Fix 3: Add Missing Index for `run_id` (P2)
```python
# In _init_db():
cursor.execute(
    "CREATE INDEX IF NOT EXISTS idx_sources_run_id ON sources(run_id)"
)
cursor.execute(
    "CREATE INDEX IF NOT EXISTS idx_sources_content_hash ON sources(content_hash)"
)
```

### Risks
- P1: No `busy_timeout` — concurrent CLI invocations could crash with "database is locked"
- P1: `close()` may fail on Windows if WAL files locked by another process
- P1: Multi-step operations have no rollback on failure
- P2: Missing indexes on `run_id`, `content_hash` could slow queries at scale

### Tests to Add
- `test_concurrent_db_access` — two processes writing simultaneously should not crash
- `test_windows_db_cleanup` — close() should leave no -wal/-shm files
- `test_transaction_rollback_on_error` — partial failure should not corrupt state
- `test_fts_triggers_sync` — INSERT to sources should auto-update sources_fts

---

## 2.5 Web Ingestion (Fetch, Clean, Cache, Deep Links) — MODULE 4 (Memory/FTS)
**Files:**
- `src/agnetwork/storage/memory.py` (483 lines) — MemoryAPI
- `src/agnetwork/storage/sqlite.py` — FTS5 schema and triggers

### Module 4: Memory/FTS Retrieval Review

#### FTS Index Rebuild Triggers

| Trigger | When Fired | Auto/Manual |
|---------|------------|-------------|
| `sources_ai` | AFTER INSERT ON sources | ✅ Auto |
| `sources_ad` | AFTER DELETE ON sources | ✅ Auto |
| `sources_au` | AFTER UPDATE ON sources | ✅ Auto |
| `artifacts_ai` | AFTER INSERT ON artifacts | ✅ Auto |
| `artifacts_ad` | AFTER DELETE ON artifacts | ✅ Auto |
| `artifacts_au` | AFTER UPDATE ON artifacts | ✅ Auto |
| `rebuild_fts_index()` | CLI `ag memory rebuild-index` | Manual |

**Observations:**
- ✅ Triggers correctly keep FTS in sync — no manual rebuild needed for normal ops
- ✅ `rebuild_fts_index()` exists for recovery (DELETE + re-INSERT)
- ⚠️ No automatic rebuild detection — if triggers fail silently, FTS drifts

#### Query Patterns

**FTS5 Query Flow:**
```
User Query → _escape_fts_query() → search_*_fts() → BM25 scoring → Results
```

**Issues Found:**
1. `_escape_fts_query()` strips `*` which disables prefix matching — may not be intentional
2. `_to_simple_query()` limits to 5 words — could miss important context
3. No query logging — can't debug why searches return empty

#### Retrieval Mode Recording

**Current State:**
- `EvidenceBundle.query` stores the query string ✅
- `EvidenceBundle.retrieval_timestamp` stores when retrieved ✅
- ❌ **Missing:** No record of whether FTS or semantic search was used
- ❌ **Missing:** No record of result count before limit was applied
- ❌ **Missing:** CLI doesn't indicate "Retrieved from memory" vs "No memory hits"

#### Proposed `RetrievalReport` Structure

```python
@dataclass
class RetrievalReport:
    """Observability data for retrieval operations."""

    query: str
    retrieval_mode: Literal["fts5", "semantic", "hybrid"]  # Track method used
    sources_searched: int  # Total in DB
    sources_matched: int   # Before limit
    sources_returned: int  # After limit
    artifacts_searched: int
    artifacts_matched: int
    artifacts_returned: int
    duration_ms: float     # Time to execute
    workspace_id: str      # Which workspace was searched
    timestamp: datetime

    # Debug info
    escaped_query: str     # After escaping
    fallback_used: bool    # Did we fall back to simple query?
```

### Recommended Timing Instrumentation Points

```python
# In MemoryAPI.search_sources():
start = time.perf_counter()
# ... search logic
duration_ms = (time.perf_counter() - start) * 1000
logger.debug(f"FTS search completed in {duration_ms:.2f}ms, {len(results)} hits")
```

**Instrumentation Points:**
1. `search_sources()` entry/exit — track FTS latency
2. `search_artifacts()` entry/exit — track FTS latency
3. `retrieve_context()` — track total retrieval time
4. `_escape_fts_query()` — log transformation for debugging
5. `rebuild_fts_index()` — log duration and row counts

### Top Likely Performance Regressions

| Risk | Severity | Trigger Condition | Mitigation |
|------|----------|-------------------|------------|
| FTS unbounded scan | P1 | Query matches many rows | Add `LIMIT` clause in SQL (already has `limit` param) |
| No index on `run_id` | P2 | Filter by run in large DB | Add index (see Module 3) |
| Global `_memory_api` singleton | P1 | First call slow; can't switch workspace | Create per-workspace instances |
| Trigger cascade | P2 | Bulk insert triggers many FTS updates | Disable triggers, bulk insert, rebuild |
| Query escaping strips wildcards | P2 | User expects prefix match | Allow `*` in query or add explicit prefix mode |

### Risks
- P1: Global `_memory_api` singleton (line 400) ignores `db_path` after first call — workspace leak
- P1: No indication to user whether memory was used ("Retrieved 5 sources" never shown)
- P2: FTS query fallback swallows exceptions silently — hard to debug
- P2: `workspace` parameter in search methods is "not yet implemented" — comment says so

### Tests to Add
- `test_fts_triggers_sync_on_insert` — INSERT source, verify in FTS
- `test_fts_triggers_sync_on_delete` — DELETE source, verify removed from FTS
- `test_retrieval_report_captures_timing` — verify duration_ms populated
- `test_memory_api_respects_workspace` — two workspaces, isolated search results
- `test_search_escaping_preserves_intent` — verify prefix match still works

---

## 2.6 Evidence & Verifier (Claims/Evidence Snippets) — MODULE 5 (Web/Evidence)
**Files:**
- `src/agnetwork/tools/web/capture.py` (280 lines) — URL capture
- `src/agnetwork/tools/web/clean.py` (194 lines) — HTML → text
- `src/agnetwork/tools/web/fetch.py` (190 lines) — HTTP fetching
- `src/agnetwork/tools/web/deeplinks.py` (813 lines) — deep link discovery
- `src/agnetwork/eval/verifier.py` (563 lines)
- `src/agnetwork/tools/ingest.py` (129 lines)

### Web Ingestion Pipeline Review

#### Raw/Clean/Meta File Structure
```
sources/
  {slug}__raw.html          # Original HTML
  {slug}__clean.txt         # Extracted text
  {slug}__meta.json         # Metadata (url, hash, title, timestamp)
  deeplinks.json            # M8: discovered links
```

#### UTF-8 Handling
- ✅ `clean.py`: Uses BeautifulSoup which handles encoding
- ✅ `capture.py:149`: `clean_file.read_text(encoding="utf-8")`
- ⚠️ `fetch.py`: Returns `content_bytes` — caller must decode
- ⚠️ No explicit charset detection from HTTP headers

#### Caching & Deduplication
- ✅ `SourceCapture._cache` — in-memory URL cache per run
- ✅ `_load_existing_cache()` — reads from `*__meta.json` files
- ✅ `content_hash` (SHA256) computed on fetch
- ✅ `capture_url(force_refresh=True)` to bypass cache
- ⚠️ No cross-run deduplication (same URL fetched in different runs)

### Failure Modes Matrix

| Failure Mode | Symptom | Current Handling | Recommendation |
|--------------|---------|------------------|----------------|
| **Encoding issues** | Garbled text | BeautifulSoup default | Add charset from headers |
| **Truncation** | Large page cut off | `max_bytes=10MB` in fetch | ✅ OK |
| **JS-heavy pages** | No content extracted | Empty clean text | Log warning; try Playwright |
| **Robots.txt blocked** | 403/429 status | Returns error CapturedSource | ✅ OK |
| **Redirect loops** | Timeout | httpx handles | ✅ OK (max_redirects) |
| **SSL errors** | Connection failed | Exception → error result | ✅ OK |
| **Rate limiting** | 429 status | Per-host 1s delay | May need exponential backoff |
| **Deep link explosion** | Too many fetches | `max_total=4` in config | ✅ OK |

### Deep Link Discovery & Agent Constraints

**Deterministic Mode:**
1. Parse HTML for `<a>` tags
2. Score by keyword match (config-driven)
3. Pick top N per category
4. Output to `deeplinks.json`

**Agent Mode (constrained):**
1. Same candidate extraction
2. LLM picks from provided candidates ONLY
3. Cannot invent URLs outside candidate set
4. `method: "agent"` recorded in selection

**Auditability:**
- ✅ `deeplinks.json` records: all candidates, scores, selections, method
- ✅ `DeepLinkSelection.to_dict()` includes reason and method
- ⚠️ No human-readable explanation in CLI output

### Evidence Quote Verification

**Verifier Check Flow:**
```
SkillResult → _check_evidence_quotes()
    → For each personalization_angle:
        → If not is_assumption AND no evidence → ERROR
        → For each evidence item:
            → Load source via source_loader(source_id)
            → Check: quote in source_text (exact match)
            → Fallback: case-insensitive + whitespace-normalized
            → If not found → ERROR
```

### Observations (Ingestor/Verifier)
- `Verifier` class validates skill results: schema compliance, evidence snippets, claim consistency
- `create_verifier_with_sources(db_path=...)` factory accepts `db_path` — **partially workspace-aware**
- `SourceIngestor` at line 20: `self.db = SQLiteManager()` — **uses global DB**
- CLI `research` command at line 274 instantiates `SourceIngestor(run.run_dir)` but passes no `db_path`
- Verifier has `_source_loader` callback pattern — good abstraction for source retrieval

### Risks
- P0: `SourceIngestor.__init__` line 20 uses `SQLiteManager()` with no args — global DB
- P0: CLI `research` at line 274 doesn't pass workspace DB path to ingestor
- P1: JS-heavy pages return empty content — no warning to user
- P1: No charset detection from HTTP headers — may mishandle non-UTF8
- P1: Singleton `_verifier` pattern without source loader may miss evidence checks
- P2: No cross-run deduplication — same URL fetched repeatedly
- P2: No caching of verification results — repeated verification is wasteful

### Recommendations
- Smallest safe change: `SourceIngestor.__init__(self, run_dir, db_path=None)` — require or default properly
- Update CLI `research` to pass `ctx.obj["workspace"].db_path`
- Add charset detection from `Content-Type` header
- Log warning when clean text is empty for HTML page

### Tests to add
- `test_ingestor_writes_to_workspace_db` — ingest file, verify in correct DB
- `test_verifier_uses_workspace_sources` — verify evidence from correct workspace
- `test_research_command_workspace_isolation` — CLI integration test
- `test_deep_links_recorded_in_json` — audit trail complete
- `test_evidence_tamper_detection` — modified quote fails verification
- `test_js_heavy_page_warning` — empty extraction logged

---

## 2.7 Kernel Execution (TaskSpec → Plan → Execute) — MODULE 6
**Files:**
- `src/agnetwork/kernel/contracts.py` (241 lines) — Skill contracts
- `src/agnetwork/kernel/models.py` (181 lines) — TaskSpec, Plan, Step
- `src/agnetwork/kernel/executor.py` (641 lines) — Plan execution
- `src/agnetwork/kernel/llm_executor.py` (873 lines) — LLM-assisted execution
- `src/agnetwork/kernel/planner.py` — Plan generation

### Contract Model Clarity

**Core Types:**
```
TaskSpec            → Input specification (task_type, inputs, constraints)
    ↓
Plan                → Ordered list of Steps
    ↓
Step                → skill_name, inputs, status
    ↓
Skill.run()         → (inputs, SkillContext) → SkillResult
    ↓
SkillResult         → output, artifacts, claims, warnings, metrics
```

**Versioning Fields:**
- `SkillResult.skill_version` — skill version string
- `ArtifactRef.metadata` — can store schema version
- ⚠️ No global contract version enforced across skill/kernel boundary

### Contract Upgrade Strategy

**Safe Schema Evolution:**
1. **Additive changes** (safe): Add new optional fields to `SkillResult`, `TaskSpec`, etc.
2. **Default values** (safe): New fields must have defaults for backward compat
3. **Deprecation** (safe): Mark old fields, keep working, log warnings
4. **Breaking changes** (requires version bump): Remove fields, change types

**Proposed Versioning:**
```python
class SkillContract:
    CONTRACT_VERSION = "1.0"  # Bump on breaking changes

    @classmethod
    def check_compatibility(cls, result: SkillResult) -> bool:
        # Verify result was produced by compatible contract version
        ...
```

### Skill Registration & Invocation

**Registration Pattern:**
```python
@register_skill("research_brief")
class ResearchBriefSkill:
    def run(self, inputs, context) -> SkillResult: ...
```

**Invocation:**
```python
skill = skill_registry.get(step.skill_name)  # Line 518
if skill:
    result = skill.run(inputs, context)
```

**Issues:**
- ⚠️ Global `skill_registry` singleton — not workspace-scoped (but skills are stateless, so OK)
- ⚠️ No skill existence check at plan time — fails at execute time

### Error Propagation & Partial Failures

**Current Flow:**
```
Step fails → ExecutionResult.add_error() → success=False
          → Later steps may still run
          → Partial artifacts may be written
```

**Issues:**
- P1: No rollback mechanism — partial artifacts persist
- P1: No "stop on first error" option
- P2: Errors aggregated but no structured failure report per step

### Brittle Couplings

| Coupling | Location | Risk |
|----------|----------|------|
| `skill_registry` global | `executor.py:57` | Low — skills are stateless |
| `TaskType` → skill mapping | `planner.py` | Medium — implicit; add new task type = update planner |
| `SkillResult.output` is `Any` | `contracts.py:161` | Medium — type safety lost |
| `EvidenceBundle` via `Any` | `contracts.py:114` | Low — avoids circular import |
| `llm_factory` dependency | `executor.py:127` | Medium — must match LLM mode |

### Observations
- `Executor` orchestrates plan execution: parse task → build plan → execute steps → persist artifacts
- `_get_memory_api(db_path=db_path)` at line 220 **correctly** accepts db_path — partial workspace awareness
- `_persist_claims()` at line 351 uses `db = SQLiteManager()` — **global DB**
- `LLMExecutor` at line 829 has fallback `db = SQLiteManager()` when no explicit path — **global DB**
- `RunContext` dataclass carries `run_dir`, `workspace_id` — but not always propagated

### Risks
- P0: `_persist_claims` line 351: `SQLiteManager()` with no args — claims written to global DB
- P0: `LLMExecutor` line 829 fallback uses global DB — skill results may go to wrong workspace
- P1: `RunContext.workspace_id` exists but not consistently used to derive `db_path`
- P1: No rollback on partial failure — inconsistent state possible
- P2: No contract version enforcement at skill boundary

### Recommendations
- Smallest safe change: Pass `db_path` from `RunContext` to `_persist_claims` and `LLMExecutor`
- Add helper: `RunContext.get_db_path()` that derives path from workspace_id
- Consider: Make `SQLiteManager()` with no args raise error (force explicit path)
- Add `CONTRACT_VERSION` constant and compatibility check

### Tests to add
- `test_claims_written_to_workspace_db` — execute skill, verify claims in correct DB
- `test_llm_executor_respects_workspace` — run LLM skill, verify artifacts in workspace
- `test_run_context_propagates_db_path` — integration test for full flow
- `test_partial_failure_does_not_corrupt` — first skill fails, verify clean state
- `test_new_skill_registration` — register skill, execute via plan

---

## 2.8 Skills (BD + work_ops + personal_ops) — MODULE 7
**Files:**
- `src/agnetwork/skills/*.py` (BD pipeline: 5 skills)
- `src/agnetwork/skills/work_ops/*.py` (3 skills)
- `src/agnetwork/skills/personal_ops/*.py` (3 skills)
- `src/agnetwork/skills/contracts.py` (re-exports from kernel)

### Skill Inventory

| Skill Name | File | Version | Evidence Discipline |
|------------|------|---------|---------------------|
| **BD Pipeline** |
| `research_brief` | `skills/research_brief.py` | 1.0 | ✅ `source_ids` → `SourceRef` |
| `target_map` | `skills/target_map.py` | 1.0 | ✅ `source_ids` → `SourceRef` |
| `outreach` | `skills/outreach.py` | 1.0 | ❌ No evidence |
| `meeting_prep` | `skills/meeting_prep.py` | 1.0 | ❌ No evidence |
| `followup` | `skills/followup.py` | 1.0 | ❌ No evidence |
| **Work Ops** |
| `meeting_summary` | `skills/work_ops/meeting_summary.py` | 1.0 | ❌ `source_refs=[]` |
| `decision_log` | `skills/work_ops/decision_log.py` | 1.0 | ❌ `source_refs=[]` |
| `status_update` | `skills/work_ops/status_update.py` | 1.0 | ❌ `source_refs=[]` |
| **Personal Ops** |
| `weekly_plan` | `skills/personal_ops/weekly_plan.py` | 1.0 | ❌ `source_refs=[]` |
| `errand_list` | `skills/personal_ops/errand_list.py` | 1.0 | ❌ `source_refs=[]` |
| `travel_outline` | `skills/personal_ops/travel_outline.py` | 1.0 | ❌ `source_refs=[]` |

### Shared Pattern (Duplication)

Every skill follows identical boilerplate (~80 lines each):
```python
@register_skill("name")
class NameSkill:
    name = "name"
    version = "1.0"

    def __init__(self):
        self.template = self._get_template()

    def _get_template(self) -> Template:
        return Template(template_str)

    def run(self, inputs, context) -> SkillResult:
        # 1. Extract inputs
        # 2. Build data dict
        # 3. Render markdown
        # 4. Build JSON
        # 5. Create claims (mostly empty)
        # 6. Create ArtifactRef (MD + JSON)
        # 7. Return SkillResult
```

### Skill Authoring Guide Checklist

```
□ Use @register_skill("skill_name") decorator
□ name class attribute matches decorator argument
□ version class attribute (semver, e.g. "1.0")
□ run(inputs: Dict, context: SkillContext) -> SkillResult
□ Set skill_name and skill_version on result
□ Artifact naming: static = skill name, dynamic = {skill}_{date}
□ Both MD and JSON artifacts use SAME name
□ FACT claims require source_ids → SourceRef evidence
□ Unsourced claims must be ClaimKind.ASSUMPTION
□ Handle missing inputs with .get() defaults
□ Include test: test_{skill}_returns_valid_result
```

### Refactor: Extract BaseSkill

```python
class BaseSkill:
    """Base class with common skill patterns."""
    name: str
    version: str = "1.0"
    template_str: str

    def __init__(self):
        self.template = Template(self.template_str)

    def run(self, inputs, context) -> SkillResult:
        data = self.prepare_data(inputs, context)
        markdown = self.template.render(**data)
        json_data = self.prepare_json(data)
        claims = self.extract_claims(data)
        artifacts = self.build_artifacts(markdown, json_data, data)
        return SkillResult(...)

    def prepare_data(self, inputs, context) -> Dict: ...  # Override
    def extract_claims(self, data) -> List[Claim]: ...   # Override
```

### Observations
- All 11 skills use identical boilerplate (Jinja2 template pattern)
- Only `research_brief` and `target_map` properly convert `source_ids` to `SourceRef`
- 9/11 skills have empty `evidence=[]` on all claims
- `contracts.py` re-exports from `kernel.contracts` for convenience
- Artifact naming inconsistent: BD skills use static names, work/personal use dynamic

### Risks
| Risk | Severity | Evidence |
|------|----------|----------|
| 9/11 skills have empty evidence | P1 | All work_ops/personal_ops |
| ~80 lines duplicate boilerplate per skill | P2 | All 11 skill files |
| Inconsistent artifact naming | P2 | Static vs dynamic |
| No input validation | P2 | All skills accept any Dict |
| Only 1 skill has test coverage | P2 | Only `test_skills.py:research_brief` |

### Recommendations
1. **Extract `BaseSkill`** — reduce 80-line boilerplate to ~15 lines per skill
2. **Standardize artifact naming** — document pattern in authoring guide
3. **Add `_validate_inputs()`** — common validation with required/optional keys
4. **Review evidence policy** — should work_ops claims cite meeting notes?
5. **Add parametrized tests** — test all skills for contract compliance

### Tests to add
```python
@pytest.mark.parametrize("skill_name", ALL_SKILLS)
def test_skill_returns_valid_result(skill_name): ...

@pytest.mark.parametrize("skill_name", ALL_SKILLS)
def test_skill_produces_md_and_json(skill_name): ...

def test_research_brief_facts_have_evidence(): ...

def test_unsourced_claims_marked_assumption(): ...
```

---

## 2.9 Observability & Run Analysis — MODULE 8
**Files:**
- `src/agnetwork/orchestrator.py` (200 lines) — RunManager
- `src/agnetwork/validate.py` (337 lines) — Run folder validation
- `src/agnetwork/kernel/contracts.py` — `SkillMetrics`
- `src/agnetwork/kernel/llm_executor.py` — `_build_skill_result` (timing)

### Current Logging Infrastructure

| Component | File | Format | Contents |
|-----------|------|--------|----------|
| `agent_worklog.jsonl` | `{run}/logs/` | JSONL | Structured action log: phase, action, status |
| `agent_status.json` | `{run}/logs/` | JSON | Session state: phases, metrics |
| `run.log` | `{run}/logs/` | Plain text | Python logging output |
| `SkillMetrics` | In `SkillResult` | Object | `execution_time_ms`, `input_tokens`, `output_tokens` |

### What CAN Be Reconstructed Today

| Information | Source | Reliability |
|-------------|--------|-------------|
| Which phases ran | `agent_worklog.jsonl` | ✅ Good |
| Action timestamps | `agent_worklog.jsonl` | ✅ Good |
| Phase status | `agent_worklog.jsonl` | ✅ Good |
| Skill execution time | `SkillMetrics.execution_time_ms` | ⚠️ Only in LLM skills |
| Input/output tokens | `SkillMetrics.input_tokens/output_tokens` | ❌ Never populated |
| Tool calls made | None | ❌ Missing |
| Memory retrieval details | None | ❌ Missing |
| LLM prompts/responses | None | ❌ Missing |
| Cache hits | None | ❌ Missing |

### What's MISSING for Debugging

1. **Tool Call Log** — no record of which tools were invoked with what params
2. **Retrieval Details** — no record of FTS queries, result counts, selection
3. **LLM Interaction Log** — no prompts/responses saved (privacy tradeoff)
4. **Cache Hit/Miss** — can't tell if result came from cache
5. **Step-level timing** — only skill-level, not sub-operations

### Proposed `trace.jsonl` Schema

```python
@dataclass
class TraceEvent:
    """Single event in the trace log."""
    timestamp: str          # ISO8601
    event_type: Literal["step_start", "step_end", "tool_call", "retrieval", "llm_call", "error"]
    run_id: str
    step_id: Optional[str]  # For step events
    skill_name: Optional[str]
    duration_ms: Optional[float]
    details: Dict[str, Any]  # Event-specific data

# Event types:
# step_start: { inputs, mode }
# step_end: { success, artifact_names, claim_count }
# tool_call: { tool_name, params_summary, result_summary }
# retrieval: { query, mode, sources_matched, sources_returned }
# llm_call: { model, input_tokens, output_tokens, cached }
# error: { error_type, message, stack_trace }
```

### Proposed CLI Commands

```bash
# Explain what happened in a run
ag run explain <run_id>
# Output:
# Run: 20260128_143022__acme__research
# Duration: 12.3s
# Steps:
#   1. research_brief (LLM) - 8.2s - success
#      - Retrieved: 5 sources (FTS)
#      - LLM: claude-3-opus, 1200 tokens
#   2. target_map (deterministic) - 0.1s - success

# Export trace for debugging
ag run trace <run_id> --output trace.jsonl

# Real-time verbose mode
ag research acme --trace --verbose
# Prints step-by-step progress with timing
```

### Observations
- `RunManager` writes structured logs (`agent_worklog.jsonl`, `agent_status.json`)
- `SkillMetrics` has fields for timing and tokens but `input_tokens`/`output_tokens` never populated
- `LLMExecutor._build_skill_result()` calculates `execution_time_ms` ✅
- Deterministic skills create `SkillMetrics()` with no data
- No tool call logging exists
- No retrieval logging exists
- `deeplinks.py` has `logger.info()` calls but not in structured format

### Risks
| Risk | Severity | Evidence |
|------|----------|----------|
| Can't debug "why did the agent choose X" | P1 | No decision log |
| Can't tell if result came from cache | P1 | No cache indicator |
| `input_tokens`/`output_tokens` always None | P2 | Never assigned |
| No retrieval trace | P2 | FTS queries not logged |
| `run.log` mixes with global Python logs | P2 | Logger named `agnetwork.{run_id}` |

### Recommendations
1. **Add `trace.jsonl`** — structured event log per run
2. **Populate token counts** — pass through from LLM response
3. **Add `--trace` flag** — enable detailed logging mode
4. **Add `ag run explain`** — human-readable run summary
5. **Instrument retrieval** — log query, mode, counts in `MemoryAPI`

### Tests to add
```python
def test_skill_metrics_populated_for_llm(): ...
def test_trace_captures_tool_calls(): ...
def test_trace_captures_retrieval(): ...
def test_run_explain_output_format(): ...
def test_verbose_mode_prints_progress(): ...
```

---

## 2.10 CI/CD & Packaging — MODULE 9
**Files:**
- `.github/workflows/ci.yml` (35 lines)
- `pyproject.toml` (73 lines)
- `requirements-lock.txt` (48 lines)

### Current CI Pipeline

```yaml
# .github/workflows/ci.yml
on: push/PR to main/master
jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    python: 3.11 only
    steps:
      - checkout
      - setup-python 3.11 (with pip cache)
      - pip install -e ".[dev]"
      - ruff check
      - ruff format --check
      - pytest -v --tb=short
```

### Issues Found

| Issue | Severity | Current | Recommended |
|-------|----------|---------|-------------|
| Single Python version | P1 | 3.11 only | Matrix: 3.11, 3.12, 3.13 |
| No Windows testing | P1 | ubuntu-latest only | Add windows-latest |
| No dependency pinning in CI | P2 | `pip install -e ".[dev]"` | Use lockfile or hash-pinned |
| No coverage threshold | P2 | pytest without cov | Add `--cov --cov-fail-under=80` |
| Lockfile has editable installs | P2 | `-e git+...` in lockfile | Pin concrete versions |
| No cache for dependencies | P2 | Only pip cache | Add full deps cache |
| No test isolation | P2 | All tests in one job | Separate lint/test/coverage |

### Dependency Pinning Analysis

**`pyproject.toml` - Loose Pins:**
```toml
dependencies = [
    "typer[all]>=0.9.0",      # Any 0.9+
    "pydantic>=2.0.0",        # Any 2.x
    "httpx>=0.27.0",          # Any 0.27+
]
```

**`requirements-lock.txt` - Problems:**
```
-e git+https://...@b74ea45...#egg=ag_network   # ❌ Editable install
pydantic==2.12.5                                # ✅ Pinned
```

**Issues:**
1. Lockfile contains `-e` editable installs — not reproducible
2. Lockfile references git commits — fragile
3. No separate `requirements.txt` for production vs dev
4. `python_version<'3.11'` conditional in deps but CI only tests 3.11

### Proposed GitHub Actions Matrix

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install ruff
      - run: ruff check .
      - run: ruff format --check .

  test:
    needs: lint
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
        python: ["3.11", "3.12"]
      fail-fast: false
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
          cache: pip
      - name: Install deps
        run: pip install -e ".[dev]"
      - name: Run tests
        run: pytest -v --tb=short --cov=agnetwork --cov-fail-under=80
      - name: Upload coverage
        if: matrix.os == 'ubuntu-latest' && matrix.python == '3.11'
        uses: codecov/codecov-action@v4

  type-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: mypy src/agnetwork --ignore-missing-imports
```

### Lockfile Strategy

**Option 1: pip-compile (Recommended)**
```bash
# Generate lockfile from pyproject.toml
pip-compile pyproject.toml -o requirements.lock
pip-compile pyproject.toml --extra dev -o requirements-dev.lock

# Install in CI
pip install -r requirements.lock
pip install -e . --no-deps
```

**Option 2: pip freeze (Current)**
```bash
pip freeze > requirements-lock.txt
# ❌ Captures editable installs
# ❌ Captures git URLs
```

### Flaky Test Analysis

| Test File | Potential Flakiness | Cause |
|-----------|---------------------|-------|
| `test_memory.py` | ⚠️ Medium | Uses `gc.collect()` for SQLite cleanup |
| `test_web.py` | ⚠️ Medium | May hit network if mocks fail |
| `test_sequence_templates.py` | ⚠️ Low | Datetime comparisons |
| `test_workspace_isolation.py` | ⚠️ Medium | File system timing on Windows |

### Observations
- CI runs on Ubuntu only — no Windows coverage
- Single Python version (3.11) — no forward compat testing
- No coverage reporting or threshold
- Lockfile has `-e git+...` entries — not reproducible
- `mypy` in dev deps but not run in CI
- No separate lint vs test jobs

### Risks
| Risk | Severity | Evidence |
|------|----------|----------|
| Windows-specific bugs undetected | P1 | SQLite WAL, path handling |
| Python 3.12/3.13 breakage undetected | P1 | No matrix testing |
| Dependency drift | P2 | Loose pins, broken lockfile |
| Coverage unknown | P2 | No coverage check |
| Type errors undetected | P2 | mypy not in CI |

### Recommendations
1. **Add matrix testing** — Ubuntu + Windows, Python 3.11 + 3.12
2. **Fix lockfile** — use pip-compile, remove editable installs
3. **Add coverage threshold** — `--cov-fail-under=80`
4. **Add mypy to CI** — catch type errors
5. **Split jobs** — lint → test → type-check (parallel)
6. **Add Windows-specific tests** — mark with `@pytest.mark.windows`

### Tests to add
```python
@pytest.mark.windows
def test_sqlite_wal_cleanup_windows(): ...

def test_requires_python_311_or_higher(): ...

def test_no_deprecated_imports(): ...
```

---

# 3) Performance Notes
## Benchmarks captured
- Command:
- Dataset:
- Machine:
- Results:

## Hotspots (suspected/confirmed)
- 

## Proposed changes
- 

---

# 4) Security & Privacy Notes
## Threat model assumptions
- Local-first; no automatic external writebacks
- Workspaces isolate work/private/client contexts
- Web fetching is potentially risky (SSRF, internal IPs)

## Findings
- SSRF:
- Secrets handling:
- PII in logs:
- Path traversal:

## Recommended mitigations
- 

---

# 5) Decisions & Follow-ups
- Decisions made during review:
- Follow-up tasks delegated:
- Deferred items (with rationale):

---

# Appendix A — Review log
| Time | Module | Area | Files | Notes |
|------|--------|------|-------|-------|
| 2026-01-28 | M1 | CLI | `cli.py` | 35 commands mapped; 5 P0 workspace issues found |
| 2026-01-28 | M2 | Workspace | `workspaces/registry.py`, `context.py` | `verify_workspace_id` is dead code |
| 2026-01-28 | M2 | Storage | `storage/sqlite.py` | Guard exists but never auto-called |
| 2026-01-28 | M2 | CRM Storage | `crm/storage.py`, `file_adapter.py` | Zero workspace awareness |
| 2026-01-28 | M3 | SQLite Patterns | `storage/sqlite.py`, `crm/storage.py` | Safe usage checklist created |
| 2026-01-28 | M4 | Memory/FTS | `storage/memory.py` | RetrievalReport proposed |
| 2026-01-28 | M5 | Web/Evidence | `tools/web/*.py`, `eval/verifier.py` | Failure modes matrix |
| 2026-01-28 | M6 | Kernel | `kernel/*.py` | Contract upgrade strategy |
| 2026-01-28 | M7 | Skills | `skills/**/*.py` | Authoring guide checklist; BaseSkill refactor |
| 2026-01-28 | M8 | Observability | `orchestrator.py`, `validate.py` | trace.jsonl proposal |
| 2026-01-28 | M9 | CI/CD | `.github/workflows/ci.yml`, `pyproject.toml` | Matrix testing proposal |

## Files pending review
- ~~`src/agnetwork/validate.py` line 312 — suspected `SQLiteManager()` global usage~~ ✅ Confirmed
- ~~`src/agnetwork/crm/mapping.py` line 54 — suspected `self.db = db or SQLiteManager()` pattern~~ ✅ Confirmed
- ~~Memory/FTS subsystem~~ ✅ Reviewed (M4)
- ~~Web ingestion tools~~ ✅ Reviewed (M5)
- ~~Skills implementations~~ ✅ Reviewed (M7)
- ~~Observability/logging~~ ✅ Reviewed (M8)
- ~~CI/CD configuration~~ ✅ Reviewed (M9)

## Module Review Status
| Module | Status | Deliverables |
|--------|--------|--------------|
| M1: CLI | ✅ Complete | Command map, misleading outputs, 5 regression tests |
| M2: Workspace/Storage | ✅ Complete | Invariants, DB connection map, factory methods |
| M3: SQLite Patterns | ✅ Complete | Safe usage checklist, 3 concrete fixes |
| M4: Memory/FTS | ✅ Complete | RetrievalReport proposal, perf risks |
| M5: Web/Evidence | ✅ Complete | Failure modes matrix, evidence flow |
| M6: Kernel | ✅ Complete | Contract upgrade strategy, brittle couplings |
| M7: Skills | ✅ Complete | Authoring guide checklist, BaseSkill refactor |
| M8: Observability | ✅ Complete | trace.jsonl schema, CLI additions |
| M9: CI/CD | ✅ Complete | Matrix proposal, lockfile strategy |

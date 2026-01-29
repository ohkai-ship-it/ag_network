# Findings Backlog — ag_network Hardening
Date: 2026-01-28
Version/commit: v0.2.0

## Priority Definitions
- **P0 (Trust breaker):** correctness, data isolation, security, or misleading behavior.
- **P1 (Important):** performance regressions, reliability risks, maintainability debt.
- **P2 (Nice-to-have):** ergonomics, small refactors, polish.

---

## Backlog Table
| ID | Priority | Area | Problem | Impact | Proposed Fix (smallest safe) | Test/Proof | Owner | Status |
|---:|:--------:|------|---------|--------|-------------------------------|-----------|-------|--------|
| 1 | P0 | Storage | `verify_workspace_id()` never auto-called | Cross-workspace data leakage | Call in `SQLiteManager.__init__` when `workspace_id` provided | `test_sqlite_rejects_wrong_workspace` | — | **Done (PR1)** |
| 2 | P0 | CRM | `CRMStorage` has zero workspace awareness | All CRM data is global/shared | Add `workspace_id` param to constructor | `test_crm_storage_workspace_isolation` | — | **Done (PR1)** |
| 3 | P0 | CRM | `FileCRMAdapter` uses global `CRMStorage()` | CRM operations ignore workspace | Pass workspace context to adapter | `test_file_adapter_uses_workspace_storage` | — | **Done (PR1.1)** |
| 4 | P0 | Kernel | `_persist_claims` uses `SQLiteManager()` | Claims written to wrong DB | Pass `db_path` from `RunContext` | `test_claims_written_to_workspace_db` | — | **Done (PR1)** |
| 5 | P0 | Kernel | `LLMExecutor` fallback uses global DB | Skill results in wrong workspace | Remove fallback; require explicit path | `test_llm_executor_respects_workspace` | — | **Done (PR1)** |
| 6 | P0 | Tools | `SourceIngestor` uses `SQLiteManager()` | Ingested sources in wrong DB | Accept `db_path` in constructor | `test_ingest_writes_to_workspace_db` | — | **Done (PR1)** |
| 7 | P0 | CLI | `status` uses global `runs_dir` | Shows runs from wrong workspace | Use `get_workspace_context(ctx).runs_dir` | `test_status_shows_only_workspace_runs` | — | **Done (PR2)** |
| 8 | P0 | CLI | CRM commands use global storage | Cross-workspace CRM leakage | Use workspace-aware storage | `test_crm_commands_respect_workspace` | — | **Done (PR3)** |
| 9 | P0 | CLI | `sequence plan` uses global `runs_dir` | Plans in wrong location | Use `get_workspace_context(ctx)` | `test_sequence_plan_respects_workspace` | — | **Done (PR2)** |
| 10 | P0 | CLI | `research` passes no `db_path` | Sources in global DB | Pass `ctx.obj["workspace"].db_path` | `test_research_command_workspace_isolation` | — | **Done (PR2)** |
| 11 | P1 | CLI | Misleading output labels | User confusion about LLM vs deterministic | Add `[LLM]`/`[cached]` prefixes | `test_cli_labels_truthfulness.py` | — | **Done (PR4)** |
| 12 | P1 | Storage | FTS index not workspace-scoped | Search may return cross-workspace | Add workspace filter to FTS queries | `test_pr5_fts_workspace_scoping.py` | — | **Done (PR5)** |
| 13 | P2 | CLI | `cli.py` is 2360 lines | Hard to maintain | Split into submodules per command group | — | — | **Done (PR6)** |

---

## P0 — Trust Breakers
### 1) `verify_workspace_id()` is dead code
- **Where:** `src/agnetwork/storage/sqlite.py:445` (defined), line 93 (not called)
- **Symptom:** Opening DB with wrong workspace_id succeeds silently
- **Root cause hypothesis:** Guard was implemented but never wired into constructor
- **Fix:** Add `if workspace_id: verify_workspace_id(self.conn, workspace_id)` in `__init__`
- **Test/Proof:** `test_sqlite_rejects_wrong_workspace` — pass wrong workspace_id, expect exception
- **Risk/Notes:** Breaking change if any code relies on silent fallback; add migration path

### 2) `CRMStorage` has no workspace concept
- **Where:** `src/agnetwork/crm/storage.py` — entire file
- **Symptom:** All CRM data (contacts, companies, interactions) is globally shared
- **Root cause hypothesis:** CRM module developed before workspace system existed
- **Fix:** Add `workspace_id` parameter to `CRMStorage.__init__`, filter all queries
- **Test/Proof:** `test_crm_storage_workspace_isolation` — create contact in ws1, verify invisible in ws2
- **Risk/Notes:** Requires schema migration to add `workspace_id` column to CRM tables

### 3) `FileCRMAdapter` uses global storage
- **Where:** `src/agnetwork/crm/adapters/file_adapter.py:68`
- **Symptom:** `self.storage = CRMStorage()` — no workspace passed
- **Root cause hypothesis:** Adapter doesn't receive workspace context from caller
- **Fix:** Accept `workspace_context` in adapter constructor, propagate to storage
- **Test/Proof:** `test_file_adapter_uses_workspace_storage`
- **Risk/Notes:** May need to update adapter interface/factory

### 4) `_persist_claims` uses global SQLiteManager
- **Where:** `src/agnetwork/kernel/executor.py:351`
- **Symptom:** `db = SQLiteManager()` — claims may go to wrong workspace DB
- **Root cause hypothesis:** `RunContext` has `workspace_id` but not `db_path`; code takes shortcut
- **Fix:** Derive `db_path` from `RunContext.workspace_id` or add `db_path` to `RunContext`
- **Test/Proof:** `test_claims_written_to_workspace_db` — execute skill, verify claims in correct DB
- **Risk/Notes:** Core execution path; test thoroughly

### 5) `LLMExecutor` fallback uses global DB
- **Where:** `src/agnetwork/kernel/llm_executor.py:829`
- **Symptom:** When no explicit `db_path`, falls back to `SQLiteManager()`
- **Root cause hypothesis:** Defensive coding that became a trap
- **Fix:** Remove fallback; require explicit `db_path` or raise error
- **Test/Proof:** `test_llm_executor_respects_workspace`
- **Risk/Notes:** May surface hidden bugs where callers don't pass path

### 6) `SourceIngestor` uses global DB
- **Where:** `src/agnetwork/tools/ingest.py:20`
- **Symptom:** `self.db = SQLiteManager()` — ingested sources in global DB
- **Root cause hypothesis:** Constructor doesn't accept `db_path`
- **Fix:** Add `db_path` param: `def __init__(self, run_dir, db_path=None)`
- **Test/Proof:** `test_ingest_writes_to_workspace_db`
- **Risk/Notes:** Update all callers (CLI `research` command)

### 7) CLI `status` uses global runs_dir
- **Where:** `src/agnetwork/cli.py:578`
- **Symptom:** Shows runs from all workspaces, not just active one
- **Root cause hypothesis:** Command predates workspace system
- **Fix:** `runs_dir = get_workspace_context(ctx).runs_dir`
- **Test/Proof:** `test_status_shows_only_workspace_runs`
- **Risk/Notes:** Simple fix; low risk

### 8) CLI CRM commands use global storage
- **Where:** `src/agnetwork/cli.py` — CRM command group
- **Symptom:** `crm list`, `crm show` etc. show all contacts regardless of workspace
- **Root cause hypothesis:** CRM storage itself has no workspace; CLI can't fix alone
- **Fix:** Blocked by #2 (CRMStorage workspace awareness)
- **Test/Proof:** `test_crm_commands_respect_workspace`
- **Risk/Notes:** Depends on CRM storage fix first

### 9) CLI `sequence plan` uses global runs_dir
- **Where:** `src/agnetwork/cli.py:1340`
- **Symptom:** Sequence plans stored in wrong workspace
- **Root cause hypothesis:** Copy-paste from other commands
- **Fix:** Use `get_workspace_context(ctx)`
- **Test/Proof:** `test_sequence_plan_respects_workspace`
- **Risk/Notes:** Simple fix

### 10) CLI `research` passes no db_path
- **Where:** `src/agnetwork/cli.py:274`
- **Symptom:** `SourceIngestor(run.run_dir)` — no `db_path` argument
- **Root cause hypothesis:** Ingestor didn't accept `db_path` (see #6)
- **Fix:** After #6 is fixed: `SourceIngestor(run.run_dir, db_path=ctx.obj["workspace"].db_path)`
- **Test/Proof:** `test_research_command_workspace_isolation`
- **Risk/Notes:** Depends on #6

---

## P1 — Important
### 11) Misleading CLI output labels
- **Where:** `src/agnetwork/cli.py` — various commands
- **Symptom:** Labels say "Analyzing..." or "Retrieved" when action is deterministic/generated
- **Root cause hypothesis:** Copy-paste; no style guide for output
- **Fix:** Establish labeling convention: `[LLM]`, `[cached]`, `[fetched]`, `[computed]`
- **Test/Proof:** Manual review; add output snapshot tests
- **Risk/Notes:** Low risk; UX improvement

### 12) FTS index not workspace-scoped
- **Where:** `src/agnetwork/storage/sqlite.py` — FTS5 queries
- **Symptom:** Full-text search may return results from other workspaces
- **Root cause hypothesis:** FTS queries don't include `workspace_id` filter
- **Fix:** Add `WHERE workspace_id = ?` to all FTS queries
- **Test/Proof:** `test_fts_search_respects_workspace_boundary`
- **Risk/Notes:** Need to verify FTS table has workspace_id column

---

## P2 — Nice-to-have
### 13) CLI file is too large (2360 lines)
- **Where:** `src/agnetwork/cli.py`
- **Symptom:** Hard to navigate; high cognitive load
- **Root cause hypothesis:** Organic growth without refactoring
- **Fix:** Split into `cli/bd.py`, `cli/crm.py`, `cli/workspace.py`, etc.
- **Test/Proof:** —
- **Risk/Notes:** Refactor only; no functional change

---

## “Next Sprint” Candidate Set
Pick 5–10 items max.

**Recommended fix order** (dependencies considered):

- [ ] ID 1 — `verify_workspace_id()` auto-call in `SQLiteManager.__init__` ← **Foundation fix**
- [ ] ID 2 — `CRMStorage` workspace awareness ← **Unblocks ID 3, 8**
- [ ] ID 6 — `SourceIngestor` accept `db_path` ← **Unblocks ID 10**
- [ ] ID 4 — `_persist_claims` use workspace DB
- [ ] ID 5 — `LLMExecutor` require explicit `db_path`
- [ ] ID 7 — CLI `status` use workspace `runs_dir`
- [ ] ID 9 — CLI `sequence plan` use workspace
- [ ] ID 3 — `FileCRMAdapter` propagate workspace (after ID 2)
- [ ] ID 8 — CLI CRM commands (after ID 2)
- [ ] ID 10 — CLI `research` pass `db_path` (after ID 6)

---

## Change Log
- 2026-01-28: Created backlog with 10 P0, 2 P1, 1 P2 issues from modules 1-5 review
- 2026-01-28: Prioritized "Next Sprint" set with dependency ordering

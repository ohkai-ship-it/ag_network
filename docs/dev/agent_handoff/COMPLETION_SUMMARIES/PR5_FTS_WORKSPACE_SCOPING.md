# PR5 Completion Summary — FTS Workspace Scoping

**Date:** 2026-01-29  
**Backlog ID:** #12 (P1)  
**Status:** ✅ Complete

---

## Problem Statement

FTS (Full-Text Search) queries in `search_sources_fts` and `search_artifacts_fts` had no workspace filter. While the system already isolates workspaces by separate database files, there was no defensive filter to prevent cross-workspace results if the same DB was somehow shared or the workspace_meta was tampered with.

---

## Solution

### 1. Defensive Workspace Filter in FTS Queries

Added `EXISTS` check against `workspace_meta` table in both FTS search methods:

**Before (search_sources_fts):**
```sql
SELECT ...
FROM sources_fts
JOIN sources s ON sources_fts.source_id = s.id
WHERE sources_fts MATCH ?
ORDER BY score
LIMIT ?
```

**After (search_sources_fts):**
```sql
SELECT ...
FROM sources_fts
JOIN sources s ON sources_fts.source_id = s.id
WHERE sources_fts MATCH ?
  AND EXISTS (
      SELECT 1 FROM workspace_meta
      WHERE workspace_id = ?
  )
ORDER BY score
LIMIT ?
```

Same pattern applied to `search_artifacts_fts`.

### 2. TypeError Guard for Unscoped Access

FTS search methods now raise `TypeError` when called on an unscoped `SQLiteManager` instance:

```python
if self._workspace_id is None:
    raise TypeError(
        "search_sources_fts requires workspace_id. "
        "Use SQLiteManager(db_path, workspace_id=...) or for_workspace(ws_ctx)."
    )
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/agnetwork/storage/sqlite.py` | Added EXISTS workspace filter + TypeError guard to `search_sources_fts` and `search_artifacts_fts` |
| `tests/test_pr5_fts_workspace_scoping.py` | **New:** 16 tests covering FTS workspace isolation |
| `tests/test_memory.py` | Updated fixtures to use workspace_id (PR5 compliance) |
| `docs/dev/reviews/FINDINGS_BACKLOG.md` | Marked #12 as Done (PR5) |

---

## FTS Tables Found

| Table | Type | Indexed Content |
|-------|------|-----------------|
| `sources_fts` | FTS5 virtual table | source_id, title, uri, content |
| `artifacts_fts` | FTS5 virtual table | artifact_id, name, artifact_type, content |

Note: These are standalone FTS5 tables (not external content), synchronized via triggers.

---

## Tests Added

`tests/test_pr5_fts_workspace_scoping.py` — 16 tests across 6 test classes:

### TestFTSRequiresWorkspaceId (4 tests)
- `test_search_sources_fts_raises_on_unscoped` — TypeError when no workspace_id
- `test_search_artifacts_fts_raises_on_unscoped` — TypeError when no workspace_id
- `test_search_sources_fts_works_with_workspace_id` — Normal operation
- `test_search_artifacts_fts_works_with_workspace_id` — Normal operation

### TestFTSDefensiveWorkspaceFilter (2 tests)
- `test_fts_search_returns_nothing_when_workspace_meta_mismatched` — EXISTS check blocks results
- `test_fts_search_succeeds_when_workspace_meta_matches` — EXISTS check allows results

### TestFTSWorkspaceIsolationViaSeparateDBs (1 test)
- `test_separate_workspaces_have_isolated_fts_data` — Separate DBs have no cross-talk

### TestCLIMemorySearchRespectWorkspace (2 tests)
- `test_cli_memory_search_creates_workspace_scoped_db` — Code path creates scoped DB
- `test_cli_memory_search_code_path_uses_workspace_id` — AST check for workspace_id

### TestMemoryAPIRequiresWorkspace (3 tests)
- `test_memory_api_requires_db_path` — TypeError without db_path
- `test_memory_api_requires_workspace_id` — TypeError without workspace_id
- `test_memory_api_for_workspace_binds_correctly` — Factory creates scoped instance

### TestFTSForeignRowsLeakPrevention (2 tests)
- `test_foreign_source_rows_not_returned_by_fts` — Simulated leak blocked
- `test_artifacts_foreign_rows_not_returned_by_fts` — Simulated leak blocked

### TestFTSQueryContainsWorkspaceFilter (2 tests)
- `test_search_sources_fts_has_exists_check` — AST check for EXISTS pattern
- `test_search_artifacts_fts_has_exists_check` — AST check for EXISTS pattern

---

## Test Output

```
561 passed, 1 skipped in 45.16s
```

---

## Performance Impact

Minimal — the `EXISTS (SELECT 1 FROM workspace_meta WHERE workspace_id = ?)` subquery:
- Uses indexed `workspace_id` column
- `workspace_meta` table has exactly 1 row per DB
- Constant-time lookup regardless of FTS result count

---

## Invariants Enforced

1. **FTS search requires workspace_id** — TypeError on unscoped instances
2. **FTS results filtered by workspace_meta** — EXISTS check in SQL
3. **No global fallbacks** — Removed ability to search without workspace context

---

## Remaining Backlog

| ID | Priority | Status |
|---:|:--------:|--------|
| 13 | P2 | Todo — CLI splitting |

All P0 and P1 items are now complete.

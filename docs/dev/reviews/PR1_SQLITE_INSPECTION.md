# PR1: SQLite Storage Inspection Report

**Date:** 2026-01-28  
**Status:** ✅ IMPLEMENTATION COMPLETE  
**Goal:** Enforce workspace isolation at the storage layer

---

## Implementation Summary

PR1 has been fully implemented. All storage components now require explicit workspace context:

### Changes Made

| Component | Change | Status |
|-----------|--------|--------|
| `SQLiteManager.__init__` | Now requires `db_path`, optional `workspace_id` | ✅ |
| `SQLiteManager.for_workspace()` | New factory that auto-verifies workspace | ✅ |
| `CRMStorage.__init__` | Now requires `db_path` | ✅ |
| `CRMStorage.for_workspace()` | New factory | ✅ |
| `MemoryAPI.__init__` | Now requires `db_path` and `workspace_id` | ✅ |
| `MemoryAPI.for_workspace()` | New factory | ✅ |
| `FileCRMAdapter.__init__` | Now requires `storage` (not optional) | ✅ |
| `PipelineMapper.__init__` | Now requires `db` | ✅ |
| `SourceIngestor.__init__` | Now requires `ws_ctx` | ✅ |
| `CRMAdapterFactory.create()` | Auto-creates storage when not provided | ✅ |

### Call Sites Fixed

| File | Function | Fix |
|------|----------|-----|
| `cli.py:274` | research command | `SourceIngestor(run.run_dir, ws_ctx)` |
| `cli.py:284` | research command | `SQLiteManager.for_workspace(ws_ctx)` |
| `kernel/executor.py:351` | `_persist_claims` | Uses `ws_ctx` from context |
| `kernel/llm_executor.py:829` | source loading | Uses `ws_ctx` from context |
| `validate.py:312` | `_validate_claim_evidence` | Optional `ws_ctx` parameter |
| `crm/mapping.py:54` | `PipelineMapper` | Requires `db` parameter |
| `crm/mapping.py:564` | `map_run_to_crm` | Requires `db` parameter |

### Tests Added

New test file: `tests/test_pr1_storage_enforcement.py` with 10 tests:
- `test_sqlite_init_requires_db_path`
- `test_sqlite_for_workspace_factory_creates_instance`
- `test_sqlite_for_workspace_factory_verifies_id`
- `test_sqlite_for_workspace_factory_initializes_new_db`
- `test_sqlite_mismatch_raises_workspace_mismatch_error`
- `test_sqlite_init_with_explicit_db_path_and_workspace_id`
- `test_crm_storage_requires_db_path`
- `test_crm_storage_for_workspace_factory_creates_instance`
- `test_no_parameterless_sqlite_manager_calls_in_src` (AST-based anti-regression)
- `test_no_config_db_path_in_storage_modules`

### Test Results

```
488 passed, 6 failed (pre-existing), 1 skipped
ruff: All checks passed!
```

The 6 failures are **pre-existing** issues unrelated to PR1:
- 5 failures: Manual mode outreach stub missing `variants` field (schema validation)
- 1 failure: openai package not installed

---

## Original Inspection (For Reference)

## Canonical Files

| Component | File |
|-----------|------|
| SQLiteManager | `src/agnetwork/storage/sqlite.py` |
| WorkspaceMismatchError | `src/agnetwork/workspaces/context.py` |
| CRMStorage | `src/agnetwork/crm/storage.py` |

---

## A) SQLiteManager Code Sections

### Class declaration + `__init__` — sqlite.py#L83-L104

```python
class SQLiteManager:
    """Manages SQLite database for entities and traceability.

    Provides CRUD operations for sources, companies, artifacts, and claims.
    Includes FTS5 full-text search support for memory retrieval.

    Supports context manager protocol for automatic cleanup:
        with SQLiteManager(db_path) as db:
            db.add_source(...)
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file. Defaults to config.db_path.
        """
        self.db_path = db_path or config.db_path          # ← GLOBAL FALLBACK
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._closed = False
        self._workspace_id_verified = False  # Track if workspace ID has been verified
        self._init_db()
```

**Issue:** `db_path=None` silently falls back to `config.db_path` — violates workspace isolation.

### Schema init (`_init_db`) — sqlite.py#L142-L156

```python
def _init_db(self) -> None:
    """Initialize database schema including FTS5 tables."""
    with sqlite3.connect(self.db_path) as conn:
        cursor = conn.cursor()

        # Workspace metadata table (M7: workspace isolation guard)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_meta (
                workspace_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                last_accessed TEXT
            )
            """
        )
        # ... more tables follow
```

### Factory Method Status

- ❌ No `for_workspace()` / `from_workspace()` / `open_db()` helper exists
- All call sites must manually pass `db_path` and call `verify_workspace_id()` separately

---

## B) Workspace Guard Code Sections

### `init_workspace_metadata()` — sqlite.py#L388-L430

```python
def init_workspace_metadata(self, workspace_id: str) -> None:
    """Initialize workspace metadata for a new database.

    Args:
        workspace_id: Workspace ID to set

    Raises:
        ValueError: If workspace metadata already exists with different ID
    """
    with sqlite3.connect(self.db_path) as conn:
        cursor = conn.cursor()

        # Check if metadata already exists
        cursor.execute("SELECT workspace_id FROM workspace_meta")
        row = cursor.fetchone()

        if row:
            existing_id = row[0]
            if existing_id != workspace_id:
                raise ValueError(
                    f"Database already initialized with workspace_id {existing_id}, "
                    f"cannot reinitialize with {workspace_id}"
                )
            # Already initialized with correct ID, just update access time
            cursor.execute(
                "UPDATE workspace_meta SET last_accessed = ?",
                (datetime.now(timezone.utc).isoformat(),),
            )
        else:
            # Initialize new workspace metadata
            cursor.execute(
                """
                INSERT INTO workspace_meta (workspace_id, created_at, last_accessed)
                VALUES (?, ?, ?)
                """,
                (workspace_id, datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()),
            )

        conn.commit()
        self._workspace_id_verified = True
```

### `verify_workspace_id()` — sqlite.py#L445-L479

```python
def verify_workspace_id(self, expected_workspace_id: str) -> None:
    """Verify that database workspace ID matches expected ID.

    This is a guard to prevent cross-workspace access.

    Args:
        expected_workspace_id: Expected workspace ID

    Raises:
        WorkspaceMismatchError: If workspace ID doesn't match
    """
    if self._workspace_id_verified:
        return  # Already verified

    actual_id = self.get_workspace_id()

    if actual_id is None:
        # Database not initialized, initialize it now
        self.init_workspace_metadata(expected_workspace_id)
        self._workspace_id_verified = True
        return

    if actual_id != expected_workspace_id:
        from agnetwork.workspaces import WorkspaceMismatchError

        raise WorkspaceMismatchError(expected=expected_workspace_id, actual=actual_id)

    # Update last accessed
    with sqlite3.connect(self.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE workspace_meta SET last_accessed = ?",
            (datetime.now(timezone.utc).isoformat(),),
        )
        conn.commit()

    self._workspace_id_verified = True
```

**Issue:** `verify_workspace_id()` is **never auto-called** in `__init__` — the guard is dead code.

### `WorkspaceMismatchError` — context.py#L129-L145

```python
class WorkspaceMismatchError(Exception):
    """Raised when a workspace ID mismatch is detected."""

    def __init__(self, expected: str, actual: str):
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Workspace mismatch: expected {expected!r}, found {actual!r}. "
            f"Cannot use database from different workspace."
        )
```

---

## C) Call Sites with Global Fallback (P0)

| File | Line | Code | Issue |
|------|------|------|-------|
| `crm/mapping.py` | 54 | `self.db = db or SQLiteManager()` | ❌ Global fallback |
| `kernel/executor.py` | 351 | `db = SQLiteManager()` | ❌ Global fallback |
| `kernel/llm_executor.py` | 829 | `db = SQLiteManager()` | ❌ Global fallback |
| `tools/ingest.py` | 20 | `self.db = SQLiteManager()` | ❌ Global fallback |
| `crm/mapping.py` | 76 | `run_dir = config.runs_dir / run_id` | ❌ Global runs_dir |
| `crm/storage.py` | 47 | `self.db_path = db_path or config.db_path` | ❌ Global fallback |

### OK Call Sites (explicit paths)

| File | Line | Code |
|------|------|------|
| `eval/verifier.py` | 521 | `db = SQLiteManager(db_path=db_path)` |
| `kernel/llm_executor.py` | 826 | `db = SQLiteManager(db_path=ws_ctx.db_path)` |
| `storage/memory.py` | 151 | `self.db = SQLiteManager(db_path)` |

---

## D) Summary of Findings

| Finding | Severity | Status |
|---------|----------|--------|
| `SQLiteManager.__init__` defaults to `config.db_path` | **P0** | ❌ Global fallback |
| `verify_workspace_id()` exists but **never auto-called** in `__init__` | **P0** | ❌ Dead guard |
| No `for_workspace(ws_ctx)` factory exists | P1 | ❌ Missing |
| `CRMStorage` has same pattern (line 47) | **P0** | ❌ Global fallback |
| 4 call sites use `SQLiteManager()` with no args | **P0** | ❌ Isolation violated |

---

## E) Recommended Implementation (PR1)

### Step 1: Add `SQLiteManager.for_workspace(ws_ctx)` factory
- Requires `WorkspaceContext`
- Auto-calls `verify_workspace_id()` in the factory
- Returns properly bound `SQLiteManager`

### Step 2: Make `SQLiteManager.__init__` require explicit `db_path`
- Emit `DeprecationWarning` if `db_path=None`
- Later: raise `TypeError` if no db_path

### Step 3: Add `workspace_id` parameter to `__init__`
- If provided, auto-call `verify_workspace_id()` after initialization

### Step 4: Fix all P0 call sites
- Replace `SQLiteManager()` with `SQLiteManager.for_workspace(ws_ctx)`
- Or pass explicit `db_path` + `workspace_id`

### Tests to Add
1. `test_for_workspace_factory_verifies_id` — factory auto-verifies
2. `test_for_workspace_factory_initializes_new_db` — new DB gets workspace_meta
3. `test_init_without_db_path_warns` — deprecation warning emitted
4. `test_mismatch_in_factory_raises` — opening DB with wrong ws_ctx raises
5. `test_claims_written_to_workspace_db` — claims persist to correct DB

---

## G) Implementation Complete

All P0 findings have been addressed. The storage layer now enforces workspace isolation:

1. ✅ `SQLiteManager` requires explicit `db_path` (no more `config.db_path` fallback)
2. ✅ `for_workspace()` factory auto-verifies workspace ID on creation
3. ✅ `verify_workspace_id()` is now called automatically via factory
4. ✅ All call sites updated to use workspace-scoped patterns
5. ✅ `CRMStorage` follows same pattern
6. ✅ `MemoryAPI` follows same pattern
7. ✅ Anti-regression tests prevent future violations

**PR1 is ready for code review.**

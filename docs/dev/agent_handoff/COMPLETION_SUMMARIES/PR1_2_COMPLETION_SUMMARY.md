# PR1.2 Completion Summary – Minor Hardening & Documentation

**Date:** 2026-01-29  
**Status:** ✅ COMPLETE  
**Gate:** `ruff check .` ✅ | `pytest` 499 passed, 1 skipped ✅

---

## Sign-Off

| Reviewer | Date | Signature |
|----------|------|-----------|
| __________ | ____/____/____ | __________ |

---

## Summary

PR1.2 adds minor hardening and documentation updates to lock the long-term contract:
- **Workspace context is the production path**
- **Env vars are dev/legacy overrides only**

No runtime behavior changes for workspace-aware commands.

---

## Changes Made

### 1) Documentation: ARCHITECTURE.md

**Location:** Appendix B: Configuration Reference → B.1 Environment Variables

**A) Updated env var tables:**

| Variable | Status Change |
|----------|---------------|
| `AG_DB_PATH` | Marked **"Legacy/dev only"** |
| `AG_RUNS_DIR` | Marked **"Legacy/dev only"** |
| `AG_CRM_PATH` | Marked **"Dev override only"**, must be a directory |

Added notes:
- Workspace-aware commands MUST use `ws_ctx.db_path` and `ws_ctx.runs_dir`
- `AG_CRM_PATH` is for file adapter export/import directory only
- Stable/multi-user deployments MUST use workspace-scoped storage

**B) Added "Configuration Precedence & Stability Policy" section:**

```
Precedence (highest → lowest):
1. workspace.toml paths (runs, db, exports)
2. CLI flags / explicit ws_ctx injection
3. Dev-only env overrides (AG_CRM_PATH, AG_DB_PATH, AG_RUNS_DIR)
4. Hardcoded defaults (used only when creating a workspace / dev tools)

Stability contract:
- Once declared "stable", config/env var meanings become a contract
- Non-disposable DB implies schema versioning + migrations
- Workspace isolation remains non-negotiable; global fallbacks stay forbidden
```

---

### 2) AST Test: Forbid `unscoped()` in Production Code

**File:** `tests/test_pr1_storage_enforcement.py`

**New test:** `test_no_unscoped_calls_in_src`

```python
def test_no_unscoped_calls_in_src(self):
    """Ensure SQLiteManager.unscoped() is never called in production code."""
    src_dir = Path(__file__).parent.parent / "src" / "agnetwork"
    
    for py_file in src_dir.rglob("*.py"):
        # Allowlist: migrations module only
        if "migrations" in py_file.parts:
            continue
        
        # Scan AST for unscoped() calls
        for node in ast.walk(tree):
            if _is_unscoped_call(node):
                violations.append(...)
```

**Enforcement:**
- Scans `src/agnetwork/**/*.py` only
- Allowlist: `migrations/` module (if it ever exists)
- Fails if `SQLiteManager.unscoped()` found in production code

---

### 3) CRM Factory: Directory Semantics for `AG_CRM_PATH`

**File:** `src/agnetwork/crm/registry.py`

**`from_env()` changes:**

| Condition | Behavior |
|-----------|----------|
| `AG_CRM_PATH` missing | `TypeError: "Dev-only: set AG_CRM_PATH (dir) or use workspace-scoped..."` |
| `AG_CRM_PATH` is a file | `TypeError: "AG_CRM_PATH must be a directory, not a file"` |
| `AG_CRM_PATH` is a directory | Creates adapter with `base_path=<dir>`, storage at `<dir>/crm.db` |
| Directory doesn't exist | Creates it automatically |

**Logging:** Debug message warns that `AG_CRM_PATH` is a dev override.

---

### 4) CRM Tests Added

**File:** `tests/test_crm_registry.py`

| Test | Purpose |
|------|---------|
| `test_from_env_rejects_file_path` | AG_CRM_PATH pointing to file → TypeError |
| `test_from_env_accepts_directory` | AG_CRM_PATH directory → adapter with correct base_path |
| `test_from_env_creates_directory_if_missing` | Missing directory → created automatically |

---

## Files Changed

```
docs/ARCHITECTURE.md                      # Config precedence + env var status
src/agnetwork/crm/registry.py             # from_env directory semantics
tests/test_pr1_storage_enforcement.py     # Forbid unscoped() in src/
tests/test_crm_registry.py                # Directory semantics tests
```

---

## Acceptance Criteria

- [x] ARCHITECTURE.md updated with config precedence + stability policy
- [x] Env vars marked as legacy/dev-only in documentation
- [x] AST test prevents `SQLiteManager.unscoped()` in `src/agnetwork/**`
- [x] `from_env()` rejects file paths for AG_CRM_PATH
- [x] `from_env()` accepts and creates directories for AG_CRM_PATH
- [x] No runtime behavior changes for workspace-aware commands
- [x] `ruff check .` passes
- [x] All 499 tests pass (1 skipped: Anthropic API key)

---

## What's Next

PR1 series complete. The codebase now has:
- **PR1:** Workspace isolation foundation
- **PR1.1:** Guard hardening (workspace_id required, no global fallbacks)
- **PR1.2:** Documentation + enforcement (config precedence locked, unscoped banned in src/)

Ready to proceed to **PR2**.

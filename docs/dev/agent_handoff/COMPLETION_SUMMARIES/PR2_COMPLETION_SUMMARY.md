# PR2 Completion Summary — CLI Workspace Path Leaks

**Date:** 2026-01-28  
**Scope:** Fix remaining P0 CLI workspace path leaks (`runs_dir` + `db_path`)  
**Backlog IDs Closed:** #7, #9, #10

---

## Summary

PR2 fixed three CLI commands that were using global paths instead of workspace-scoped paths:

| ID | Command | Problem | Fix |
|----|---------|---------|-----|
| #7 | `status` | Used `config.runs_dir` | Now uses `ws_ctx.runs_dir` |
| #9 | `sequence plan` | Used `config.runs_dir` | Now uses `ws_ctx.runs_dir` |
| #10 | `research` | Was flagged for db_path issue | **Already fixed** in prior PR — uses `ws_ctx` throughout |

---

## Files Changed

### `src/agnetwork/cli.py`

**`status()` function (~line 575):**
```python
# Before
def status():
    runs = sorted(Path(config.runs_dir).glob("*"))
    
# After  
def status(ctx: Context):
    ws_ctx = get_workspace_context(ctx)
    echo(f"[workspace: {ws_ctx.workspace_name}]", fg="cyan")
    runs = sorted(Path(ws_ctx.runs_dir).glob("*"))
```

**`sequence_plan()` function (~line 1309):**
```python
# Before
def sequence_plan(contact_id: str, ...):
    runs_path = Path(config.runs_dir)
    
# After
def sequence_plan(ctx: Context, contact_id: str, ...):
    ws_ctx = get_workspace_context(ctx)
    echo(f"[workspace: {ws_ctx.workspace_name}]", fg="cyan")
    runs_path = Path(ws_ctx.runs_dir)
```

---

## Tests Added

**New file:** `tests/test_pr2_cli_workspace_paths.py` (6 tests)

| Test Class | Test Name | Purpose |
|------------|-----------|---------|
| `TestStatusWorkspaceIsolation` | `test_status_shows_only_workspace_runs` | Status shows only runs in active workspace |
| `TestStatusWorkspaceIsolation` | `test_status_isolation_between_workspaces` | Two workspaces see different runs |
| `TestSequencePlanWorkspaceIsolation` | `test_sequence_plan_uses_workspace_runs_dir` | Sequence plan uses ws_ctx.runs_dir |
| `TestSequencePlanWorkspaceIsolation` | `test_sequence_plan_isolation_between_workspaces` | Two workspaces use different runs_dirs |
| `TestResearchWorkspaceIsolation` | `test_research_uses_workspace_context` | Regression guard for research command |
| `TestNoConfigRunsDirInWorkspaceCommands` | `test_no_config_runs_dir_in_fixed_commands` | AST-based anti-regression test |

---

## Invariants Enforced

1. **No global `runs_dir` in workspace-aware commands** — All workspace-aware CLI commands must use `ws_ctx.runs_dir`, not `config.runs_dir`
2. **Workspace name visibility** — Commands now echo `[workspace: name]` so users know which workspace they're operating on
3. **AST anti-regression** — Test parses CLI source to ensure `status()` and `sequence_plan()` don't reference `config.runs_dir`

---

## Gate Results

```
ruff check .  → All checks passed!
pytest --tb=short -q → 505 passed, 1 skipped in 36.78s
```

The 1 skipped test is `test_llm_adapters.py::test_anthropic_adapter_real_call` (requires `ANTHROPIC_API_KEY`).

---

## Pre-PR2 → Post-PR2 Test Count

| Stage | Tests |
|-------|-------|
| Pre-PR2 | 499 |
| Post-PR2 | 505 |
| **Delta** | **+6** |

---

## Remaining P0 Items

After PR2, the following P0 items remain in FINDINGS_BACKLOG.md:

| ID | Area | Problem |
|----|------|---------|
| 1 | Storage | `verify_workspace_id()` never auto-called |
| 2 | CRM | `CRMStorage` has zero workspace awareness |
| 3 | CRM | `FileCRMAdapter` uses global `CRMStorage()` |
| 4 | Kernel | `_persist_claims` uses `SQLiteManager()` |
| 5 | Kernel | `LLMExecutor` fallback uses global DB |
| 6 | Tools | `SourceIngestor` uses `SQLiteManager()` |
| 8 | CLI | CRM commands use global storage |

---

## Sign-Off

- [x] All 6 new tests pass
- [x] Full suite passes (505 passed, 1 skipped)
- [x] Ruff clean
- [x] FINDINGS_BACKLOG.md updated (#7, #9, #10 marked Done)
- [x] No regressions

**PR2 Complete.** ✅

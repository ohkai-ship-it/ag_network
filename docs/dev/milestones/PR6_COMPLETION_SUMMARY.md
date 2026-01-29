# PR6 Completion Summary — CLI Module Splitting

**PR:** PR6 - CLI Refactor: Split cli.py into submodules
**Backlog ID:** #13
**Priority:** P2 (Nice-to-have)
**Date:** 2026-01-28

## Problem Statement

The monolithic `cli.py` file had grown to ~2000 lines, making it hard to navigate and maintain. Commands for different domains (research, CRM, workspace, etc.) were all in one file.

## Solution Implemented

Split `cli.py` into a `cli/` package with separate modules per command group:

```
src/agnetwork/cli/
├── __init__.py              # Re-exports app for backward compatibility
├── app.py                   # Typer app + workspace helpers (CLIState, resolve_workspace, etc.)
├── commands_research.py     # research, targets, outreach, prep, followup
├── commands_pipeline.py     # status, validate-run, run-pipeline
├── commands_memory.py       # memory rebuild-index, memory search
├── commands_crm.py          # crm export-run, export-latest, import, list, search, stats
├── commands_sequence.py     # sequence plan, list-templates, show-template, templates
├── commands_workspace.py    # workspace create, list, show, set-default, doctor + prefs
└── commands_skills.py       # meeting-summary, status-update, decision-log, weekly-plan, errand-list, travel-outline
```

## Key Design Decisions

1. **Backward Compatibility**: The old import `from agnetwork.cli import app` still works
2. **Entry Point Unchanged**: `pyproject.toml` entry point `ag = "agnetwork.cli:app"` works seamlessly
3. **Module Registration**: Command modules are imported in `__init__.py` to register with the app
4. **Helper Functions Scoped**: Each module contains its own helper functions (e.g., `_discover_and_fetch_deep_links` is in both `commands_research.py` and `commands_pipeline.py`)

## Files Changed

### Created (8 files)
- `src/agnetwork/cli/__init__.py`
- `src/agnetwork/cli/app.py`
- `src/agnetwork/cli/commands_research.py`
- `src/agnetwork/cli/commands_pipeline.py`
- `src/agnetwork/cli/commands_memory.py`
- `src/agnetwork/cli/commands_crm.py`
- `src/agnetwork/cli/commands_sequence.py`
- `src/agnetwork/cli/commands_workspace.py`
- `src/agnetwork/cli/commands_skills.py`

### Deleted (1 file)
- `src/agnetwork/cli.py` (replaced by cli/ package)

### Modified (4 test files)
- `tests/test_cli_refactored.py` - Updated imports
- `tests/test_cli_labels_truthfulness.py` - Updated imports for `_build_mode_label`
- `tests/test_pr2_cli_workspace_paths.py` - Updated AST check paths
- `tests/test_pr3_crm_workspace_isolation.py` - Updated AST check paths
- `tests/test_pr5_fts_workspace_scoping.py` - Updated import for `memory_search`

### Updated Documentation
- `docs/dev/reviews/FINDINGS_BACKLOG.md` - Marked #13 as Done

## Quality Gate

```
ruff check .        # ✅ Passed
pytest -q           # ✅ 561 passed, 1 skipped
```

## Module Line Counts

| Module | Lines | Commands |
|--------|-------|----------|
| app.py | ~110 | (helpers only) |
| commands_research.py | ~370 | 5 commands |
| commands_pipeline.py | ~350 | 3 commands |
| commands_memory.py | ~90 | 2 commands |
| commands_crm.py | ~290 | 6 commands |
| commands_sequence.py | ~220 | 4 commands |
| commands_workspace.py | ~330 | 8 commands |
| commands_skills.py | ~370 | 6 commands |

**Total new CLI package:** ~2130 lines (vs. old 1967-line monolith)
**Overhead:** ~8% from module boilerplate (docstrings, imports)

## Behavior Verification

- All 561 tests pass (no behavior changes)
- CLI entry point `ag --help` works correctly
- All subcommands accessible via original patterns
- Test files updated to import from new module locations

## Notes

- The `_discover_and_fetch_deep_links` helper is duplicated in `commands_research.py` and `commands_pipeline.py` rather than extracted to a shared module — could be refactored further if needed
- Some tests do AST analysis on cli.py; these were updated to check the new module paths

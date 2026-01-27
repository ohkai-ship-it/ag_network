# Pre-existing Lint Issues

**Status: RESOLVED (M6.3)**

All issues documented below have been resolved in M6.3 (Codebase Cleanup & Refactor).

## Summary

| Code | Count | Severity | Status |
|------|-------|----------|--------|
| F821 | 2 | **High** | ✅ FIXED |
| C901 | 3 | Low | ✅ FIXED |
| E402 | 3 | Low | ✅ FIXED |

---

## Resolved Issues

### F821: Undefined name `timezone` in cli.py ✅

**Fixed:** Added `from datetime import timezone` import in the `crm sequence plan` command.

### C901: Function complexity ✅

**Fixed by refactoring:**

| Function | Original Complexity | Resolution |
|----------|---------------------|------------|
| `run_pipeline` | 15 | Extracted helpers: `_resolve_execution_mode`, `_setup_llm_factory`, `_fetch_urls_for_pipeline`, `_print_pipeline_result` |
| `crm_list` | 11 | Extracted helpers: `_render_accounts_list`, `_render_contacts_list`, `_render_activities_list` with dispatch table |
| `_create_activities` | 17 | Extracted methods: `_activity_from_outreach`, `_activity_from_meeting_prep`, `_activity_from_followup`, `_activity_from_research_brief`, `_get_scoped_source_ids` |

### E402: Module imports not at top of file ✅

**Fixed:** Moved `json`, `Path`, and `Dict` imports to top of `sequence.py`.

---

## Verification

```bash
# All lint checks pass:
ruff check .
# All checks passed!

# All tests pass:
pytest -q
# 426 passed, 2 skipped
```

---

## New Tests Added (M6.3)

- `tests/test_cli_refactored.py` - 13 tests for CLI helper functions
- `tests/test_mapping_refactored.py` - 12 tests for mapping helper methods

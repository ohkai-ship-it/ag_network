# CURRENT_STATE

## Branch/Version
- **main:** v0.2.0 (post-hardening)
- **current branch:** pr6-cli-split (to merge)
- **test count:** 561 passed, 1 skipped

## Objective
Hardening phase: workspace isolation, no global fallbacks, truthful CLI labels.

## Completed PRs
| PR | Title | Backlog IDs | Tests Added |
|----|-------|-------------|-------------|
| PR1 | Storage Layer Workspace Enforcement | #1, #2, #4, #5, #6 | +16 |
| PR1.1 | CRM Adapter Workspace Propagation | #3 | +4 |
| PR1.2 | SQLiteManager.unscoped() Ban in src/ | — | +1 |
| PR2 | CLI Workspace Isolation | #7, #9, #10 | +12 |
| PR3 | CRM Workspace Isolation | #2, #3, #8 | +16 |
| PR3.1 | CRMStorage.unscoped() Ban in src/ | — | +1 |
| PR4 | Truthful CLI Labels | #11 | +23 |
| PR5 | FTS Workspace Scoping | #12 | +16 |
| PR6 | CLI Module Splitting | #13 | 0 (refactor) |

## Invariants Enforced
1. ✅ `SQLiteManager` requires `workspace_id` (AST test)
2. ✅ `CRMStorage` requires `workspace_id` (AST test)
3. ✅ No `SQLiteManager.unscoped()` in src/ (AST test)
4. ✅ No `CRMStorage.unscoped()` in src/ (AST test)
5. ✅ CLI labels reflect reality (tests)
6. ✅ FTS search requires `workspace_id` (TypeError test)
7. ✅ FTS queries include workspace filter (EXISTS check)

## Expected Skips
- `test_anthropic_adapter_*` (requires ANTHROPIC_API_KEY)

## Remaining Backlog
**All P0, P1, and P2 items complete.**

## Next Steps
- Hardening phase complete
- All backlog items resolved
- Ready for new feature development or further refactoring

---

## ⚠️ Repository Setup Required

**Enable branch protection on `main`:**
1. Go to GitHub → Settings → Branches → Branch protection rules
2. Add rule for `main`:
   - ✅ Require a pull request before merging
   - ✅ Require status checks to pass (CI)
   - ✅ Require branches to be up to date
3. Save changes

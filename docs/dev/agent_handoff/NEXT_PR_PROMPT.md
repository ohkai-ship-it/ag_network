# NEXT_PR_PROMPT

All P0, P1, and P2 hardening items from the Findings Backlog are complete.

---

## Hardening Phase Complete

The hardening phase has been successfully completed with the following PRs:

| PR | Title | Backlog IDs | Status |
|----|-------|-------------|--------|
| PR1 | Storage Layer Workspace Enforcement | #1, #2, #4, #5, #6 | ✅ |
| PR1.1 | CRM Adapter Workspace Propagation | #3 | ✅ |
| PR1.2 | SQLiteManager.unscoped() Ban in src/ | — | ✅ |
| PR2 | CLI Workspace Isolation | #7, #9, #10 | ✅ |
| PR3 | CRM Workspace Isolation | #2, #3, #8 | ✅ |
| PR3.1 | CRMStorage.unscoped() Ban in src/ | — | ✅ |
| PR4 | Truthful CLI Labels | #11 | ✅ |
| PR5 | FTS Workspace Scoping | #12 | ✅ |
| PR6 | CLI Module Splitting | #13 | ✅ |

## Next Steps

The codebase is now ready for:
1. **Feature Development** — New capabilities and integrations
2. **Performance Optimization** — If needed based on profiling
3. **Additional Refactoring** — Based on team feedback

---

## Template for Future PRs

```markdown
## PR#: Title

You are the Junior Engineer (VS Code + Copilot + Opus). Implement PR#: **Title** (Backlog ID #X, Priority).

### Scope
✅ What to do
❌ What NOT to do

### Invariants
- Must-hold rules

### Steps
1. ...
2. ...

### Tests Required
- test_xxx

### Acceptance Criteria
- [ ] ...
```

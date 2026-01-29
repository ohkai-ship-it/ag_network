---
Sprint: SPRINT-2026-01
Backlog: BI-0002
Branch: chore/github-flow-docs
Type: Completion summary
---

# BI-0002: GitHub Flow Conventions + Repo Hygiene Checklist

## Summary

Implemented BI-0002 by creating comprehensive GitHub flow conventions and repo hygiene documentation. This docs-only PR establishes explicit team workflows for branching, PR sizing, local checks, and documentation organization. No code changes—only new internal engineering docs and a minor `.gitignore` clarification.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `docs/dev/team/github_flow.md` | **New** | Comprehensive GitHub flow guide (branching, PR sizing, preflight checks, CI parity, review process, docs taxonomy, versioning) |
| `docs/dev/team/repo_hygiene_checklist.md` | **New** | Copy-paste friendly checklist for daily workflows (setup, before/after checks, doc placement, no-shortcuts policy) |
| `.gitignore` | **Modified** | Clarified `docs/dev/` comments; added explicit `docs/dev/_local/` entry with explanation |
| `docs/dev/backlog/items/BI-0002-github-flow-conventions.md` | **Modified** | Status: Ready → Done; marked all acceptance criteria complete |
| `docs/dev/backlog/BACKLOG_INDEX.md` | **Modified** | BI-0002 status: Ready → Done |

## Evidence

### Baseline (before changes)
```
ruff: All checks passed!
pytest: 561 passed, 1 skipped in 44.03s
```

### Final (after changes)
```
ruff: All checks passed!
pytest: 561 passed, 1 skipped in 50.83s
```

### Diff Summary
```
.gitignore                           |   6 +-
docs/dev/team/github_flow.md         | 330 +++ (new)
docs/dev/team/repo_hygiene_checklist.md | 290 +++ (new)
docs/dev/backlog/items/BI-0002-...   |  ~15 lines changed
docs/dev/backlog/BACKLOG_INDEX.md    |   1 line changed
```

## Key Conventions Documented

### Branch Naming
```
feature/...  → new functionality
fix/...      → bug fixes
chore/...    → maintenance, docs, refactors
hotfix/...   → urgent production fixes
```

### PR Sizing
- Target ≤400 lines of meaningful diff
- Single logical change per PR
- Split if touching multiple unrelated modules

### Local Preflight Checklist
```
pip install -e ".[dev]"
python -m ruff check .
python -m pytest -q
```

### Docs Taxonomy
| Path | Audience | Purpose |
|------|----------|---------|
| `docs/` | Users | Public API contract |
| `docs/dev/` | Engineers | Internal coordination (force-add) |
| `docs/dev/_local/` | Local | Scratch output (gitignored, never commit) |

## Backlog Items Updated

| ID | Status Change |
|----|---------------|
| BI-0002 | Ready → **Done** |

## Notes / Follow-ups

1. **No CI changes**: This sprint is docs-only; CI pipeline refactors deferred per scope constraints.
2. **Pre-existing deleted file**: `docs/dev/reviews/FINDINGS_BACKLOG.md` appears deleted but is unrelated to this PR (pre-existing state).

## Commit Commands

```powershell
# Stage changes
git add .gitignore
git add docs/dev/team/github_flow.md
git add docs/dev/team/repo_hygiene_checklist.md
git add docs/dev/backlog/items/BI-0002-github-flow-conventions.md
git add docs/dev/backlog/BACKLOG_INDEX.md
git add docs/dev/agent_handoff/COMPLETION_SUMMARIES/SPRINT-2026-01_BI-0002_completion.md

# Commit
git commit -m "chore(docs): add GitHub flow conventions and repo hygiene checklist (BI-0002)"
```

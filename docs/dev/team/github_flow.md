# GitHub Flow Conventions

> **Purpose**: Step-by-step guide for contributing to `ag-network`, covering branching, PR sizing, local checks, and CI parity.  
> **Audience**: All contributors (human or AI agent).  
> **Last Updated**: January 2026 (Sprint SPRINT-2026-01)

---

## Table of Contents

1. [Branch Naming](#1-branch-naming)
2. [PR Sizing Rules](#2-pr-sizing-rules)
3. [Local Preflight Checklist](#3-local-preflight-checklist)
4. [CI Parity Expectations](#4-ci-parity-expectations)
5. [Review Process](#5-review-process)
6. [Docs Taxonomy](#6-docs-taxonomy)
7. [Scratch Output and _local/](#7-scratch-output-and-_local)
8. [Release Notes and Versioning](#8-release-notes-and-versioning)

---

## 1. Branch Naming

Use a **prefix/** pattern that indicates the type of change:

| Prefix | Use When | Example |
|--------|----------|---------|
| `feature/` | Adding new functionality | `feature/crm-hubspot-adapter` |
| `fix/` | Fixing a bug | `fix/workspace-isolation-leak` |
| `chore/` | Maintenance, docs, refactors (no user-facing change) | `chore/github-flow-docs` |
| `hotfix/` | Urgent production fix (rare) | `hotfix/cli-crash-on-empty-input` |

### Rules

1. **Lowercase, hyphen-separated**: `feature/add-crm-export` (not `Feature/AddCrmExport`)
2. **Short but descriptive**: convey the intent in 3–5 words
3. **No spaces or special characters** except hyphens

### Examples

```bash
# Good
git checkout -b feature/research-skill-caching
git checkout -b fix/fts5-query-escaping
git checkout -b chore/update-readme

# Bad
git checkout -b "feature/Add New CRM Module"   # spaces, capitals
git checkout -b stuff                           # too vague
git checkout -b feature/add_new_crm_module      # underscores (prefer hyphens)
```

---

## 2. PR Sizing Rules

### What is "PR-Sized"?

A PR should be **small enough to review in one session** (~30 min or less). Aim for:

- **≤ 400 lines** of meaningful diff (excluding auto-generated files, lock files)
- **Single logical change**: one feature, one fix, one refactor
- **Clear commit message**: summarizes what + why

### When to Split a PR

| Scenario | Action |
|----------|--------|
| Feature touches multiple unrelated modules | Split by module |
| Large refactor with many files | Ship prep/cleanup first, then the core change |
| New feature + new tests + doc updates | Usually OK together if focused |
| Migration + new functionality | Ship migration first, then feature |

### Splitting Example

Bad (too large):
```
PR #42: "Add CRM integration, update CLI, refactor storage, add tests, fix 3 bugs"
```

Good (split into):
```
PR #42: "chore: refactor storage module for CRM prep"
PR #43: "feature: add FileCRMAdapter with tests"
PR #44: "feature: add CLI commands for CRM import/export"
PR #45: "fix: resolve 3 CRM-related bugs found in testing"
```

---

## 3. Local Preflight Checklist

Before pushing any PR, run these checks locally. This ensures CI won't fail on trivial issues.

### 3.1 Setup (One-Time)

```powershell
# Clone and enter repo
git clone https://github.com/<org>/ag-network.git
cd ag-network

# Create virtual environment (recommended)
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell
# or: source .venv/bin/activate   # macOS/Linux

# Install with dev dependencies
pip install -e ".[dev]"
```

### 3.2 Before Every PR

```powershell
# 1. Install fresh (catches missing deps)
pip install -e ".[dev]"

# 2. Lint check
python -m ruff check .

# Expected: "All checks passed!"
# If issues: `python -m ruff check . --fix` for auto-fixable

# 3. Run tests (offline mode)
python -m pytest -q

# Expected: All pass, some may skip (provider tests skip cleanly when offline)
# If failures: fix root cause—do NOT disable tests
```

### 3.3 What "Offline" Means

- Tests run without network calls to external providers (OpenAI, Anthropic, web)
- Provider-dependent tests are **skipped** (not failed) when credentials absent
- The `FakeLLM` adapter enables deterministic testing without real API calls

### 3.4 Quick Checklist (Copy-Paste Ready)

```
[ ] pip install -e ".[dev]"
[ ] python -m ruff check .   → "All checks passed!"
[ ] python -m pytest -q      → all pass (some skipped is OK)
[ ] git status               → only expected files changed
```

---

## 4. CI Parity Expectations

### What CI Runs

CI (GitHub Actions) runs the same checks you run locally:

| Check | Local Command | CI Equivalent |
|-------|---------------|---------------|
| Lint | `python -m ruff check .` | Same |
| Tests | `python -m pytest -q` | Same (offline, no secrets) |
| Type check | `python -m mypy src/` | (Optional, may be added later) |

### Why Parity Matters

- If local passes but CI fails → environment mismatch (report as bug)
- If CI passes but local fails → your environment is stale (`pip install -e ".[dev]"`)
- Tests must pass **offline** (no external API keys in CI)

### Provider Tests

- Tests that require real LLM calls are **marked to skip** when credentials are missing
- CI does not have provider keys → these tests skip cleanly
- You can run them locally with `AG_ANTHROPIC_API_KEY=... pytest` (optional)

---

## 5. Review Process

### Who Reviews What

| PR Type | Reviewer | Notes |
|---------|----------|-------|
| Code changes (kernel, storage, CLI) | Senior engineer or project lead | Focus on invariants |
| Docs-only changes | Any team member | Check accuracy, clarity |
| Backlog/process changes | Project lead | Ensure alignment with sprint goals |

### How to Request Review

1. Push branch, open PR on GitHub
2. Fill in PR template (if provided)
3. Link to backlog item (e.g., "Implements BI-0002")
4. Add completion summary or checklist in PR description

### Attaching Evidence

For non-trivial changes, include evidence:

```markdown
## Evidence

- ruff: `All checks passed!`
- pytest: `561 passed, 1 skipped in 44.03s`
- Manual test: ran `ag research "Acme Corp"` → output as expected

## Files Changed
- `docs/dev/team/github_flow.md` (new)
- `docs/dev/team/repo_hygiene_checklist.md` (new)
- `.gitignore` (updated)
```

### Review Checklist (for Reviewers)

```
[ ] PR scope matches backlog item / issue
[ ] No unrelated changes snuck in
[ ] Tests pass (CI green or local evidence)
[ ] Docs updated if user-facing behavior changed
[ ] No new shortcuts (disabled tests, suppressed warnings)
[ ] Invariants preserved (workspace isolation, truthful labeling)
```

---

## 6. Docs Taxonomy

### Two Documentation Roots

| Path | Audience | Content | Committed? |
|------|----------|---------|------------|
| `docs/` | **Users** (external) | Architecture, CLI reference, guides | Yes (public contract) |
| `docs/dev/` | **Engineers** (internal) | Sprints, reviews, handoffs, backlog | Yes |

### Why the Split?

- `docs/` = the **public API contract**; changes here affect user expectations
- `docs/dev/` = **internal coordination**; noisy but essential for continuity

### Directory Structure

```
docs/
├── ARCHITECTURE.md          # High-level design (user-facing)
├── CLI_REFERENCE.md         # Command reference (user-facing)
└── dev/                     # Internal engineering docs
    ├── agent_handoff/       # Multi-agent coordination
    ├── backlog/             # Work items, indexes
    ├── bugs/                # Bug reports, tracking
    ├── reviews/             # Code review notes
    ├── sprints/             # Sprint planning
    ├── team/                # Process docs (this file!)
    └── _local/              # Scratch output (gitignored)
```

### Placement Rules

| Content Type | Location |
|--------------|----------|
| User guides, tutorials | `docs/` |
| API documentation | `docs/` |
| Sprint plans, backlog items | `docs/dev/sprints/`, `docs/dev/backlog/` |
| Code review notes | `docs/dev/reviews/` |
| Agent handoff state | `docs/dev/agent_handoff/` |
| Scratch/temp output | `docs/dev/_local/` |

---

## 7. Scratch Output and _local/

### Purpose

During development, you may generate:

- Debug logs, traces
- Test output artifacts
- Temporary analysis files
- AI-generated drafts before cleanup

### Where to Put It

```
docs/dev/_local/
```

### Why Gitignored?

- Prevents noisy commits
- Keeps repo history clean
- Allows local experimentation without affecting others

### .gitignore Entry

The `.gitignore` includes:

```
# Dev docs (local scratch)
docs/dev/_local/
```

### Example Usage

```powershell
# Generate debug output
python -m pytest --tb=long > docs/dev/_local/pytest_debug.txt

# Save scratch analysis
ag research "Acme Corp" --verbose > docs/dev/_local/acme_debug.json
```

---

## 8. Release Notes and Versioning

### Version Scheme

`ag-network` follows **semantic versioning**: `MAJOR.MINOR.PATCH`

| Version | Meaning |
|---------|---------|
| `0.x.y` | Pre-1.0 development (API may change) |
| `0.2.x` | Current development line |
| `1.0.0` | First stable release (future) |

### How Tags Relate to `main`

- `main` branch = latest development (may be ahead of last tag)
- Tags like `v0.2.0`, `v0.2.1` = snapshot releases
- Each tag should have passing tests

### Release Process (High-Level)

1. Ensure `main` is stable (all checks pass)
2. Update `CHANGELOG.md` with release notes
3. Bump version in `pyproject.toml`
4. Create tag: `git tag v0.2.1`
5. Push tag: `git push origin v0.2.1`

### What Goes in CHANGELOG?

```markdown
## [0.2.1] - 2026-01-29

### Added
- GitHub flow conventions doc (BI-0002)

### Fixed
- (none this release)

### Changed
- (none this release)
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Flow Quick Ref                    │
├─────────────────────────────────────────────────────────────┤
│ Branch:   feature/…  fix/…  chore/…  hotfix/…              │
│ PR size:  ≤400 lines, single logical change                │
│                                                             │
│ Before push:                                                │
│   pip install -e ".[dev]"                                  │
│   python -m ruff check .                                   │
│   python -m pytest -q                                      │
│                                                             │
│ Docs:                                                       │
│   docs/        → user-facing (public)                      │
│   docs/dev/    → internal (engineering)                    │
│   docs/dev/_local/ → scratch (gitignored)                  │
│                                                             │
│ Golden rule: Fix root cause, never disable checks.         │
└─────────────────────────────────────────────────────────────┘
```

---

## Related Documents

- [repo_hygiene_checklist.md](repo_hygiene_checklist.md) — Practical checklist for daily use
- [BACKLOG_INDEX.md](../backlog/BACKLOG_INDEX.md) — Work item tracking
- [ARCHITECTURE.md](../../ARCHITECTURE.md) — System design overview

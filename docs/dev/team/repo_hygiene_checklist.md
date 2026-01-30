# Repo Hygiene Checklist

> **Purpose**: Copy-paste checklist for daily development workflow.  
> **Companion to**: [github_flow.md](github_flow.md)  
> **Last Updated**: January 2026 (Sprint SPRINT-2026-01)

---

## Quick Start Checklist

Use this before starting any work session:

```
┌─────────────────────────────────────────────────────────────┐
│                 REPO HYGIENE CHECKLIST                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  SETUP (once per machine / after clone)                    │
│  [ ] git clone <repo>                                      │
│  [ ] cd <repo-folder>                                      │
│  [ ] python -m venv .venv                                  │
│  [ ] .venv\Scripts\Activate.ps1  (or source on Unix)      │
│  [ ] pip install -e ".[dev]"                               │
│                                                             │
│  BEFORE CHANGES                                             │
│  [ ] git checkout main && git pull                         │
│  [ ] git checkout -b <prefix>/<description>                │
│  [ ] pip install -e ".[dev]"  (refresh deps)              │
│  [ ] python -m ruff check .   → "All checks passed!"      │
│  [ ] python -m pytest -q      → all pass                  │
│                                                             │
│  AFTER CHANGES                                              │
│  [ ] python -m ruff check .   → still passing             │
│  [ ] python -m pytest -q      → still passing             │
│  [ ] git status               → only expected files       │
│  [ ] git diff --stat          → reasonable diff size      │
│                                                             │
│  BEFORE MERGE                                               │
│  [ ] PR description complete                               │
│  [ ] Evidence attached (ruff/pytest output)               │
│  [ ] Backlog item updated (if applicable)                 │
│  [ ] Completion summary written (for non-trivial PRs)     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Repo Setup

### First-Time Setup

```powershell
# Clone repository
git clone https://github.com/<org>/<repo>.git
cd <repo-folder>

# Create isolated virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate (macOS/Linux)
# source .venv/bin/activate

# Install package with dev dependencies
pip install -e ".[dev]"

# Verify installation
python -c "import agnetwork; print(agnetwork.__version__)"
```

### After Each Pull

```powershell
git pull origin main
pip install -e ".[dev]"   # Refresh deps (they may have changed)
```

---

## 2. Before/After Checks

### Before Making Changes

```powershell
# Ensure clean baseline
python -m ruff check .     # Lint
python -m pytest -q        # Tests (offline)
```

**Expected**:
- Ruff: `All checks passed!`
- Pytest: `XXX passed, Y skipped` (no failures)

> **Provider tests**: If a provider test *fails* instead of skipping, file a bug (P1)—do not add API keys to CI.

### After Making Changes

Run the same checks again:

```powershell
python -m ruff check .
python -m pytest -q
```

If something fails:
1. **Fix the root cause** (don't disable the check)
2. If it's a pre-existing issue, file a bug and proceed (don't make it worse)

---

## 3. Doc Placement Rules

### Where Does This Doc Go?

| Type of Content | Location | Committed? |
|-----------------|----------|------------|
| **User guides, API docs** | `docs/` | ✅ Yes |
| **Architecture overview** | `docs/ARCHITECTURE.md` | ✅ Yes |
| **CLI reference** | `docs/CLI_REFERENCE.md` | ✅ Yes |
| **Sprint planning** | `docs/dev/sprints/` | ✅ Yes |
| **Backlog items** | `docs/dev/backlog/items/` | ✅ Yes |
| **Bug reports** | `docs/dev/bugs/reports/` | ✅ Yes |
| **Code review notes** | `docs/dev/reviews/` | ✅ Yes |
| **Agent handoff state** | `docs/dev/agent_handoff/` | ✅ Yes |
| **Process docs (this!)** | `docs/dev/team/` | ✅ Yes |
| **Scratch/debug output** | `docs/dev/_local/` | ❌ No (gitignored) |

### What's Gitignored?

Only `docs/dev/_local/` is gitignored. All other `docs/dev/` content (backlog, sprints, handoffs, team docs) commits normally—no `git add -f` needed.

### Never Commit to _local/

The `docs/dev/_local/` directory is for:
- Debug logs
- Scratch analysis
- Temporary outputs

It is gitignored. Do not force-add anything from `_local/`.

---

## 4. "No Shortcuts" Policy

### What Counts as a Shortcut?

| ❌ Shortcut | ✅ Correct Approach |
|-------------|---------------------|
| Adding `# noqa` to silence lint | Fix the lint issue |
| Marking failing test as `@pytest.mark.skip` | Fix the test or underlying code |
| Adding `--ignore` flags to CI | Fix the root cause |
| Removing a test that fails | Fix the test or explain why it's invalid |
| Hardcoding values to make tests pass | Fix the logic being tested |

### When a Check Fails

1. **Understand why** (read the error message)
2. **Fix the root cause** (not the symptom)
3. **If blocked**: file a bug, document it, ask for help—but don't bypass

### Exceptions

If a check is genuinely wrong (false positive):
1. Document why in a comment
2. Get team agreement
3. Add a targeted suppression with explanation:

```python
# False positive: xyz is used dynamically via __getattr__
xyz = "value"  # noqa: F841
```

---

## 5. When to Update Backlog/Bug Indexes

### Backlog Index (`docs/dev/backlog/BACKLOG_INDEX.md`)

Update when:
- [ ] Starting a backlog item → Status: `In progress`
- [ ] Completing a backlog item → Status: `Done`
- [ ] Blocking on an item → Status: `Blocked`, add note
- [ ] Creating a new backlog item → Add row to table

### Bug Index (`docs/dev/bugs/BUG_INDEX.md`)

Update when:
- [ ] Discovering a bug → Create report, add to index
- [ ] Fixing a bug → Update status to `Fixed`, link to PR
- [ ] Deferring a bug → Update status to `Deferred`, add rationale

### Backlog Item Files

Each item in `docs/dev/backlog/items/BI-XXXX-*.md`:
- Update `Status:` field when state changes
- Add implementation notes as you work
- Mark acceptance criteria checkboxes when complete

---

## 6. PR Completion Summaries

### When to Write One

Write a completion summary for:
- [ ] Any PR that closes a backlog item
- [ ] Any non-trivial code change
- [ ] Any change that affects multiple modules

Skip for:
- Typo fixes
- Single-line changes
- Pure formatting

### What to Include

```markdown
# PR<N>: <title>

## Summary
What changed and why (2-3 sentences).

## Files Changed
- `path/to/file.py` — description of change
- `path/to/doc.md` — new/updated

## Evidence
- ruff: `All checks passed!`
- pytest: `XXX passed, Y skipped in ZZs`
- Manual test: (if applicable)

## Backlog Items
- BI-XXXX: Status → Done

## Notes / Follow-ups
- (Any loose ends or related future work)
```

### Where to Put It

```
docs/dev/agent_handoff/COMPLETION_SUMMARIES/SPRINT-YYYY-MM_BI-XXXX_completion.md
```

Example: `SPRINT-2026-01_BI-0002_completion.md`

---

## 7. Branch Naming Quick Reference

| Prefix | Use Case | Example |
|--------|----------|---------|
| `feature/` | New functionality | `feature/hubspot-adapter` |
| `fix/` | Bug fix | `fix/fts5-escaping` |
| `chore/` | Maintenance, docs, refactor | `chore/update-deps` |
| `hotfix/` | Urgent production fix | `hotfix/cli-crash` |

---

## 8. Common Commands Reference

```powershell
# === Environment ===
pip install -e ".[dev]"          # Install with dev deps
pip list                          # Check installed packages

# === Linting ===
python -m ruff check .           # Lint check
python -m ruff check . --fix     # Auto-fix lint issues

# === Testing ===
python -m pytest -q              # Quick test run
python -m pytest -v              # Verbose test run
python -m pytest tests/test_kernel.py  # Run specific file
python -m pytest -k "test_name"  # Run tests matching name

# === Git ===
git status                        # Check working tree
git diff --stat                   # Summary of changes
git add docs/dev/...             # Stage internal docs (normal add)
git commit -m "type: description" # Commit with conventional message
git push -u origin branch-name   # Push new branch
```

---

## 9. Invariants to Preserve

Every change must preserve these invariants:

| Invariant | What It Means |
|-----------|---------------|
| **Workspace isolation** | No cross-workspace reads/writes |
| **No silent global fallbacks** | DB/storage/runs paths are explicit |
| **Truthful CLI labeling** | `deterministic` vs `agent`; `retrieved` vs `generated` |
| **Auditability** | Sources/evidence/artifacts are verifiable |
| **LLM-first; deterministic-capable** | Default runtime is `--mode llm`; manual mode for CI/perf/debug; no provider calls in CI |

If your change might affect these, add explicit tests or documentation.

---

## 10. End-of-Session Checklist

Before ending a work session:

```
[ ] All changes committed (or stashed)
[ ] Branch pushed to remote
[ ] PR opened (if work is complete)
[ ] Backlog item updated
[ ] Completion summary written (if PR-worthy)
[ ] No uncommitted scratch files outside _local/
```

---

## Related Documents

- [github_flow.md](github_flow.md) — Detailed GitHub flow conventions
- [BACKLOG_INDEX.md](../backlog/BACKLOG_INDEX.md) — Work item tracking
- [BUG_INDEX.md](../bugs/BUG_INDEX.md) — Bug tracking

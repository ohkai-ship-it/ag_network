# Release Checklist — v0.2.0

**Release Date**: 2026-01-27  
**Release Type**: Minor (new capabilities)  
**Milestone**: M1-M8 Complete

---

## Pre-Release Checks

### Code Quality

- [x] **ruff check . clean** — All checks passed!
- [x] **pytest clean** — 484 passed, 1 skipped in 34.10s
- [x] **Golden BD run clean** — Pipeline generates all 5 artifacts
- [x] **Workspace isolation tests pass** — Included in test suite

### Documentation

- [x] **README matches `ag --help`** — 19 commands documented
- [x] **Sample runs/artifacts exist** — `test_demo` workspace with von Rundstedt demo
- [x] **CHANGELOG.md updated** — v0.2.0 section added
- [x] **Milestone summaries complete** — M1-M8 completion docs

### Security

- [x] **No secrets committed** — Verified with grep, .env gitignored
- [x] **.env.example exists** — Template for API keys
- [x] **API keys use environment variables** — OPENAI_API_KEY, ANTHROPIC_API_KEY

### Dependencies

- [x] **pyproject.toml dependencies pinned** — Min versions specified
- [x] **Dev install instructions clear** — README Quick Start section
- [x] **Optional extras documented** — `[llm]`, `[dev]`, `[all]`

---

## Version Bump

| File | Before | After |
|------|--------|-------|
| `pyproject.toml` | 0.1.0 | 0.2.0 |
| `src/agnetwork/__init__.py` | 0.1.0 | 0.2.0 |
| `README.md` | v0.1 | v0.2 |

---

## Test Results Summary

```
Platform: Windows 11
Python: 3.14.0
Date: 2026-01-27

ruff check .: All checks passed!
pytest: 484 passed, 1 skipped in 34.10s

LLM Integration Test:
- Provider: OpenAI (gpt-4o)
- Pipeline: Full BD pipeline completed
- Artifacts: 10 files generated
- Claims: 9 persisted
```

---

## Golden Demo Run

**Location**: `C:\Users\Kai\.agnetwork\workspaces\test_demo\runs\20260127_134749__von_rundstedt__pipeline\`

**Command**:
```bash
ag run-pipeline "von Rundstedt" \
  --snapshot "Leading German HR consulting company..." \
  --url "https://www.rundstedt.de/" \
  --pain "Workforce restructuring during economic uncertainty" \
  --trigger "Economic downturn forcing layoffs" \
  --competitor "Korn Ferry" --competitor "LHH" \
  --persona "CHRO" --mode llm --deep-links --deep-links-max 3
```

**Artifacts Generated**:
- research_brief.md/json
- target_map.md/json
- outreach.md/json
- meeting_prep.md/json
- followup.md/json

---

## Git Operations

- [x] **Commits squashed/cleaned** (if needed)
- [x] **Tag created**: `v0.2.0`
- [x] **Tag message**: See CHANGELOG.md v0.2.0 section

---

## Post-Release

- [ ] Push tag to origin: `git push origin v0.2.0`
- [ ] Update any external documentation
- [ ] Archive release notes

---

*Checklist completed: 2026-01-27*

# CLI Review Report — SPRINT-2026-01 / BI-0004

> **Date**: 2026-01-30  
> **Reviewer**: Opus 4.5 (Junior Engineer)  
> **Scope**: Truthfulness + UX review (BI-0004)  
> **Branch**: chore/cli-review-bi0004  
> **Baseline**: CLI_REFERENCE.md (docs/CLI_REFERENCE.md)

---

## 1. Command Inventory

### 1.1 Top-Level Commands

| Command | Category | Description | Has `--mode`? |
|---------|----------|-------------|---------------|
| `run-pipeline` | Pipeline | Full BD pipeline (5 artifacts) | ✅ Yes |
| `research` | Research | Account research brief | ❌ No |
| `targets` | Research | Prospect target map | ❌ No |
| `outreach` | Research | Outreach message drafts | ❌ No |
| `prep` | Research | Meeting preparation pack | ❌ No |
| `followup` | Research | Post-meeting follow-up | ❌ No |
| `status` | Pipeline | Show recent runs | N/A |
| `validate-run` | Pipeline | Validate run integrity | N/A |

### 1.2 Subcommand Groups

| Group | Commands | Status |
|-------|----------|--------|
| `workspace` | create, list, show, set-default, doctor | ✅ Complete |
| `prefs` | show, set, reset | ✅ Complete |
| `crm` | export-run, export-latest, import, list, search, stats | ✅ Complete |
| `memory` | rebuild-index, search | ✅ Complete |
| `sequence` | plan, list-templates, show-template | ✅ Complete |

### 1.3 Work/Personal Ops Skills

| Command | Description |
|---------|-------------|
| `meeting-summary` | Generate meeting summary |
| `status-update` | Generate status report |
| `decision-log` | Generate ADR-style log |
| `weekly-plan` | Generate weekly plan |
| `errand-list` | Generate errand list |
| `travel-outline` | Generate travel itinerary |

---

## 2. Truthfulness Check

### 2.1 Label Infrastructure

| Label | Implemented | Used Correctly? |
|-------|-------------|-----------------|
| `[LLM]` | ✅ `cli_labels.py` | ⚠️ Partial — see CLI-001 |
| `[computed]` | ✅ `cli_labels.py` | ⚠️ Misused — see CLI-001 |
| `[placeholder]` | ✅ `cli_labels.py` | ✅ Correct |
| `[fetched]` | ✅ `cli_labels.py` | ✅ Correct |
| `[cached]` | ✅ `cli_labels.py` | ✅ Correct |
| `[FTS]` | ✅ `cli_labels.py` | ✅ Correct |

### 2.2 Truthfulness Findings

#### CLI-001 (P1): Misleading `[computed]` label in research command

**Status**: ⚠️ CONFIRMED TRUTHFULNESS VIOLATION → **BUG-0002 filed**

**Evidence**: `commands_research.py:153`
```python
typer.echo(f"🔍 [computed] Starting research run for {company}...")
```

This line prints `[computed]` regardless of whether:
- LLM mode is used (via environment or configuration)
- The subsequent skill execution uses LLM

**Impact**: Users cannot trust the label to distinguish LLM-generated vs deterministic output.

**Root Cause**: The `research` command lacks a `--mode` flag unlike `run-pipeline`. It appears to always run in manual mode, but the label is hardcoded rather than derived from actual execution mode.

**Fix Required**: Per **DECISION-0004**, add `--mode` flag and use `get_mode_labels()`.

> **Open question**: We must confirm whether `research` can ever call an LLM via `AG_LLM_ENABLED` defaults in the kernel/skill layer, even without `--mode`. If yes, CLI-001 is a shipped bug; if no, the hardcoded label is merely misleading (still P1 for truthfulness).

#### CLI-008 (P1): Missing `--mode` flag in CLI commands

**Status**: ✅ DECISION MADE → **DECISION-0004**, **BI-0014 (P1)**

Per DECISION-0004: "All CLI commands that generate content must implement `--mode {manual,llm}` with consistent help and defaults."

**Evidence**: `ag research --help` shows no `--mode` flag, unlike `ag run-pipeline --help`.

**Scope**: All top-level commands that generate content:
- Research commands: `research`, `targets`, `outreach`, `prep`, `followup`
- Work ops skills: `meeting-summary`, `status-update`, `decision-log`, etc.

**Tracked by**: BI-0014 (P1)

---

## 3. Documentation Drift

### 3.1 CLI_REFERENCE.md vs Actual CLI

| Item | Documented | Actual | Status |
|------|------------|--------|--------|
| `research --snapshot` | Optional | **Required** | ⚠️ DOC DRIFT |
| `research` has `--mode` | Not documented | Not implemented | ✅ Consistent |
| `run-pipeline --mode` | Documented | Implemented | ✅ Consistent |
| `validate-run -m` | Documented | Implemented | ✅ Consistent |
| `workspace doctor` | Documented | Implemented | ✅ Consistent |

### 3.2 Documentation Issue

#### CLI-009 (P2): `research --snapshot` documented as optional but is required

**Evidence**: 
- CLI_REFERENCE.md shows `--snapshot` as optional: `ag research "Acme Corp" --snapshot "Enterprise SaaS platform"`
- Actual CLI shows: `*  --snapshot         -s                     TEXT     Company snapshot/description [required]`

**Fix**: Update CLI_REFERENCE.md to mark `--snapshot` as required.

---

## 4. UX Consistency Check

### 4.1 Help Text Quality

| Command | Docstring | Examples | Detail Level |
|---------|-----------|----------|--------------|
| `run-pipeline` | ✅ Detailed | ✅ In docstring | High |
| `research` | ⚠️ One-liner | ❌ None | Low |
| `targets` | ⚠️ One-liner | ❌ None | Low |
| `workspace create` | ✅ Good | ❌ None | Medium |
| `memory search` | ⚠️ One-liner | ❌ None | Low |

### 4.2 Error Message Quality

| Location | Current Error | Suggested Improvement |
|----------|---------------|----------------------|
| `app.py:61-68` | `❌ Workspace not found: {name}` | ✅ Has hint: "Use 'ag workspace list'" |
| `workspace create` | `❌ Error: {e}` | ❌ No recovery hint |
| `validate-run` | `❌ Run path not found` | ❌ No example of valid path |

### 4.3 Output Format Consistency

| Command | Output Format | Uses Rich? |
|---------|---------------|------------|
| `workspace list` | Rich Table | ✅ |
| `workspace show` | Plain text | ❌ |
| `status` | Plain text | ❌ |
| `crm list` | Rich Table | ✅ |
| `memory search` | Plain text | ❌ |

---

## 5. Prioritized Findings

### P1 (Truthfulness / Policy — Must Fix)

| ID | Finding | File | Fix Size | Tracked By |
|----|---------|------|----------|------------|
| CLI-001 | `[computed]` printed regardless of mode | `commands_research.py:153` | S | BUG-0002, BI-0011 |
| CLI-008 | Missing `--mode` in CLI commands | `commands_*.py` | M | BI-0014, DECISION-0004 |

### P2 (UX Consistency — Should Fix)

| ID | Finding | File | Fix Size |
|----|---------|------|----------|
| CLI-009 | Doc drift: `--snapshot` marked optional | `CLI_REFERENCE.md` | S |
| CLI-010 | Mixed output formats (rich vs plain) | Various | M |
| CLI-011 | Inconsistent help text detail | Various | M |
| CLI-012 | Some errors lack recovery hints | Various | S |

### P3 (Nice to Have)

| ID | Finding | File | Fix Size |
|----|---------|------|----------|
| CLI-013 | No shell completion hints in docs | `CLI_REFERENCE.md` | S |

---

## 6. Recommendations (PR-Sized)

### PR #1 (S): Fix CLI-001 truthfulness violation

**Scope**: 
- Audit `commands_research.py` to determine if LLM paths exist
- If yes: add `--mode` flag and use `get_mode_labels()`
- If no: verify and document that research is deterministic-only

**Acceptance Criteria**:
- [ ] `research` command label accurately reflects execution mode
- [ ] Tests verify label correctness
- [ ] No regression in existing functionality

### PR #2 (S): Fix documentation drift

**Scope**:
- Update CLI_REFERENCE.md to mark `research --snapshot` as required
- Add examples to commands lacking them

**Acceptance Criteria**:
- [ ] CLI_REFERENCE.md matches actual CLI behavior
- [ ] All commands have at least one example

### PR #3 (M): Standardize output formats

**Scope**:
- Convert `workspace show`, `status`, `memory search` to rich tables
- Create helper function for consistent table creation

**Acceptance Criteria**:
- [ ] All list/status commands use rich tables
- [ ] Table styles are consistent

### PR #4 (M): Add `--mode` to research commands (if needed)

**Scope** (depends on PR #1 findings):
- Add `--mode` flag to `research`, `targets`, `outreach`, `prep`, `followup`
- Ensure labels reflect actual mode

---

## 7. Related Backlog Items

| BI ID | Relationship |
|-------|--------------|
| BI-0011 | CLI label truthfulness + consistency (includes CLI-001) |
| BI-0012 | CLI progress indicators |

---

## 8. Checklist for Next Review

- [ ] Verify CLI-001 fix is complete
- [ ] Verify documentation matches CLI
- [ ] Check for new commands added since this review
- [ ] Test shell completion functionality

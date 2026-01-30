# BUG-0002 — CLI prints `[computed]` label regardless of actual execution mode

## Metadata
- **ID:** BUG-0002
- **Status:** Open
- **Severity:** P1
- **Area:** CLI / Truthfulness
- **Reporter:** Opus 4.5 (BI-0004 review)
- **Date reported:** 2026-01-30
- **Source:** CLI-001 finding

## Summary

The `research` command (and potentially other commands) prints `[computed]` in its output regardless of whether the underlying execution uses LLM or deterministic mode. This violates the truthfulness invariant.

## Steps to Reproduce

```powershell
# Set LLM enabled (if the kernel respects this)
$env:AG_LLM_ENABLED = "1"

# Run research command
ag research "TestCo" --snapshot "Test company"

# Observe output
# 🔍 [computed] Starting research run for TestCo...
# ^^^ Always says [computed], even if LLM paths are invoked
```

## Expected Behavior

Label should reflect actual execution mode:
- `[computed]` if deterministic/manual mode was used
- `[LLM]` if LLM was invoked

## Actual Behavior

Always prints `[computed]` because the label is hardcoded:

```python
# commands_research.py:153
typer.echo(f"🔍 [computed] Starting research run for {company}...")
```

## Root Cause

1. The `research` command lacks a `--mode` flag
2. The label is hardcoded rather than derived from `get_mode_labels()`
3. It's unclear whether `AG_LLM_ENABLED` affects execution without `--mode`

## Impact

- **Truthfulness violation**: Users cannot trust the label
- **Trust erosion**: If LLM is silently used when labeled `[computed]`, users may share/trust output they shouldn't

## Proposed Fix

Per DECISION-0004:
1. Add `--mode` flag to `research` command (BI-0014)
2. Use `get_mode_labels()` to derive label from actual mode
3. Verify whether `AG_LLM_ENABLED` affects behavior

## Related Items

| Item | Relationship |
|------|--------------|
| CLI-001 | Original finding |
| BI-0011 | CLI label truthfulness backlog item |
| BI-0014 | Add --mode to all commands |
| DECISION-0004 | Policy requiring --mode on all commands |

## Verification

- [ ] `research --mode manual` prints `[computed]`
- [ ] `research --mode llm` prints `[LLM]`
- [ ] Labels match actual execution (not just flag value)

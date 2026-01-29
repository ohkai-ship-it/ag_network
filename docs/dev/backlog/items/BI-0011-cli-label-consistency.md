# BI-0011 — CLI label truthfulness and consistency

## Metadata
- **ID:** BI-0011
- **Type:** CLI UX / Truthfulness
- **Status:** Proposed
- **Priority:** **P1** (contains truthfulness violation)
- **Area:** CLI
- **Owner:** TBD
- **Target sprint:** TBD
- **Source:** BI-0003 code review (CLI-001 (P1), CLI-002, CLI-003, CLI-004, CLI-006, CLI-007)

## Problem

### ⚠️ Truthfulness Violation (CLI-001, P1)

`commands_research.py:145` prints `[computed]` even when running in **LLM mode**:
```python
typer.echo(f"🔍 [computed] Starting research run...")
```

This **violates the truthful CLI invariant** — users cannot distinguish LLM-generated vs deterministic output. This is a core trust property, not UX polish.

### Additional Issues (P2)

1. **Label registry drift** (CLI-006): `cli_labels.py` has a dual registry (LABELS_V1/V2) with ~30% unused labels and some duplicates

2. **No workspace prefix in headers** (CLI-002): When working across workspaces, there's no visual cue for which workspace the output belongs to

3. **Mixed table formats** (CLI-007): Some commands use `rich.table`, others use plain text

4. **Multi-tenant list mode gaps** (CLI-004): List commands show workspace names but not a quick summary of what's in each

## Goal

Improve CLI output consistency and clarity:
- Clean up label registry (single source of truth)
- Add optional `[workspace]` prefix to headers
- Standardize on rich tables throughout
- Add workspace summary to list commands

## Non-goals

- Full i18n support (future)
- CLI theming/colors customization
- Output format flags (JSON, CSV, etc.) — that's separate work

## Acceptance criteria

### Label cleanup (CLI-001)
- [ ] Audit LABELS_V1 vs LABELS_V2 — consolidate to single registry
- [ ] Remove unused labels (mark as deprecated first, then remove)
- [ ] Add tests to detect unused labels

### Workspace prefix (CLI-002)
- [ ] `--workspace-prefix` flag or config option
- [ ] When enabled, headers include `[workspace-name]` prefix
- [ ] Default: off (to avoid breaking existing scripts)

### Table consistency (CLI-003)
- [ ] Document preferred table style (rich.table vs plain)
- [ ] Migrate remaining plain-text lists to rich tables
- [ ] Create helper function for consistent table creation

### List mode (CLI-004)
- [ ] `agn workspace list` shows count of runs per workspace
- [ ] `agn run list` shows status distribution when listing across workspaces

## Current label analysis

From prior review:
- LABELS_V1: ~20 labels
- LABELS_V2: ~25 labels
- Overlap: ~15 labels with identical values
- Unused: ~8-10 labels (never referenced in code)

## Implementation notes

Label cleanup approach:
```python
# Before: dual registry
LABELS_V1 = {"key": "value", ...}
LABELS_V2 = {"key": "value", ...}

# After: single registry with version-aware getter
LABELS = {
    "key": {
        "v1": "value_v1",
        "v2": "value_v2",  # or same as v1
    },
}

def get_label(key: str, version: int = 2) -> str:
    return LABELS[key][f"v{version}"]
```

Or simpler: just pick v2 and remove v1.

## Risks

- Changing labels may break user scripts that grep output
- Workspace prefix may clutter output for single-workspace users

## PR plan

1. PR (S): Label registry cleanup + unused label removal
2. PR (S): Workspace prefix option
3. PR (S): Table consistency migration

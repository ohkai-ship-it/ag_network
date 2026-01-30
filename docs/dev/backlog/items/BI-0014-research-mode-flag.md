# BI-0014 — Add `--mode` flag to all top-level CLI commands

## Metadata
- **ID:** BI-0014
- **Type:** CLI Feature / Policy Enforcement
- **Status:** Proposed
- **Priority:** **P1** (consistency invariant per DECISION-0004)
- **Area:** CLI
- **Owner:** TBD
- **Target sprint:** TBD
- **Source:** BI-0004 CLI review (CLI-008), DECISION-0004

## Problem

The `run-pipeline` command has a `--mode` flag to choose between `manual` and `llm` execution, but other top-level commands do not. Per **DECISION-0004**, all CLI commands must implement `--mode {manual,llm}` with consistent help and defaults.

Current state:
- ✅ `run-pipeline` has `--mode`
- ❌ `research`, `targets`, `outreach`, `prep`, `followup` lack `--mode`
- ❌ Work ops skills (`meeting-summary`, `status-update`, etc.) lack `--mode`

This violates CLI consistency and makes truthfulness labels unreliable.

## Goal

Add `--mode` flag to **all top-level commands** that generate content, with consistent help text and defaults.

## Non-goals

- Changing the default mode (stays `manual`)
- Adding LLM capabilities where they don't exist (flag may be no-op initially)
- Breaking existing scripts

## Acceptance criteria

- [ ] `research`, `targets`, `outreach`, `prep`, `followup` all have `--mode` flag
- [ ] Default is `manual` (matches current behavior)
- [ ] Labels correctly reflect chosen mode (fixes CLI-001)
- [ ] CLI_REFERENCE.md updated to document new flags
- [ ] Tests verify flag behavior

## Implementation notes

Pattern from `run-pipeline`:
```python
mode: str = typer.Option(
    "manual",
    "--mode", "-m",
    help="Execution mode: manual (default) or llm"
)
```

Label output should use:
```python
from agnetwork.cli_labels import get_mode_labels, format_labels

labels = get_mode_labels(is_llm=(mode == "llm"))
typer.echo(f"🔍 {format_labels(labels)} Starting research run...")
```

## Dependencies

- Depends on BI-0011 (CLI-001 fix) being understood first
- May be bundled with BI-0011

## Risks

- Commands may not have working LLM paths — need to verify before adding flag

## PR plan

1. PR (M): Add `--mode` to research commands + label fixes

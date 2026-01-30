# BI-0013 — Fix documentation drift in CLI_REFERENCE.md

## Metadata
- **ID:** BI-0013
- **Type:** Documentation
- **Status:** Proposed
- **Priority:** P2
- **Area:** CLI / Docs
- **Owner:** TBD
- **Target sprint:** TBD
- **Source:** BI-0004 CLI review (CLI-009)

## Problem

CLI_REFERENCE.md has drifted from actual CLI behavior:

- `research --snapshot` is documented as optional but is actually required
- Help text examples don't always match current flag requirements

## Goal

Ensure CLI_REFERENCE.md accurately reflects actual CLI behavior.

## Non-goals

- Changing CLI behavior to match docs (that would require broader discussion)
- Full rewrite of CLI_REFERENCE.md

## Acceptance criteria

- [ ] `research --snapshot` marked as required in CLI_REFERENCE.md
- [ ] All examples in CLI_REFERENCE.md tested and verified working
- [ ] Add "Last verified" date to CLI_REFERENCE.md header

## Implementation notes

Quick audit process:
1. Run each documented command with `--help`
2. Compare documented options with actual options
3. Fix any discrepancies

## Risks

- Low risk (docs-only)

## PR plan

1. PR (S): Fix doc drift in CLI_REFERENCE.md

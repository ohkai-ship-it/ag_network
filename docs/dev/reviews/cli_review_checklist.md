# cli_review_checklist.md

Use this checklist in Sprint 02 to make the CLI more complete and intuitive without shortcuts.

## Inventory
- List all commands and subcommands (auto-generated from Typer help output)
- List global flags and per-command flags
- Identify hidden/legacy commands

## Consistency
- Naming: verbs first, consistent nouns (e.g., `run`, `plan`, `status`, `inspect`)
- Output format: consistent prefixes, workspace echo, truth labels
- Exit codes: non-zero on error, zero on success
- Help text: each command has examples + explanation of side-effects

## Completeness
- Missing “inspect”/“explain” style commands for runs
- Missing “doctor” command for environment/workspace health
- Missing “migrate”/“repair” commands (if applicable)

## Safety
- Commands that write data must confirm workspace context
- No global directory writes
- Dry-run support where safe

## Versioning
- Breaking CLI changes must be versioned (or behind explicit “v2” mode)
- Deprecations must be explicit and time-bounded

# Bug Index (persistent)

This is the canonical list of known bugs. Each bug has a dedicated report in `docs/dev/bugs/reports/`.

## Status legend
- **Open**: confirmed, not fixed
- **Investigating**: reproducing / narrowing scope
- **Blocked**: depends on other work
- **Fixed**: landed on main (include PR)
- **Won't fix**: document rationale

## Bugs (sorted by priority, then recency)

| ID | Title | Status | Priority | Area | First seen | Owner | Repro? | Link |
|---|---|---|---|---|---|---|---|---|
| BUG-0001 | Evidence not populated (pending repro) | Open | P1 | Runs/Claims | YYYY-MM-DD | Jeff | no | reports/BUG-0001-evidence-not-populated.md |
| BUG-0002 | CLI prints `[computed]` regardless of mode | Open | P1 | CLI/Truthfulness | 2026-01-30 | TBD | yes | reports/BUG-0002-cli-computed-label-hardcoded.md |

## Legacy / external references
If an earlier bug note exists (e.g. `docs/dev/bugs/BUG_EVIDENCE_NOT_POPULATED.md`), link it here:
- `BUG_EVIDENCE_NOT_POPULATED.md` (legacy note; optional migration into `reports/`)

## Notes
- P0 = trust breakers (isolation, truthfulness, corruption, security)
- P1 = important (reliability, CI correctness, perf regressions)
- P2 = polish (UX, refactors)

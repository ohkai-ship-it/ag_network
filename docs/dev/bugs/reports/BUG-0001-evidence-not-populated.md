# BUG-0001 — Evidence not populated (pending repro)

## Metadata
- **ID:** BUG-0001
- **Status:** Open
- **Priority:** P1
- **Area:** Runs/Claims
- **Owner:** Jeff
- **First seen:** (unknown)
- **Last verified:** 2026-01-29
- **Version/branch:** v0.2 / main
- **Workspace:** (unknown)

## Summary
Evidence is reported as missing / not populated in at least one workflow, but we currently do not have a minimal reproduction.
This bug remains tracked so it does not get forgotten.

## Invariant impact
- [x] Auditability risk (missing evidence chain)
- [ ] Workspace isolation
- [ ] Truthful CLI
- [ ] Determinism
- [ ] Data corruption

## Steps to reproduce
TBD (needs a concrete repro).

## Expected behavior
Claims/artifacts that require evidence should include a verifiable evidence trail:
`claim_id → source_id(s) → snippet/offsets → persisted in run folder`

## Actual behavior
TBD.

## Evidence
If this was previously documented elsewhere, link it here, e.g.:
- `docs/dev/bugs/BUG_EVIDENCE_NOT_POPULATED.md` (legacy location)

## Regression test plan
Once repro exists:
- Add an integration test that runs the minimal workflow and asserts evidence is persisted.

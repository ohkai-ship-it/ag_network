# BI-0002 — GitHub flow conventions + repo hygiene checklist

## Metadata
- **ID:** BI-0002
- **Type:** Process/Hardening
- **Status:** Done
- **Priority:** P1
- **Area:** CI/Process
- **Owner:** Jeff
- **Target sprint:** SPRINT-2026-01
- **Completed:** 2026-01-29

## Problem
We need a shared, explicit GitHub workflow so that:
- PRs remain reviewable and auditable,
- local checks match CI checks,
- docs/dev remains internal and doesn’t accidentally become user-facing,
- the team can move “slowly and correctly” without ambiguity.

Right now, the team expects more explanation and guardrails.

## Goal
Deliver a clear, step-by-step **GitHub flow guide** plus a practical **repo hygiene checklist** that explains:
- branching strategy,
- PR sizing and review expectations,
- required checks and how to run them locally,
- how releases/tags relate to `v0.2.x`,
- how docs are organized (`docs/` user-facing vs `docs/dev/` internal),
- how to handle generated/scratch artifacts (recommended `docs/dev/_local/`).

## Non-goals
- Enforcing branch protection rules in GitHub settings (doc-only this sprint)
- Major CI refactors (unless required for correctness)

## Acceptance criteria (Definition of Done)
- [x] A new doc exists (internal): `docs/dev/team/github_flow.md` (or similar)
- [x] The doc includes:
  - [x] Branching conventions (`feature/…`, `fix/…`, `chore/…`)
  - [x] PR size rules ("PR-sized" changes) and when to split
  - [x] Local preflight checklist (install, ruff, pytest offline)
  - [x] CI parity expectations (what CI runs and why)
  - [x] Review process (who reviews what; how to attach evidence)
  - [x] Docs taxonomy: `docs/` vs `docs/dev/` and why
  - [x] Where to put scratch output (`docs/dev/_local/`, gitignored)
- [x] A **repo hygiene checklist** exists (internal): `docs/dev/team/repo_hygiene_checklist.md`
- [x] (Optional if appropriate) `.gitignore` includes `docs/dev/_local/`
- [x] No contradictions with invariants and "truthful CLI" rules

## Implementation notes
- Keep this accessible: assume a new contributor can follow it without prior context.
- Prefer explicit commands and examples over abstract rules.

## Risks
- Over-specification that blocks iteration: keep it pragmatic and aligned to current practice.

## PR plan (PR-sized)
1. PR #1 (docs-only): GitHub flow guide + repo hygiene checklist + `.gitignore` for `_local/` (if used)

## Completion
- **Branch**: chore/github-flow-docs
- **Summary**: [SPRINT-2026-01_BI-0002_completion.md](../../agent_handoff/COMPLETION_SUMMARIES/SPRINT-2026-01_BI-0002_completion.md)

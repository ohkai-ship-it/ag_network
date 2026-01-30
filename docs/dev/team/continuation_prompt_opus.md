# continuation_prompt_opus.md
_Last updated: 2026-01-29_

You are **Opus 4.5** in VS Code (Junior Engineer). You are starting a **new chat / fresh context**.

## Your role
Implement PR-sized changes from prompts/specs. Stay within scope. Add tests. Produce local completion summaries.
You must not take shortcuts (no disabling checks, no bypass flags, no “just ignore warnings”).

## Context snapshot (end of previous sprint)

### Completed hardening (high-level)
- Workspace isolation enforced (no silent global fallbacks; workspace guard runs on DB open).
- Workspace-bound factories for storage (SQLite + CRM).
- CLI uses workspace runs_dir in status and sequence plan.
- CRM is workspace-scoped end-to-end (storage + CLI).
- Truthful CLI labels (LLM/computed/placeholder/fetched/cached) reflect real behavior.
- FTS search scoped defensively to workspace (given per-workspace DB model).
- CLI refactored: cli.py split into modules with no behavior change.

### Open / next sprint focus
- Persistent backlog + sprint structure (repeatable cadence).
- Fix “source of truth” workflows in GitHub (templates/CI/branch protection; ensure docs/dev is gitignored).
- Observability: run-level traces, step timings, evidence trails, debugging UX.
- Performance: profiling harness + timing metrics, identify regressions, optimize hot paths.
- New bug: “evidence not populated” appears related to workspace behavior (triage + fix).

### Non-negotiables for next sprint
- No shortcuts: no flags to silence errors/warnings; fix root causes.
- LLM-first execution; deterministic-capable test path (manual mode for CI/perf/debug; no provider calls in CI).
- Every change locked by tests + documented decisions when behavior changes.


## Sprint boot (do this first)
1) Create local sprint folder:
- `docs/dev/sprints/SPRINT_02/`
  - `PLAN.md` (sprint goals + backlog slice)
  - `DAILY_LOG.md`
  - `PR_SUMMARIES/`

2) Ensure `docs/dev/` is gitignored (do NOT commit local work docs).
- If `.gitignore` does not include `docs/dev/`, add it in a tiny PR.

3) Verify GitHub “source of truth” workflow (without changing behavior):
- Branch protection: require CI checks + PR review.
- CI uses `pip install -e ".[dev]"`.
- PR template + issue template exist.
- Keep canonical docs in repo; keep dev notes local.

## Next sprint workstreams (create a persistent backlog)
A) **Backlog + sprint structure**
- Convert FINDINGS_BACKLOG into: `backlog/` + `sprints/SPRINT_02.md` (in repo) OR equivalent structure.
- Add definitions: P0/P1/P2, “Definition of Done”, “Evidence required”, “Test requirements”.
- Goal: repeatable sprint planning and tracking.

B) **Observability**
- Add run-level step timing capture (start/end/duration) with stable schema.
- Add structured run trace output (JSONL or sqlite table) with workspace scope.
- Improve debug UX: ensure INFO logs capture key actions (no silent failures).

C) **Performance**
- Add a small benchmark harness (`pytest-benchmark` or custom script) for hot paths:
  - run creation, source ingest, FTS search, research pipeline.
- Capture baseline and compare in CI (optional initially).
- Identify and fix obvious regressions (no premature optimization).

D) **Bug triage: evidence not populated**
- Reproduce deterministically.
- Confirm workspace scoping issue (wrong DB, wrong workspace_id, stale retrieval).
- Add regression tests and fix root cause.

## Output expectations
For each PR:
- Branch, commit(s), tests, local completion summary in `docs/dev/sprints/SPRINT_02/PR_SUMMARIES/`
- Update canonical backlog status (in repo).

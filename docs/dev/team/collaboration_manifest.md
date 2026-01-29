# collaboration_manifest.md
_Last updated: 2026-01-29_

This document defines **how we collaborate** on `agnetwork`: roles, invariants, where artifacts live, and the conventions that keep the system auditable and trustworthy.

## 1) Team structure

### Product Manager (Human-in-the-loop) — **Kai**
**Responsibilities**
- Owns priorities, sprint goals, acceptance criteria, and sign-off.
- Approves merges and decides trade-offs.
- Provides context, constraints, and final decisions.

### Senior Engineer / Architect — **Jeff** (ChatGPT, GPT-5.2 Thinking)
**Responsibilities**
- Architecture + design decisions, PR scoping, risk management.
- Writes implementation prompts/specs and review checklists.
- Reviews PR completion summaries, detects invariant regressions.
- Maintains system invariants and the “truthful CLI” contract.

### Junior Engineer — **Jacob** (VS Code + Copilot + Opus 4.5)
**Responsibilities**
- Implements PRs following the prompt/spec (no scope creep).
- Adds tests (offline; deterministic by default).
- Updates internal work docs (summaries, debug notes, test reports).
- Produces PR completion summaries for review.

## 2) Non-negotiable invariants (must always hold)

- **Workspace isolation is hard**: no cross-workspace reads/writes; storage + memory + runs are workspace-scoped.
- **No global fallbacks**: DB/storage/runs must not silently default to global config.
- **Truthful CLI**: labels must reflect reality (deterministic vs agent; retrieved vs generated; cached vs fetched).
- **Auditability**: sources captured; artifacts reference `source_id`s; evidence snippets (when required) are verifiable; verifier enforces.
- **Determinism by default**: LLM/enrichment is opt-in; tests run offline; golden outputs don’t change unless versioned.

If a change threatens any invariant, we stop and redesign; we do not “patch around it”.

## 3) Documentation taxonomy (what goes where)

### `docs/` — user-facing documentation (**public contract**)
`docs/` is the **user-facing** documentation folder. It is the place for content we’re willing to treat as stable guidance:
- Getting started / installation
- CLI usage and examples
- Architecture extensions meant for users
- Any documentation that should remain coherent across releases

Rule: if something in `docs/` is wrong, it is a **product bug**.

### `docs/dev/` — internal engineering documentation (**not user-facing**)
`docs/dev/` is for **internal** development artifacts and process docs. It may be committed, but it is **not** part of the user-facing contract:
- Sprint planning artifacts (`docs/dev/sprints/`)
- Persistent backlog (`docs/dev/backlog/`)
- Persistent bugs (`docs/dev/bugs/`)
- Reviews and findings (`docs/dev/reviews/`)
- Agent handoff notes (`docs/dev/agent_handoff/`)
- Team/process docs (`docs/dev/team/`)

Rule: content in `docs/dev/` is allowed to be more detailed, tactical, and iterative.

### Optional: `_local` scratch space (recommended)
If you want a clean separation between committed internal docs and machine output / noisy notes, create:
- `docs/dev/_local/` (gitignored)
  - perf runs, logs, temporary investigations, throwaway prompts, etc.

## 4) Persistent tracking conventions (bugs, backlog, sprints)

### Backlog (canonical)
- Canonical index: `docs/dev/backlog/BACKLOG_INDEX.md`
- One item per file: `docs/dev/backlog/items/BI-0001-short-slug.md`
- Template: `docs/dev/backlog/templates/BACKLOG_ITEM_TEMPLATE.md`
- Status: Proposed → Ready → In progress → Done (or Blocked / Dropped)

### Bugs (canonical)
- Canonical index: `docs/dev/bugs/BUG_INDEX.md`
- One bug per file: `docs/dev/bugs/reports/BUG-0001-short-slug.md`
- Template: `docs/dev/bugs/templates/BUG_REPORT_TEMPLATE.md`
- Status: Open / Investigating / Blocked / Fixed / Won’t fix
- Priority rubric:
  - **P0** trust breakers (isolation, truthfulness, security, corruption)
  - **P1** important (reliability, CI correctness, perf regressions)
  - **P2** polish (UX, refactors)

### Sprints
- Templates: `docs/dev/sprints/templates/SPRINT_START_TEMPLATE.md`, `SPRINT_END_TEMPLATE.md`
- Sprint docs live in `docs/dev/sprints/` (e.g., `SPRINT-2026-01.md`).

## 5) Agent handoff procedure (for every PR)

### Canonical artifacts (committed, stable references)
- `ARCHITECTURE.md` — canonical architecture (repo root)
- `CLI_REFERENCE.md` — CLI reference (repo root)
- `PROJECT_PLAN.md` — project plan / roadmap (repo root)
- `docs/dev/reviews/REVIEW_GUIDE.md` — how we run reviews
- `docs/dev/team/collaboration_manifest.md` — this document

### Handoff loop
1) **Kai/Jeff** defines PR scope (small + test-first) and writes a PR prompt/spec.
2) **Jacob** implements on a branch and runs:
   - `pip install -e ".[dev]"`
   - `ruff check .`
   - `pytest -q` (offline)
3) **Jacob** writes a completion summary (and links evidence) in:
   - `docs/dev/agent_handoff/COMPLETION_SUMMARIES/`
4) **Jeff** reviews completion summary + key diffs (no “trust me”).
5) **Kai** merges only after CI passes and invariants hold.

### No-shortcuts rule
- Never “fix” errors by disabling checks, suppressing warnings, or adding flags to bypass invariants.
- If a check is noisy/incorrect, fix the underlying cause or tighten the check with clear rationale + tests.

## 6) Quality bar (must always hold)
- `ruff check .` clean
- `pytest -q` clean offline (provider tests must skip cleanly)
- No silent global fallbacks (DB/storage/runs always workspace-scoped)
- Workspace isolation never weakened
- CLI labels remain truthful (deterministic vs agent; retrieved vs generated; cached vs fetched)

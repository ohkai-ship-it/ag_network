# Sprint <SPRINT-ID> — Start

## Metadata
- **Sprint ID:** SPRINT-YYYY-MM (or SPRINT-000X)
- **Start date:** YYYY-MM-DD
- **Branch:** main
- **Version target:** v0.2.x (if any)
- **Roles:** Kai (PM/HITL), Jeff (Sr Eng/Arch), Jacob (Jr Eng)

## Sprint goals (ranked)
1. ...
2. ...
3. ...

## Scope (committed)
- BI-XXXX
- BI-XXXX

## Out of scope
- …

## Invariants (must not regress)
- Workspace isolation hard (no cross-workspace reads/writes)
- No global fallbacks (DB/storage/runs)
- Truthful CLI labeling (deterministic vs agent; retrieved vs generated; cached vs fetched)
- Auditability (sources + evidence chain verifiable)
- LLM-first; deterministic-capable test path (manual mode for CI/perf/debug)

## Baselines to capture (before changes)
- ruff / pytest status
- Small perf baseline (cold + warm)
- CLI help output snapshot (for review)

## Risks / watch-outs
- …

## PR plan (small + reviewable)
- PR1: ...
- PR2: ...

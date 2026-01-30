# Backlog Index (persistent)

Canonical backlog of work items (features, refactors, hardening). Each item has a file in `docs/dev/backlog/items/`.

## Status legend
- **Proposed** → **Ready** → **In progress** → **Done**
- or **Blocked** / **Dropped**

## Items (sorted by priority then sequence)

| ID | Title | Type | Status | Priority | Area | Sprint | Owner | Link |
|---|---|---|---|---|---|---|---|---|
| BI-0001 | Docs + backlog/bug/sprint templates + indexes | Docs/Hardening | Done | P1 | Docs | SPRINT-2026-01 | Jeff | items/BI-0001-docs-backlog-templates.md |
| BI-0002 | GitHub flow conventions + repo hygiene checklist | Process/Hardening | Done | P1 | CI/Process | SPRINT-2026-01 | Jeff | items/BI-0002-github-flow-conventions.md |
| BI-0003 | Quick code review (structured) + findings → backlog/bugs | Hardening | Done | P1 | Review | SPRINT-2026-01 | Jeff | items/BI-0003-quick-code-review.md |
| BI-0004 | CLI review (truthfulness + UX) + backlog/bug intake | Hardening | Done | P1 | CLI | SPRINT-2026-01 | Jeff | items/BI-0004-cli-review.md |
| BI-0005 | Performance baseline + harness (offline) | Perf/Hardening | Done | P1 | Perf | SPRINT-2026-01 | Jeff | items/BI-0005-performance-baseline-harness.md |
| BI-0006 | Observability review + MVP trace spec (run visibility) | Observability | Done | P1 | Observability | SPRINT-2026-01 | Jeff | items/BI-0006-observability-mvp-spec.md |
| BI-0007 | Batch DB inserts for bulk operations | Performance | Proposed | P2 | Storage | TBD | TBD | items/BI-0007-batch-db-inserts.md |
| BI-0008 | Lazy loading for workspace registry | Performance | Proposed | P2 | Core | TBD | TBD | items/BI-0008-lazy-workspace-registry.md |
| BI-0009 | Add timing + evidence chain to worklog | Observability | Proposed | P1 | Observability | TBD | TBD | items/BI-0009-worklog-timing-evidence.md |
| BI-0010 | Track LLM token usage per run | Observability | Proposed | P2 | Observability | TBD | TBD | items/BI-0010-llm-token-tracking.md |
| BI-0011 | CLI label truthfulness + consistency | CLI UX | Proposed | **P1** | CLI | TBD | TBD | items/BI-0011-cli-label-consistency.md |
| BI-0012 | CLI progress indicators for long ops | CLI UX | Proposed | P2 | CLI | TBD | TBD | items/BI-0012-cli-progress-indicators.md |
| BI-0013 | Fix documentation drift in CLI_REFERENCE.md | Documentation | Proposed | P2 | CLI/Docs | TBD | TBD | items/BI-0013-cli-doc-drift.md |
| BI-0014 | Add `--mode` flag to all CLI commands | CLI Feature | Proposed | **P1** | CLI | TBD | TBD | items/BI-0014-research-mode-flag.md |
| BI-0015 | Policy Alignment — LLM-First, Deterministic-Capable | Process/Docs | Done | P1 | Docs/Governance | SPRINT-2026-01 | Jacob | items/BI-0015-policy-alignment-llm-first.md |

## Intake rules
- **P0**: isolation, truthfulness, security, corruption
- **P1**: reliability, CI parity, perf regressions
- **P2**: UX polish, refactors, nice-to-haves

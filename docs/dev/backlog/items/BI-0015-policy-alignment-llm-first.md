# BI-0015: Policy Alignment — LLM-First, Deterministic-Capable

| Field | Value |
|-------|-------|
| **ID** | BI-0015 |
| **Title** | Policy Alignment — LLM-First, Deterministic-Capable |
| **Type** | Process / Docs |
| **Status** | Done |
| **Priority** | P1 |
| **Area** | Docs / Governance |
| **Sprint** | SPRINT-2026-01 |
| **Owner** | Jacob |

## Summary

Align all documentation with the updated testing/runtime policy:

- **LLM-first execution** — default runtime UX is `--mode llm`
- **Deterministic-capable test path** — manual mode exists for CI/perf/debug (offline, deterministic)
- **Manual mode is not required to match LLM feature parity**
- **Provider/network calls must never happen in CI unless explicitly configured**

This replaces the previous "deterministic by default" wording, which implied that manual mode was the default runtime experience.

## Scope

**Docs-only change** — no code changes required.

### Files to update

1. `docs/dev/team/collaboration_manifest.md` — change invariant bullet
2. `docs/dev/backlog/items/BI-0006-observability-mvp-spec.md`
3. `docs/dev/reviews/OBSERVABILITY_MVP_SPRINT-2026-01.md`
4. `docs/dev/team/continuation_prompt_gpt52_TEMPLATE.md`
5. `docs/dev/team/continuation_prompt_opus_TEMPLATE.md`
6. `docs/dev/team/continuation_prompt_gpt52.md`
7. `docs/dev/team/continuation_prompt_opus.md`
8. `docs/dev/team/repo_hygiene_checklist.md`
9. `docs/dev/sprints/templates/SPRINT_START_TEMPLATE.md`
10. `docs/dev/sprints/SPRINT-2026-01.md`
11. `docs/dev/backlog/BACKLOG_INDEX.md`

### Decision entry

Add **DECISION-0003** to `docs/dev/agent_handoff/DECISIONS.md`:
- LLM-first; manual mode is deterministic-capable for CI/perf/debug

## Acceptance criteria

- [ ] All occurrences of "deterministic by default" / "determinism by default" updated
- [ ] DECISION-0003 created
- [ ] Completion summary with search terms + files changed + before/after snippet

## Search terms used

```bash
grep -rE "deterministic by default|determinism by default" docs/dev/
grep -rE "deterministic|determinism" docs/dev/team/
```

## Related

- DECISION-0002 (Langfuse LLM-only)
- DECISION-0004 (--mode everywhere)

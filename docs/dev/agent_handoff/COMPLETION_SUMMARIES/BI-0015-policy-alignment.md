# Completion Summary: BI-0015 — Policy Alignment: LLM-First, Deterministic-Capable

## Summary

Updated all documentation from "deterministic by default" to "LLM-first; deterministic-capable test path" to accurately reflect that:

- **LLM mode is the intended user experience** (`--mode llm`)
- **Manual mode is a testing/debugging capability** (`--mode manual`)
- Manual mode is not required to match LLM feature parity
- Provider/network calls must never happen in CI unless explicitly configured

## Search terms used

```bash
# Primary search (14 matches initially)
grep -rE "deterministic by default|determinism by default" docs/dev/

# Broader search for related phrasing (20+ matches)
grep -rE "deterministic|determinism" docs/dev/team/
```

## Files changed

| File | Changes |
|------|---------|
| `docs/dev/agent_handoff/DECISIONS.md` | Added DECISION-0003 |
| `docs/dev/team/collaboration_manifest.md` | Updated invariant bullet + Junior Engineer responsibility |
| `docs/dev/team/continuation_prompt_gpt52_TEMPLATE.md` | Updated role + invariants sections (2 occurrences) |
| `docs/dev/team/continuation_prompt_opus_TEMPLATE.md` | Updated invariants section |
| `docs/dev/team/continuation_prompt_gpt52.md` | Updated role + non-negotiables sections (2 occurrences) |
| `docs/dev/team/continuation_prompt_opus.md` | Updated non-negotiables section |
| `docs/dev/team/repo_hygiene_checklist.md` | Updated invariants table |
| `docs/dev/team/ag_network_build_playbook_M1-M8.md` | Updated core principles |
| `docs/dev/sprints/templates/SPRINT_START_TEMPLATE.md` | Updated invariants section |
| `docs/dev/sprints/SPRINT-2026-01.md` | Updated invariants section |
| `docs/dev/backlog/items/BI-0006-observability-mvp-spec.md` | Updated design principles (2 occurrences) |
| `docs/dev/reviews/OBSERVABILITY_MVP_SPRINT-2026-01.md` | Updated objective + design principles table (2 occurrences) |
| `docs/dev/backlog/items/BI-0015-policy-alignment-llm-first.md` | Created backlog item |
| `docs/dev/backlog/BACKLOG_INDEX.md` | Added BI-0015 entry |
| `docs/dev/agent_handoff/COMPLETION_SUMMARIES/BI-0015-policy-alignment.md` | This file |

## Before/After (key invariant bullet)

### Before (`collaboration_manifest.md`)

```markdown
- **Determinism by default**: LLM/enrichment is opt-in; tests run offline; golden outputs don't change unless versioned.
```

### After (`collaboration_manifest.md`)

```markdown
- **LLM-first execution; deterministic-capable test path**: default runtime is `--mode llm`; manual mode (`--mode manual`) provides offline determinism for CI/perf/debug; provider/network calls never happen in CI unless explicitly configured.
```

## Decision entry added

**DECISION-0003 — LLM-first execution; deterministic-capable test path**

- Default runtime UX is `--mode llm`
- Manual mode exists for CI/perf/debug (offline, deterministic)
- Manual mode is not required to match LLM feature parity
- Provider/network calls must never happen in CI unless explicitly configured

## Verification

After all edits, the only remaining matches for "deterministic by default" are:

1. **DECISION-0003 context**: `"The phrase "deterministic by default" implied..."` (intentional reference)
2. **BI-0015 backlog item**: References to the old wording and search terms (documentation of the change)

All operational documentation now uses the new "LLM-first; deterministic-capable" framing.

## Acceptance criteria

- [x] All occurrences of "deterministic by default" / "determinism by default" updated
- [x] DECISION-0003 created
- [x] Completion summary with search terms + files changed + before/after snippet

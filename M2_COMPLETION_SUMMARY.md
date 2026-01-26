# Milestone M2 Completion Summary

## New Kernel Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              CLI Layer                                    │
│  ag research | ag targets | ag outreach | ag prep | ag followup          │
│                          ag run-pipeline (NEW)                            │
└────────────────────────────────────────┬─────────────────────────────────┘
                                         │
                                         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          Kernel Layer (NEW)                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────────────┐     │
│  │    TaskSpec     │  │     Planner     │  │   KernelExecutor      │     │
│  │  - task_type    │──│  - create_plan  │──│  - execute_task       │     │
│  │  - workspace    │  │  - TASK_MAP     │  │  - execute_plan       │     │
│  │  - inputs       │  │                 │  │  - _process_step      │     │
│  │  - constraints  │  └─────────────────┘  │  - _persist_artifacts │     │
│  └─────────────────┘           │           │    _via_runmanager    │     │
│                                ▼           └───────────────────────┘     │
│                                ▼                        │                │
│  ┌─────────────────────────────────────┐               │                │
│  │              Plan                   │               │                │
│  │  - steps: List[Step]                │               │                │
│  │  - get_next_step()                  │               │                │
│  │  - is_complete() / has_failed()     │               │                │
│  └─────────────────────────────────────┘               │                │
└────────────────────────────────────────────────────────┼────────────────┘
                                                         │
                                         ┌───────────────┴───────────────┐
                                         ▼                               ▼
┌──────────────────────────────────────────────┐  ┌─────────────────────────┐
│              Skills Layer (MIGRATED)         │  │   Eval/Verifier (NEW)   │
│  ┌───────────────────────────────────────┐   │  │  - verify_skill_result  │
│  │  Skill Protocol (Skill Contract)      │   │  │  - artifact_refs_exist  │
│  │  - name: str                          │   │  │  - json_validates       │
│  │  - version: str                       │   │  │  - schema_validates     │
│  │  - run(inputs, ctx) -> SkillResult    │   │  │  - claims_labeled       │
│  └───────────────────────────────────────┘   │  │  - basic_completeness   │
│                                              │  └─────────────────────────┘
│                                              │
│  Migrated Skills:                            │
│  ✅ research_brief  ✅ target_map           │
│  ✅ outreach        ✅ meeting_prep         │
│  ✅ followup                                 │
└──────────────────────────────────────────────┘
                                         │
                                         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│              Orchestrator/RunManager (UNCHANGED)                          │
│  - Creates run folder structure                                           │
│  - Writes artifacts (MD + JSON with meta)                                │
│  - Manages worklog.jsonl and status.json                                 │
│  - Injects version metadata                                               │
└──────────────────────────────────────────────────────────────────────────┘
```

## How `ag run-pipeline` Works

1. **CLI receives command** with company name and options
2. **TaskSpec created** with `TaskType.PIPELINE` and inputs
3. **Planner creates Plan** with 5 sequential steps:
   - step_1_research_brief → step_2_target_map → step_3_outreach → step_4_meeting_prep → step_5_followup
4. **KernelExecutor runs each step**:
   - Gets skill from registry
   - Creates SkillContext with run_id, workspace
   - Calls `skill.run(inputs, context)`
   - Receives SkillResult with output, artifacts, claims
   - Verifies result (if verifier enabled)
   - Delegates artifact writing to RunManager
5. **Single run folder** contains all 5 artifact pairs

## Skills Migrated to Contract

All 5 BD skills now implement the Skill protocol:

| Skill | Artifacts | Status |
|-------|-----------|--------|
| research_brief | research_brief.md, research_brief.json | ✅ Migrated |
| target_map | target_map.md, target_map.json | ✅ Migrated |
| outreach | outreach.md, outreach.json | ✅ Migrated |
| meeting_prep | meeting_prep.md, meeting_prep.json | ✅ Migrated |
| followup | followup.md, followup.json | ✅ Migrated |

## Verification Enforcement

The Verifier layer performs these checks on every SkillResult:

1. **artifact_refs_exist**: All artifacts have both MD and JSON versions
2. **json_validates**: JSON content parses correctly
3. **schema_validates**: JSON validates against Pydantic output models (ResearchBrief, TargetMap, etc.)
4. **claims_labeled**: Claims without evidence are marked as assumption/inference (not fact)
5. **basic_completeness**: Required fields present per artifact type

If verification fails with severity=ERROR:
- Step is marked as failed
- Run status is set to "failed"
- Issues are logged to worklog.jsonl
- `ag run-pipeline` exits with code 1

> **Note**: `schema_validates` uses WARNING severity to allow flexibility while still surfacing issues.

## New Files Added

```
src/agnetwork/
├── kernel/
│   ├── __init__.py       # Kernel module exports
│   ├── models.py         # TaskSpec, Plan, Step (with started_at/completed_at), Constraints
│   ├── contracts.py      # SkillResult, SkillContext, Claim, etc. (CANONICAL location)
│   ├── planner.py        # Creates Plans from TaskSpecs
│   └── executor.py       # Executes Plans, delegates persistence to RunManager
├── skills/
│   ├── contracts.py      # Re-exports from kernel.contracts (convenience import)
│   ├── target_map.py     # NEW: TargetMapSkill
│   ├── outreach.py       # NEW: OutreachSkill
│   ├── meeting_prep.py   # NEW: MeetingPrepSkill
│   └── followup.py       # NEW: FollowupSkill
└── eval/
    ├── __init__.py       # Eval module exports
    └── verifier.py       # Verifier class with Pydantic schema validation

tests/
├── test_kernel.py        # Tests for TaskSpec, Plan, Planner
├── test_verifier.py      # Tests for Verifier
└── test_executor.py      # Tests for pipeline and verification
```

### Architecture Notes

- **Canonical contract location**: `agnetwork.kernel.contracts` is the single source of truth for skill contracts. `agnetwork.skills.contracts` re-exports for convenience.
- **Artifact persistence**: `KernelExecutor._persist_artifacts_via_runmanager()` delegates ALL file writing to `RunManager`. The executor never writes files directly.
- **Step timestamps**: `Step` model includes `started_at`, `completed_at`, and `status` fields for execution tracking (useful for future retries/tool failures in M3).

## Backward Compatibility

✅ All existing CLI commands work unchanged:
- `ag research` - Same output format
- `ag targets` - Same output format
- `ag outreach` - Same output format
- `ag prep` - Same output format
- `ag followup` - Same output format
- `ag validate-run` - Same behavior
- `ag status` - Same behavior

✅ Golden tests from M1 all pass (60 tests total)

## Test Results

```
60 passed in 2.02s
- Golden tests: 7 passed (all existing commands)
- Kernel tests: 15 passed (TaskSpec, Plan, Planner)
- Verifier tests: 8 passed
- Executor tests: 5 passed
- Existing tests: 25 passed (models, orchestrator, validate, versioning)
```

## Follow-ups for M3 (LLM Tool Integration)

1. **Tool abstraction layer**: Define Tool protocol similar to Skill
2. **LLM client integration**: Add OpenAI/Anthropic clients with retry/fallback
3. **Research skill enhancement**: Replace deterministic content with LLM generation
4. **Source ingestion**: Web scraping, PDF parsing for research sources
5. **Prompt templates**: Jinja2 templates for skill prompts
6. **Rate limiting**: Implement token bucket for API calls
7. **Cost tracking**: Track token usage per run in metrics

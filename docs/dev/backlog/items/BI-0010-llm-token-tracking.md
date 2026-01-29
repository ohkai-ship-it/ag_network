# BI-0010 — Track LLM token usage per run

## Metadata
- **ID:** BI-0010
- **Type:** Observability
- **Status:** Proposed
- **Priority:** P2
- **Area:** Observability / Cost-awareness
- **Owner:** TBD
- **Target sprint:** TBD
- **Source:** BI-0003 code review (OBS-002)

## Problem

There's no visibility into LLM token consumption per run. This makes it impossible to:

- Track cost trends over time
- Identify expensive prompts
- Set budgets or alerts
- Compare efficiency across prompt versions

The semantic kernel abstracts LLM calls, so we need to surface usage metrics at the orchestrator level.

## Goal

Track and persist token usage (prompt tokens, completion tokens, total) for each run.

## Non-goals

- Real-time cost calculation (exchange rates vary)
- Token budget enforcement (future feature)
- Multi-model cost comparison

## Acceptance criteria

- [ ] LLM adapters return token counts with responses
- [ ] `ExecutionContext` accumulates token counts across all LLM calls
- [ ] `run.worklog` includes a summary entry with total tokens
- [ ] `agent_status.json` metrics include `prompt_tokens`, `completion_tokens`
- [ ] CLI `run show <run-id>` displays token summary
- [ ] Unit tests verify token tracking

## Proposed schema additions

### Worklog summary entry
```json
{
  "timestamp": "...",
  "phase": "_summary",
  "action": "run_completed",
  "status": "success",
  "llm_usage": {
    "prompt_tokens": 12345,
    "completion_tokens": 2345,
    "total_tokens": 14690,
    "call_count": 5
  }
}
```

### agent_status.json metrics
```json
{
  "metrics": {
    "prompt_tokens": 12345,
    "completion_tokens": 2345,
    "total_tokens": 14690,
    "llm_call_count": 5,
    "elapsed_seconds": 42.5
  }
}
```

## Implementation notes

OpenAI and Anthropic both return usage in their responses:
```python
# OpenAI
response.usage.prompt_tokens
response.usage.completion_tokens

# Anthropic
response.usage.input_tokens
response.usage.output_tokens
```

The adapters need to expose this in a normalized form.

## Risks

- Some providers (mock, local) may not have token counts → use estimates or 0
- Token counts may vary slightly between SDK versions

## Dependencies

- Semantic kernel adapter changes
- ExecutionContext enhancement

## PR plan

1. PR (S): Add token usage tracking to adapters + ExecutionContext + status

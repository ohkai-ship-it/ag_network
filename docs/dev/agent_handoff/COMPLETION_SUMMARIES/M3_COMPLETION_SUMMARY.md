# M3 Completion Summary: LLM Tooling + Structured Generation

**Completed:** January 26, 2026  
**Status:** ✅ All tasks complete, 116 tests passing

---

## Overview

M3 adds LLM as a **tool** (not agent replacement) with:
- Adapter-based provider abstraction (Anthropic, OpenAI, Fake)
- Multi-role routing (draft, critic, extractor)
- Structured output enforcement with Pydantic + repair loop
- Prompt library for all 5 BD skills
- Backward-compatible execution modes (manual default, LLM opt-in)

---

## Architecture Map

```
src/agnetwork/
├── kernel/
│   ├── models.py          # Added ExecutionMode enum
│   ├── executor.py        # Added LLM mode support
│   └── llm_executor.py    # NEW: LLMSkillExecutor class
│
├── tools/
│   └── llm/               # NEW MODULE
│       ├── __init__.py    # Public exports
│       ├── types.py       # LLMMessage, LLMRequest, LLMResponse, LLMUsage
│       ├── factory.py     # LLMFactory, LLMConfig, RoleConfig
│       ├── structured.py  # extract_json, parse_or_repair_json
│       └── adapters/
│           ├── base.py    # LLMAdapter Protocol + error classes
│           ├── fake.py    # FakeAdapter for deterministic testing
│           ├── anthropic.py  # Claude integration
│           └── openai.py     # GPT integration
│
├── prompts/               # NEW MODULE
│   ├── __init__.py
│   ├── research_brief.py  # build_research_brief_prompt()
│   ├── target_map.py      # build_target_map_prompt()
│   ├── outreach.py        # build_outreach_prompt()
│   ├── meeting_prep.py    # build_meeting_prep_prompt()
│   ├── followup.py        # build_followup_prompt()
│   └── critic.py          # CriticResult, build_critic_prompt()
│
├── config.py              # Added LLMConfig class
└── cli.py                 # Added --mode flag to run-pipeline
```

---

## How to Enable LLM Mode

### 1. Set Environment Variables

```bash
# Required
export AG_LLM_ENABLED=1
export ANTHROPIC_API_KEY=sk-ant-...  # or OPENAI_API_KEY

# Optional (defaults shown)
export AG_LLM_DEFAULT_PROVIDER=anthropic
export AG_LLM_DEFAULT_MODEL=claude-sonnet-4-20250514
export AG_LLM_TEMPERATURE=0.7
export AG_LLM_MAX_TOKENS=4096
export AG_LLM_TIMEOUT_S=60

# Role-specific overrides (optional)
export AG_LLM_CRITIC_PROVIDER=anthropic
export AG_LLM_CRITIC_MODEL=claude-sonnet-4-20250514
export AG_LLM_DRAFT_PROVIDER=anthropic
export AG_LLM_DRAFT_MODEL=claude-sonnet-4-20250514
```

### 2. Run Pipeline with LLM Mode

```bash
# Default: manual mode (deterministic templates)
ag run-pipeline TestCorp --snapshot "AI company"

# LLM mode: uses configured LLM for generation
ag run-pipeline TestCorp --snapshot "AI company" --mode llm
```

### 3. Individual Commands

Individual skill commands (`ag research`, `ag targets`, etc.) continue to use manual mode. LLM mode is only available through `run-pipeline --mode llm`.

---

## Role Configuration

| Role | Purpose | Default Temp | Use Case |
|------|---------|--------------|----------|
| `default` | General-purpose | 0.7 | Fallback for unconfigured roles |
| `draft` | Generate initial artifacts | 0.7 | Research briefs, outreach drafts |
| `critic` | Review and repair | 0.3 | JSON repair, quality review |
| `extractor` | Extract structured data | 0.0 | Future: web scraping, parsing |

---

## Structured Output Flow

```
1. LLM generates text response
        ↓
2. extract_json() finds JSON in response
        ↓
3. json.loads() parses to dict
        ↓
4. Pydantic model.model_validate(dict)
        ↓
   [If validation fails]
        ↓
5. _repair_json() calls critic role
        ↓
6. Retry up to max_repairs times
        ↓
7. Return validated model OR raise StructuredOutputError
```

---

## Testing Strategy

### Offline Testing (No API Keys)

All tests use `FakeAdapter` which provides:
- Preset responses for each skill type
- Response queue for multi-turn scenarios
- Pattern matching on prompt content
- Configurable failures for error paths

```python
# Example test setup
fake_factory = LLMFactory(config)
draft_fake = FakeAdapter()
draft_fake.add_response("research brief", FAKE_RESEARCH_BRIEF)
factory.set_adapter("draft", draft_fake)
```

### Live Testing (With API Keys)

```bash
# Skipped by default, run with:
ANTHROPIC_API_KEY=sk-ant-... pytest tests/test_llm_adapters.py -k "live"
```

---

## Safety Notes

### ⚠️ Draft-Only Mode
All LLM outputs are **drafts requiring human review**. No auto-send, no CRM writes.

### ⚠️ Assumptions Labeled
When no sources are provided, all personalization angles are marked `is_assumption: true`.

### ⚠️ Verifier Still Enforced
The existing verifier runs after LLM generation. Unsourced facts without assumption labels will fail verification.

### ⚠️ No Secrets in Code
API keys are read from environment variables only. Never commit `.env` files.

---

## Files Created/Modified

### New Files (21)
- `src/agnetwork/tools/llm/__init__.py`
- `src/agnetwork/tools/llm/types.py`
- `src/agnetwork/tools/llm/factory.py`
- `src/agnetwork/tools/llm/structured.py`
- `src/agnetwork/tools/llm/adapters/__init__.py`
- `src/agnetwork/tools/llm/adapters/base.py`
- `src/agnetwork/tools/llm/adapters/fake.py`
- `src/agnetwork/tools/llm/adapters/anthropic.py`
- `src/agnetwork/tools/llm/adapters/openai.py`
- `src/agnetwork/prompts/__init__.py`
- `src/agnetwork/prompts/research_brief.py`
- `src/agnetwork/prompts/target_map.py`
- `src/agnetwork/prompts/outreach.py`
- `src/agnetwork/prompts/meeting_prep.py`
- `src/agnetwork/prompts/followup.py`
- `src/agnetwork/prompts/critic.py`
- `src/agnetwork/kernel/llm_executor.py`
- `tests/test_llm_adapters.py`
- `tests/test_llm_structured.py`
- `tests/test_llm_skills.py`

### Modified Files (7)
- `.env.example` - Added LLM configuration variables
- `src/agnetwork/config.py` - Added LLMConfig class
- `src/agnetwork/kernel/models.py` - Added ExecutionMode enum
- `src/agnetwork/kernel/executor.py` - Added LLM mode support
- `src/agnetwork/kernel/__init__.py` - Export ExecutionMode
- `src/agnetwork/cli.py` - Added --mode flag
- `pyproject.toml` - Added optional dependencies

---

## Dependencies Added

```toml
[project.optional-dependencies]
llm = ["anthropic>=0.18.0", "openai>=1.12.0"]
anthropic = ["anthropic>=0.18.0"]
openai = ["openai>=1.12.0"]
all = ["anthropic>=0.18.0", "openai>=1.12.0"]
```

Install with: `pip install -e ".[llm]"` or `pip install -e ".[anthropic]"`

---

## Test Results

```
116 passed, 2 skipped in 1.54s
```

Skipped tests are live API tests (require actual API keys).

---

## Follow-ups for Future Milestones

### M4: Retrieval / RAG
- Connect web search results to research_brief sources
- Add source attribution to claims
- Reduce assumption flags with real evidence

### M5: Web Evidence
- Web scraping for company data
- LinkedIn profile parsing
- News/PR extraction

### M6: Human-in-the-Loop
- Review UI for LLM drafts
- Accept/edit/reject workflow
- Feedback loop for prompt tuning

---

## Quick Reference

```bash
# Check LLM status
python -c "from agnetwork.tools.llm import LLMFactory; f = LLMFactory.from_env(); print('Enabled:', f.is_enabled)"

# Run with LLM
AG_LLM_ENABLED=1 ag run-pipeline TestCorp --snapshot "desc" --mode llm

# Run tests
pytest tests/test_llm_*.py -v

# Lint
ruff check .
```

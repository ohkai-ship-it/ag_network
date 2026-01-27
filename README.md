# AG Network - Autonomous Business Development Agent

**Status**: ✅ **v0.1 + M1-M7 Complete**  
**Package**: `agnetwork`  
**Documentation**: `COMPLETION_SUMMARY.md`, `M7_IMPLEMENTATION_SUMMARY.md`, `PROTOCOL.md`

**New in M7**: Configurable workspaces with isolated storage, Work Ops & Personal Ops skill packs, per-workspace preferences!

---

## Quick Start

```bash
# Install (one-time)
pip install -e .

# Install with LLM support (optional)
pip install -e ".[llm]"

# Run a command (manual mode - deterministic)
ag research "Your Company" \
  --snapshot "Description" \
  --pain "Problem 1" \
  --trigger "Event 1" \
  --competitor "Rival"

# Run full pipeline with LLM mode (requires API key)
AG_LLM_ENABLED=1 ag run-pipeline "Your Company" --snapshot "Description" --mode llm

# Check results
ls runs/
cat runs/<latest>/artifacts/research_brief.md

# Validate a run
ag validate-run runs/<run_folder>
```

---

## What's Inside

```
ag_network/
├── README.md                      ← This file
├── COMPLETION_SUMMARY.md          ← v0.1 project summary
├── M3_COMPLETION_SUMMARY.md       ← LLM tooling summary (NEW)
├── PROTOCOL.md                    ← Execution log
├── pyproject.toml                 ← Dependencies
├── .github/workflows/ci.yml       ← CI pipeline (ruff + pytest)
│
├── src/agnetwork/                 ← Source code
│   ├── cli.py                     ← CLI commands (8 total)
│   ├── config.py                  ← Configuration + LLMConfig
│   ├── orchestrator.py            ← Run system & logging
│   ├── versioning.py              ← Artifact/skill versioning
│   ├── validate.py                ← Run validation
│   ├── kernel/                    ← Task/Plan/Executor (M2)
│   │   ├── models.py              ← TaskSpec, Plan, Step, ExecutionMode
│   │   ├── executor.py            ← KernelExecutor
│   │   └── llm_executor.py        ← LLMSkillExecutor (M3)
│   ├── tools/llm/                 ← LLM integration (M3)
│   │   ├── adapters/              ← Anthropic, OpenAI, Fake
│   │   ├── factory.py             ← Role-based routing
│   │   └── structured.py          ← JSON parse + repair
│   ├── prompts/                   ← Prompt library (M3)
│   ├── models/core.py             ← Pydantic models
│   ├── storage/sqlite.py          ← Database operations
│   ├── tools/ingest.py            ← Source ingestion
│   └── skills/                    ← Skill implementations
│
├── tests/                         ← Tests (437+ passing)
└── runs/                          ← Execution artifacts
```

---

## Features

✅ **19 CLI Commands**: BD pipeline, Work Ops, Personal Ops, memory, CRM, workspace, prefs  
✅ **Global --workspace**: Scope any command to a specific workspace  
✅ **Execution Modes**: Manual (deterministic) or LLM (AI-assisted)  
✅ **LLM Integration**: Anthropic Claude, OpenAI GPT, Fake adapter for testing  
✅ **Structured Output**: Pydantic validation + repair loop  
✅ **Run System**: Timestamped, immutable, auditable runs  
✅ **Artifacts**: Markdown + JSON outputs with version metadata  
✅ **Logging**: JSONL worklog + JSON status tracking  
✅ **Database**: SQLite for sources & traceability  
✅ **Workspace Isolation**: Per-workspace database, runs, and preferences  
✅ **CI Pipeline**: GitHub Actions for ruff + pytest  
✅ **Tests**: 437+ passing, 0 lint errors

---

## CLI Commands

### Global Options

| Option | Description |
|--------|-------------|
| `--workspace, -w <name>` | Run command in a specific workspace context |

### BD Pipeline Commands

| Command | Description |
|---------|-------------|
| `ag research <company>` | Generate account research brief |
| `ag targets <company>` | Create prospect target map |
| `ag outreach <company>` | Draft outreach messages |
| `ag prep <company>` | Prepare meeting pack |
| `ag followup <company>` | Create post-meeting follow-up |
| `ag run-pipeline <company>` | Run full BD pipeline (supports `--mode llm`) |

### Work Ops Commands

| Command | Description |
|---------|-------------|
| `ag meeting-summary` | Generate meeting summary from notes |
| `ag status-update` | Generate weekly status update |
| `ag decision-log` | Generate ADR-style decision record |

### Personal Ops Commands

| Command | Description |
|---------|-------------|
| `ag weekly-plan` | Generate weekly plan with goals |
| `ag errand-list` | Generate organized errand list |
| `ag travel-outline` | Generate travel itinerary |

### Workspace Commands

| Command | Description |
|---------|-------------|
| `ag workspace create <name>` | Create new isolated workspace |
| `ag workspace list` | List all registered workspaces |
| `ag workspace show [name]` | Show workspace details |
| `ag workspace set-default <name>` | Set default workspace |
| `ag workspace doctor [name]` | Run health checks |

### Other Commands

| Command | Description |
|---------|-------------|
| `ag status` | Show recent runs |
| `ag validate-run <path>` | Validate run folder integrity |
| `ag memory search <query>` | Search sources/artifacts |
| `ag memory rebuild-index` | Rebuild FTS5 indexes |
| `ag crm export-run <run_id>` | Export run as CRM package |
| `ag crm list <entities>` | List CRM entities |
| `ag sequence plan <run_id>` | Generate outreach sequence |
| `ag prefs show` | Show workspace preferences |
| `ag prefs set <key> <value>` | Set preference |

---

## LLM Mode (M3)

Enable AI-assisted generation with:

```bash
# Set environment variables
export AG_LLM_ENABLED=1
export ANTHROPIC_API_KEY=sk-ant-...  # or OPENAI_API_KEY

# Run pipeline with LLM
ag run-pipeline "TestCorp" --snapshot "AI startup" --mode llm
```

See [M3_COMPLETION_SUMMARY.md](M3_COMPLETION_SUMMARY.md) for full details on:
- Role configuration (draft, critic, extractor)
- Structured output flow
- Testing with FakeAdapter
- Safety notes

---

## Key Files

| File | Purpose |
|------|---------|
| [COMPLETION_SUMMARY.md](COMPLETION_SUMMARY.md) | Full project overview & results |
| [PROTOCOL.md](PROTOCOL.md) | Execution log per Master Orchestrator Protocol |
| [src/agnetwork/cli.py](src/agnetwork/cli.py) | All CLI commands |
| [src/agnetwork/orchestrator.py](src/agnetwork/orchestrator.py) | Run system & logging |
| [src/agnetwork/versioning.py](src/agnetwork/versioning.py) | Artifact versioning (M1) |
| [src/agnetwork/validate.py](src/agnetwork/validate.py) | Run validation (M1) |
| [tests/](tests/) | Unit tests (33 passing) |

---

## Testing

```bash
# Run all tests (116 passing)
pytest tests/ -v

# Run LLM-specific tests
pytest tests/test_llm_*.py -v

# Lint check
ruff check .

# Full CI simulation
ruff check . && pytest tests/ -v
```

---

## Artifact Versioning (M1)

All JSON artifacts now include a `meta` block:

```json
{
  "company": "TechCorp",
  "snapshot": "...",
  "meta": {
    "artifact_version": "1.0",
    "skill_name": "research_brief",
    "skill_version": "1.0",
    "generated_at": "2026-01-25T16:27:18.252124+00:00",
    "run_id": "20260125_162718__testcompany__research"
  }
}
```

---

## Architecture

```
CLI (Typer)
    ↓
Commands (research, targets, outreach, prep, followup, validate-run)
    ↓
RunManager (orchestrator.py)
    ├── Creates: runs/<timestamp>__<slug>__<command>/
    ├── Logs: agent_worklog.jsonl + agent_status.json
    ├── Saves: inputs.json + sources/ + artifacts/
    └── Injects: version metadata via versioning.py
    ↓
Skills (research_brief.py + Jinja2 templates)
    ├── Generates: Markdown output
    └── Returns: JSON data
    ↓
Storage (SQLite + Files)
    ├── Database: sources, companies, artifacts, claims
    └── Files: MD, JSON, logs
    ↓
Models (Pydantic)
    └── Validates: All inputs & outputs
```

---

## Tech Stack

- **Python 3.11+** (tested on 3.14)
- **Typer 0.21.1** - CLI framework
- **Pydantic 2.12.5** - Data validation
- **Jinja2 3.1.6** - Templates
- **SQLite** - Local database
- **pytest 9.0.2** - Testing
- **ruff 0.14.14** - Linting

---

## Recent Runs (Examples)

```
runs/
├── 20260125_143654__techcorp__research/
│   ├── inputs.json
│   ├── artifacts/
│   │   ├── research_brief.md      ✅ Generated
│   │   └── research_brief.json    ✅ With meta block
│   └── logs/
│       ├── run.log
│       ├── agent_worklog.jsonl
│       └── agent_status.json
└── 20260125_162718__testcompany__research/
    └── ...
```

---

## Next Steps

1. **Test** the CLI: `ag research "Test Company" --snapshot "..."`
2. **Try LLM mode**: Set `AG_LLM_ENABLED=1` and run with `--mode llm`
3. **Check** test results: `pytest tests/ -v`
4. **Plan** M4: Retrieval / RAG for web evidence

---

## Questions?

- **How does it work?** → See [PROTOCOL.md](PROTOCOL.md)
- **What was built?** → See [COMPLETION_SUMMARY.md](COMPLETION_SUMMARY.md)
- **LLM integration?** → See [M3_COMPLETION_SUMMARY.md](M3_COMPLETION_SUMMARY.md)
- **Workspaces & Isolation?** → See [M7_IMPLEMENTATION_SUMMARY.md](M7_IMPLEMENTATION_SUMMARY.md)

---

## M7: Workspaces (NEW!)

### Create Isolated Workspaces

```bash
# Create work workspace
ag workspace create work --set-default
ag prefs set tone professional

# Create personal workspace
ag workspace create personal
ag prefs set tone casual --workspace personal

# List all workspaces
ag workspace list

# Check workspace health
ag workspace doctor work
```

### Work Ops Skills

```bash
# Meeting summaries
ag meeting-summary --topic "Q1 Planning" --notes "- Discussed budget..."

# Status updates
ag status-update --accomplishment "Completed M7" --in-progress "Testing"

# Decision logs (ADR-style)
ag decision-log --title "Use PostgreSQL" --context "Need a database" --decision "PostgreSQL"
```

### Personal Ops Skills

```bash
# Weekly planning
ag weekly-plan --goal "Exercise 3x" --goal "Read book" --monday "Team standup"

# Errand lists
ag errand-list --errand "Grocery store" --errand "Post office"

# Travel planning
ag travel-outline --destination "Paris" --start 2026-02-10 --end 2026-02-17
```

### Using --workspace Flag

```bash
# Run BD command in a specific workspace
ag --workspace work research "TechCorp" --snapshot "AI startup"

# Search memory in a specific workspace
ag --workspace work memory search "machine learning"

# Create artifacts in personal workspace
ag --workspace personal weekly-plan --goal "Exercise"
```

### Workspace Isolation

- ✅ Each workspace has isolated database, runs, and exports
- ✅ Database guard prevents cross-workspace access
- ✅ Per-workspace preferences and policies
- ✅ 11 isolation tests verify boundaries

See [M7_IMPLEMENTATION_SUMMARY.md](M7_IMPLEMENTATION_SUMMARY.md) for complete documentation.

---

**Built with Master Orchestrator Protocol** ✅  
v0.1 + M1-M7 Complete

---

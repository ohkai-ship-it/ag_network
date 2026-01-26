# AG Network - Autonomous Business Development Agent

**Status**: ✅ **v0.1 Complete** + **M1 Platform Hardening**  
**Package**: `agnetwork`  
**Documentation**: `COMPLETION_SUMMARY.md`, `PROTOCOL.md`

---

## Quick Start

```bash
# Install (one-time)
pip install -e .

# Run a command
bd research "Your Company" \
  --snapshot "Description" \
  --pain "Problem 1" \
  --trigger "Event 1" \
  --competitor "Rival"

# Check results
ls runs/
cat runs/<latest>/artifacts/research_brief.md

# Validate a run
bd validate-run runs/<run_folder>
```

---

## What's Inside

```
ag_network/
├── README.md                      ← This file
├── COMPLETION_SUMMARY.md          ← Full project summary
├── PROTOCOL.md                    ← Execution log
├── pyproject.toml                 ← Dependencies
├── .github/workflows/ci.yml       ← CI pipeline (ruff + pytest)
│
├── src/agnetwork/                 ← Source code
│   ├── cli.py                     ← CLI commands (7 total)
│   ├── config.py                  ← Configuration
│   ├── orchestrator.py            ← Run system & logging
│   ├── versioning.py              ← Artifact/skill versioning (M1)
│   ├── validate.py                ← Run validation (M1)
│   ├── models/core.py             ← Pydantic models
│   ├── storage/sqlite.py          ← Database operations
│   ├── tools/ingest.py            ← Source ingestion
│   └── skills/research_brief.py   ← Skill implementations
│
├── tests/                         ← Tests (33 passing)
│   ├── test_models.py
│   ├── test_orchestrator.py
│   ├── test_skills.py
│   ├── test_versioning.py         ← Versioning tests (M1)
│   ├── test_validate.py           ← Validation tests (M1)
│   └── golden/                    ← Golden run tests (M1)
│       └── test_golden_runs.py
│
├── data/bd.sqlite                 ← Database
└── runs/                          ← Execution artifacts
```

---

## Features

✅ **7 CLI Commands**: research, targets, outreach, prep, followup, status, validate-run  
✅ **Run System**: Timestamped, immutable, auditable runs  
✅ **Artifacts**: Markdown + JSON outputs with version metadata  
✅ **Logging**: JSONL worklog + JSON status tracking  
✅ **Database**: SQLite for sources & traceability  
✅ **CI Pipeline**: GitHub Actions for ruff + pytest  
✅ **Golden Tests**: Regression tests for artifact structure  
✅ **Validation**: CLI command to validate run integrity  
✅ **Tests**: 33/33 passing, 0 lint errors

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `bd research <company>` | Generate account research brief |
| `bd targets <company>` | Create prospect target map |
| `bd outreach <company>` | Draft outreach messages |
| `bd prep <company>` | Prepare meeting pack |
| `bd followup <company>` | Create post-meeting follow-up |
| `bd status` | Show recent runs |
| `bd validate-run <path>` | Validate run folder integrity |

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
# Run all tests
pytest tests/ -v

# Run golden tests only
pytest tests/golden/ -v

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

1. **Test** the CLI: `bd research "Test Company" --snapshot "..."`
2. **Check** test results: `pytest tests/ -v`
3. **Validate** runs: `bd validate-run runs/<folder>`
4. **Plan** M2: Agent Kernel + Skill Contract Standardization

---

## Questions?

- **How does it work?** → See [PROTOCOL.md](PROTOCOL.md)
- **What was built?** → See [COMPLETION_SUMMARY.md](COMPLETION_SUMMARY.md)
- **What's the architecture?** → See `src/agnetwork/`

---

**Built with Master Orchestrator Protocol** ✅  
v0.1 + M1 Platform Hardening Complete

---

# BD Copilot - Autonomous Business Development Agent

**Status**: ✅ **v0.1 Complete** - Production Ready  
**Location**: `./bd-copilot/`  
**Documentation**: `COMPLETION_SUMMARY.md` (this folder), `bd-copilot/README.md`, `bd-copilot/PROTOCOL.md`

---

## Quick Start

```bash
cd bd-copilot

# Install (one-time)
pip install -e .

# Run a command
python -m agnetwork.cli research "Your Company" \
  --snapshot "Description" \
  --pain "Problem 1" \
  --trigger "Event 1" \
  --competitor "Rival"

# Check results
ls runs/latest/artifacts/
cat runs/latest/artifacts/research_brief.md
```

---

## What's Inside

```
ag_network/
├── COMPLETION_SUMMARY.md          ← Full project summary
├── Cursor_Prompt_BD_Copilot...md  ← Original specification
└── bd-copilot/                    ← Main project
    ├── README.md                  ← User guide
    ├── PROTOCOL.md                ← Execution log
    ├── pyproject.toml             ← Dependencies
    ├── src/agnetwork/             ← Source code (13 files)
    ├── tests/                     ← Tests (7 passing)
    ├── data/bd.sqlite             ← Database
    └── runs/                      ← Execution artifacts
```

---

## Features

✅ **5 CLI Commands**: research, targets, outreach, prep, followup  
✅ **Run System**: Timestamped, immutable, auditable runs  
✅ **Artifacts**: Markdown + JSON outputs for each command  
✅ **Logging**: JSONL worklog + JSON status tracking  
✅ **Database**: SQLite for sources & traceability  
✅ **Tests**: 7/7 passing, 0 lint errors  
✅ **Documentation**: 1000+ lines across guides

---

## Key Files

| File | Purpose |
|------|---------|
| [COMPLETION_SUMMARY.md](COMPLETION_SUMMARY.md) | Full project overview & results |
| [bd-copilot/README.md](bd-copilot/README.md) | User guide & command reference |
| [bd-copilot/PROTOCOL.md](bd-copilot/PROTOCOL.md) | Execution log per Master Orchestrator Protocol |
| [bd-copilot/src/agnetwork/cli.py](bd-copilot/src/agnetwork/cli.py) | All 5 commands |
| [bd-copilot/src/agnetwork/orchestrator.py](bd-copilot/src/agnetwork/orchestrator.py) | Run system & logging |
| [bd-copilot/tests/](bd-copilot/tests/) | Unit tests (7/7 passing) |

---

## Testing

```bash
cd bd-copilot
pytest tests/ -v                    # Run all tests (7/7 pass)
python -m ruff check src/ tests/    # Lint check (0 errors)
```

---

## Architecture

```
CLI (Typer)
    ↓
Commands (research, targets, outreach, prep, followup)
    ↓
RunManager (orchestrator.py)
    ├── Creates: runs/<timestamp>__<slug>__<command>/
    ├── Logs: agent_worklog.jsonl + agent_status.json
    └── Saves: inputs.json + sources/ + artifacts/
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
│   │   └── research_brief.json    ✅ Generated
│   └── logs/
│       ├── run.log
│       ├── agent_worklog.jsonl
│       └── agent_status.json
└── 20260125_143717__techcorp__targets/
    └── ...
```

---

## Next Steps

1. **Review** [COMPLETION_SUMMARY.md](COMPLETION_SUMMARY.md) for full details
2. **Test** the CLI: `cd bd-copilot && python -m agnetwork.cli research ...`
3. **Read** [bd-copilot/README.md](bd-copilot/README.md) for command reference
4. **Check** test results: `pytest tests/ -v`
5. **Plan** v0.2: LLM integration, web scraping, automation

---

## Questions?

- **How does it work?** → See [bd-copilot/PROTOCOL.md](bd-copilot/PROTOCOL.md)
- **How do I use it?** → See [bd-copilot/README.md](bd-copilot/README.md)
- **What was built?** → See [COMPLETION_SUMMARY.md](COMPLETION_SUMMARY.md)
- **What's the architecture?** → See `bd-copilot/src/agnetwork/`

---

**Built with Master Orchestrator Protocol** ✅  
All specifications from `Cursor_Prompt_BD_Copilot_Master_Orchestrator.md` implemented.

---

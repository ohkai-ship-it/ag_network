# BD Copilot v0.1 - CLI Tool for Business Development Workflows

**Autonomous, reproducible, structured BD artifacts** for research → targets → outreach → meeting prep → follow-up.

## Features

- **Local-first CLI**: No external API dependencies for v0.1
- **Reproducible runs**: Each command creates a timestamped, auditable run folder
- **Traceability**: Facts vs assumptions clearly marked in all outputs
- **Structured outputs**: Both human-readable Markdown and JSON artifacts
- **Logging**: Agent worklog and status files track all decisions

## Quick Start

### Installation

```bash
cd bd-copilot
pip install -e .
```

Optionally, install dev dependencies for testing:

```bash
pip install -e ".[dev]"
```

### Environment Setup

Copy `.env.example` to `.env` and configure (optional—defaults work for local use):

```bash
cp .env.example .env
```

### First Command: Research a Company

```bash
bd research "Acme Corp" \
  --snapshot "Fortune 500 manufacturing company, ~$10B revenue" \
  --pain "Supply chain disruption" \
  --pain "Rising operational costs" \
  --trigger "New CTO announced" \
  --trigger "Q3 earnings beat expectations" \
  --competitor "Rival Corp" \
  --competitor "Competitor LLC"
```

This creates a run folder with:
- `inputs.json`: Full parameters
- `artifacts/research_brief.md`: Human-readable brief
- `artifacts/research_brief.json`: Structured data
- `logs/agent_worklog.jsonl`: Action log
- `logs/agent_status.json`: Execution status

## Available Commands

### `bd research <company>`

Generate an account research brief with snapshot, pains, triggers, competitors, and personalization angles.

**Options:**
- `--snapshot, -s`: Company description (required)
- `--pain, -p`: Key pain points (repeatable)
- `--trigger, -t`: Buying triggers (repeatable)
- `--competitor, -c`: Competitor names (repeatable)
- `--sources, -f`: JSON file with ingested sources (optional)

**Example output:**
- `research_brief.md`: Formatted markdown brief
- `research_brief.json`: Structured JSON data

---

### `bd targets <company>`

Generate prospect target map with roles, titles, and hypotheses.

**Options:**
- `--persona, -p`: Target persona (optional)

**Example output:**
- `target_map.md`: Persona table
- `target_map.json`: Structured persona data

---

### `bd outreach <company>`

Create outreach message drafts (email and LinkedIn variants).

**Options:**
- `--persona, -p`: Target persona (required)
- `--channel, -c`: `email` or `linkedin` (default: email)

**Example output:**
- `outreach.md`: Message variants with hook/subject
- `outreach.json`: Structured message data

---

### `bd prep <company>`

Prepare meeting agenda, questions, and stakeholder map.

**Options:**
- `--type, -t`: Meeting type: `discovery`, `demo`, `negotiation` (default: discovery)

**Example output:**
- `meeting_prep.md`: Agenda and questions
- `meeting_prep.json`: Structured prep data

---

### `bd followup <company>`

Generate post-meeting follow-up summary and next steps.

**Options:**
- `--notes, -n`: Meeting notes or path to notes file (required)

**Example output:**
- `followup.md`: Summary and action items
- `followup.json`: Structured follow-up data

---

### `bd status`

Show recent runs and their execution phase.

## Run Folder Anatomy

Each command produces a run folder at `runs/<timestamp>__<slug>__<command>/`:

```
runs/20240125_142530__acme_corp__research/
├── inputs.json                          # Full command inputs + defaults
├── sources/
│   ├── src_abc123.json                  # Ingested sources
│   └── ...
├── artifacts/
│   ├── research_brief.md                # Human-readable output
│   └── research_brief.json              # Structured data
└── logs/
    ├── run.log                          # Detailed execution log
    ├── agent_worklog.jsonl              # Action log (one entry per line)
    └── agent_status.json                # Execution status snapshot
```

### Key Files

**inputs.json**
```json
{
  "company": "Acme Corp",
  "snapshot": "Fortune 500...",
  "pains": ["Supply chain disruption", "Rising costs"],
  "triggers": ["New CTO", "Q3 earnings"],
  "competitors": ["Rival Corp"],
  "sources_ingested": 2
}
```

**agent_status.json**
```json
{
  "session_id": "20240125_142530__acme_corp__research",
  "started_at": "2024-01-25T14:25:30...",
  "last_updated": "2024-01-25T14:25:35...",
  "current_phase": "2",
  "phases_completed": ["0", "1"],
  "phases_in_progress": ["2"],
  "phases_blocked": [],
  "issues_fixed": [],
  "issues_remaining": [],
  "metrics": {
    "tests_passing": 5,
    "lint_status": "pass",
    "coverage": 85.0
  }
}
```

**agent_worklog.jsonl** (one JSON object per line)
```jsonl
{"timestamp": "2024-01-25T14:25:30...", "phase": "0", "action": "Initialize run", "status": "success", "changes_made": [], ...}
{"timestamp": "2024-01-25T14:25:31...", "phase": "1", "action": "Ingest sources", "status": "success", "changes_made": [...], ...}
```

## Data Models

All outputs use Pydantic models for validation:

- **ResearchBrief**: Company snapshot, pains, triggers, competitors, personalization angles
- **TargetMap**: Personas, roles, buying hypotheses
- **OutreachDraft**: Message variants (email/LinkedIn), sequences, objection responses
- **MeetingPrepPack**: Agenda, questions, stakeholder map, listening signals, close plan
- **FollowUpSummary**: Meeting summary, next steps, tasks, CRM notes

See [models/core.py](src/bdcopilot/models/core.py) for full schema.

## Safety & Best Practices

### Secrets
- Never commit `.env` (use `.env.example`)
- All credentials stored in environment variables only
- Database file `data/bd.sqlite` excluded from version control

### Traceability
- Every claim in output is tagged as **sourced** or **ASSUMPTION**
- Sources registered in SQLite for audit trail
- All runs immutable and timestamped

### Audit Trail
- `agent_worklog.jsonl`: Timestamped log of all meaningful actions
- `agent_status.json`: Snapshot of execution state
- `run.log`: Detailed debug output

## Testing

Run the test suite:

```bash
pytest tests/ -v
```

Run with coverage:

```bash
pytest tests/ --cov=src/bdcopilot --cov-report=html
```

## Code Quality

Format and check code:

```bash
ruff check src/ tests/
```

## Architecture

### Core Modules

- **cli.py**: Typer CLI entry point
- **config.py**: Configuration and environment handling
- **orchestrator.py**: Run management, logging, status tracking
- **models/core.py**: Pydantic data models
- **storage/sqlite.py**: Database for sources and traceability
- **tools/ingest.py**: Source ingestion (text, files, URLs)
- **skills/**: Generation skills (research_brief, target_map, outreach, etc.)

### Tech Stack

- **Python 3.11+**
- **Typer**: CLI framework
- **Pydantic**: Data validation and models
- **Jinja2**: Template rendering
- **SQLite**: Local storage (stdlib)
- **pytest**: Testing
- **ruff**: Linting and formatting

## v0.1 Scope

✅ **Included:**
- CLI with 5 core commands
- Run system with logging and status tracking
- Manual source ingestion
- Research brief generation with templates
- Tests and quality checks

❌ **Not included (v0.2+):**
- Automatic email/LinkedIn sending
- Web scraping or API integrations
- CRM writes
- LLM-powered generation
- UI/web dashboard

## Development Workflow

1. **Create a new feature branch** and make changes
2. **Test locally**: `pytest tests/`
3. **Run linter**: `ruff check src/`
4. **Test a command**: `bd research "Test Corp" --snapshot "Test"`
5. **Check the run folder**: `ls -la runs/latest/`
6. **Commit and push** with atomic commits

## Future Enhancements (v0.2+)

- LLM integration for AI-powered artifact generation
- Web scraping for URL sources
- Email template library expansion
- CRM integration (read-only for now)
- Sequence automation (with approval gates)
- Multi-company research batching
- Export to Notion, HubSpot, Salesforce

## Support & Contribution

For issues, feature requests, or contributions:
1. Document the issue clearly
2. Provide example commands and outputs
3. Check existing runs folder for debugging info

---

**BD Copilot v0.1** © 2024. Built for reproducible, auditable business development workflows.

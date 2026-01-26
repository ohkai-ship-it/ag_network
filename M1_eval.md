# 🔄 AG Network Refactor Sync Package

**Generated**: 2026-01-26  
**Status**: ✅ **M1 Platform Hardening Complete**  
**Tests**: 33 passing, 0 warnings, 0 lint errors

---

## 1. What Changed in the Refactor (Bullet Summary)

- **Renamed package**: `bdcopilot` → `agnetwork`
- **CLI command**: `bd` → `ag` (see `pyproject.toml`)
- **Added M1 Platform Hardening**:
  - `versioning.py` – artifact & skill version injection
  - `validate.py` – run folder validation CLI
  - Golden run tests in `tests/golden/`
  - CI workflow at `.github/workflows/ci.yml`
- **All artifacts now include `meta` block** with versioning
- **33 tests passing**, 0 warnings, 0 lint errors

### M1 Eval Fixes Applied (2026-01-26)

| Issue | Fix |
|-------|-----|
| `datetime.utcnow()` deprecation (3 warnings) | Replaced with `datetime.now(timezone.utc)` in all 6 models |
| `ruff` in runtime dependencies | Moved to `[project.optional-dependencies].dev` |
| Legacy `BD_*` env vars | Renamed to `AG_DB_PATH`, `AG_RUNS_DIR`, `AG_LOG_LEVEL` |
| Database `bd.sqlite` | Renamed to `ag.sqlite` |
| "BD Copilot" docstrings | Updated to "AG Network" |

**Result**: 33 tests passing, 0 warnings, 0 lint errors

---

## 2. Packaging + Dependencies

**pyproject.toml**:
```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ag-network"
version = "0.1.0"
description = "Agent network: Workflow orchestration for agentic AI with a multipurpose skillset"
readme = "README.md"
requires-python = ">=3.11"
authors = [{name = "AG Network Team"}]
license = {text = "MIT"}

dependencies = [
    "typer[all]>=0.9.0",
    "pydantic>=2.0.0",
    "jinja2>=3.1.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "mypy>=1.5.0",
    "ruff>=0.1.0",
]

[project.scripts]
ag = "agnetwork.cli:app"

[tool.setuptools]
packages = ["agnetwork"]
package-dir = {"" = "src"}

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "C901",   # mccabe complexity
]
ignore = ["E501"]  # line too long (handled by formatter)

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
```

| Key | Value |
|-----|-------|
| **Package name** | `ag-network` |
| **Import name** | `agnetwork` |
| **Layout** | `src/agnetwork/...` |
| **Python** | `>=3.11` |

---

## 3. Project Tree (depth 4)

```
ag_network/
├── README.md
├── COMPLETION_SUMMARY.md
├── PROTOCOL.md
├── pyproject.toml
├── .github/
│   └── workflows/
│       └── ci.yml              ← CI pipeline (ruff + pytest)
├── data/
│   └── ag.sqlite
├── runs/
│   └── 20260125_162718__testcompany__research/
│       ├── inputs.json
│       ├── artifacts/
│       │   ├── research_brief.json
│       │   └── research_brief.md
│       ├── logs/
│       │   ├── agent_status.json
│       │   └── agent_worklog.jsonl
│       └── sources/
├── src/
│   └── agnetwork/
│       ├── __init__.py
│       ├── cli.py              ← CLI entrypoint (7 commands)
│       ├── config.py           ← Config system
│       ├── orchestrator.py     ← RunManager (run creation, logging)
│       ├── versioning.py       ← Artifact/skill version injection
│       ├── validate.py         ← Run validation
│       ├── models/
│       │   ├── __init__.py
│       │   └── core.py         ← Pydantic models
│       ├── skills/
│       │   ├── __init__.py
│       │   └── research_brief.py
│       ├── storage/
│       │   ├── __init__.py
│       │   └── sqlite.py       ← SQLite schema + ops
│       ├── tools/
│       │   ├── __init__.py
│       │   └── ingest.py       ← Source ingestion
│       └── templates/          ← (empty, Jinja inline)
└── tests/
    ├── conftest.py
    ├── test_models.py
    ├── test_orchestrator.py
    ├── test_skills.py
    ├── test_validate.py
    ├── test_versioning.py
    └── golden/
        └── test_golden_runs.py ← CLI regression tests
```

---

## 4. Entrypoints

**Console script** (pyproject.toml):
```toml
[project.scripts]
ag = "agnetwork.cli:app"
```

| Item | Value |
|------|-------|
| **CLI module** | `src/agnetwork/cli.py` |
| **Framework** | Typer |
| **Commands** | `research`, `targets`, `outreach`, `prep`, `followup`, `status`, `validate-run` |

---

## 5. Agent Backbone

### 5.1 Run System: `RunManager`

**Location**: `src/agnetwork/orchestrator.py`

```python
class RunManager:
    """Manages run folders and logging."""

    def __init__(self, command: str, slug: str):
        """Initialize a new run session."""
        self.command = command
        self.slug = slug
        self.timestamp = datetime.now(timezone.utc)
        self.run_id = f"{self.timestamp.strftime('%Y%m%d_%H%M%S')}__{slug}__{command}"
        self.run_dir = config.runs_dir / self.run_id

        # Create run directory structure
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "sources").mkdir(exist_ok=True)
        (self.run_dir / "artifacts").mkdir(exist_ok=True)
        (self.run_dir / "logs").mkdir(exist_ok=True)

        # Initialize logging
        self.logger = self._setup_logger()
        self.worklog_path = self.run_dir / "logs" / "agent_worklog.jsonl"
        self.status_path = self.run_dir / "logs" / "agent_status.json"

        # Initialize status file
        self._init_status()

    def log_action(
        self,
        phase: str,
        action: str,
        status: str,
        changes_made: Optional[list] = None,
        tests_run: Optional[list] = None,
        verification_results: Optional[dict] = None,
        next_action: Optional[str] = None,
        issues_discovered: Optional[list] = None,
    ) -> None:
        """Log an action to the worklog."""
        # → writes to agent_worklog.jsonl

    def save_inputs(self, inputs: Dict[str, Any]) -> None:
        """Save command inputs to inputs.json."""

    def save_artifact(
        self,
        artifact_name: str,
        markdown_content: str,
        json_data: Dict[str, Any],
        skill_name: Optional[str] = None,
    ) -> None:
        """Save both markdown and JSON versions of an artifact."""
        # Injects version metadata via versioning.inject_meta()

    def update_status(self, **kwargs) -> None:
        """Update agent_status.json."""
```

### 5.2 Logging Files

| File | Format | Purpose |
|------|--------|---------|
| `logs/agent_worklog.jsonl` | JSONL | Action-by-action log |
| `logs/agent_status.json` | JSON | Session state snapshot |
| `logs/run.log` | Text | Python logging output |

### 5.3 Versioning

**Location**: `src/agnetwork/versioning.py`

```python
# Package version
PACKAGE_VERSION = "0.1.0"

# Default versions for artifacts and skills
DEFAULT_ARTIFACT_VERSION = "1.0"
DEFAULT_SKILL_VERSION = "1.0"

# Skill version registry
SKILL_VERSIONS: Dict[str, str] = {
    "research_brief": "1.0",
    "target_map": "1.0",
    "outreach": "1.0",
    "meeting_prep": "1.0",
    "followup": "1.0",
}

def inject_meta(
    json_data: Dict[str, Any],
    artifact_name: str,
    skill_name: str,
    run_id: str,
) -> Dict[str, Any]:
    """Inject metadata into artifact JSON data."""
    result = dict(json_data)
    result["meta"] = create_artifact_meta(
        artifact_name=artifact_name,
        skill_name=skill_name,
        run_id=run_id,
    )
    return result
```

---

## 6. Domain Contracts (Pydantic Models)

**Location**: `src/agnetwork/models/core.py`

```python
class Source(BaseModel):
    """Represents a source of information."""
    id: str
    source_type: str  # "url", "pasted_text", "file"
    content: str
    title: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FactCheck(BaseModel):
    """Tracks whether a claim is sourced or assumed."""
    claim: str
    is_assumption: Optional[bool] = None
    source_ids: List[str] = Field(default_factory=list)
    confidence: Optional[float] = None  # 0.0 to 1.0


class ResearchBrief(BaseModel):
    """Output model for account research."""
    company: str
    snapshot: str
    pains: List[str]
    triggers: List[str]
    competitors: List[str]
    personalization_angles: List[Dict[str, Any]]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TargetMap(BaseModel):
    """Output model for prospect target map."""
    company: str
    personas: List[Dict[str, Any]]  # Role, title, hypotheses
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OutreachVariant(BaseModel):
    """A single outreach message variant."""
    channel: str  # "email" or "linkedin"
    subject_or_hook: Optional[str] = None
    body: str
    personalization_notes: Optional[str] = None


class OutreachDraft(BaseModel):
    """Output model for outreach drafts."""
    company: str
    persona: str
    variants: List[OutreachVariant]
    sequence_steps: List[str]
    objection_responses: Dict[str, str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MeetingPrepPack(BaseModel):
    """Output model for meeting preparation."""
    company: str
    meeting_type: str  # "discovery", "demo", "negotiation"
    agenda: List[str]
    questions: List[str]
    stakeholder_map: Dict[str, str]
    listen_for_signals: List[str]
    close_plan: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FollowUpSummary(BaseModel):
    """Output model for post-meeting follow-up."""
    company: str
    meeting_date: datetime
    summary: str
    next_steps: List[str]
    tasks: List[Dict[str, Any]]
    crm_notes: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

### Artifact JSON Contract

Every artifact includes a `meta` block:

```json
{
  "company": "...",
  "snapshot": "...",
  "...other domain fields...": "...",
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

## 7. SQLite Schema

**Location**: `src/agnetwork/storage/sqlite.py`

```sql
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    run_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL,
    claim_text TEXT NOT NULL,
    is_assumption INTEGER DEFAULT 0,
    source_ids TEXT,
    confidence REAL,
    FOREIGN KEY(artifact_id) REFERENCES artifacts(id)
);
```

---

## 8. Tests + Tooling

### Test Structure

```
tests/
├── conftest.py          ← Fixtures (temp_run_dir)
├── test_models.py       ← Pydantic model tests
├── test_orchestrator.py ← RunManager tests
├── test_skills.py       ← Skill generation tests
├── test_validate.py     ← Validation tests (M1)
├── test_versioning.py   ← Versioning tests (M1)
└── golden/
    └── test_golden_runs.py ← CLI end-to-end tests
```

### Tooling Config (in pyproject.toml)

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "C901"]
ignore = ["E501"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
```

### Current Status

```
33 passed in 1.17s
```

(No warnings - datetime deprecations fixed)

---

## 9. Sample Run Artifacts

**Run folder**: `runs/20260125_162718__testcompany__research/`

### inputs.json

```json
{
  "company": "TestCompany",
  "snapshot": "A test company for M1",
  "pains": [
    "Test pain 1"
  ],
  "triggers": [],
  "competitors": [],
  "sources_ingested": 0
}
```

### artifacts/research_brief.json

```json
{
  "company": "TestCompany",
  "snapshot": "A test company for M1",
  "pains": [
    "Test pain 1"
  ],
  "triggers": [],
  "competitors": [],
  "personalization_angles": [
    {
      "name": "Market Expansion",
      "fact": "TestCompany is expanding into new markets",
      "is_assumption": true
    },
    {
      "name": "Cost Optimization",
      "fact": "TestCompany seeks to optimize operational costs",
      "is_assumption": true
    },
    {
      "name": "Digital Transformation",
      "fact": "TestCompany is undergoing digital transformation",
      "is_assumption": true
    }
  ],
  "meta": {
    "artifact_version": "1.0",
    "skill_name": "research_brief",
    "skill_version": "1.0",
    "generated_at": "2026-01-25T16:27:18.252124+00:00",
    "run_id": "20260125_162718__testcompany__research"
  }
}
```

### artifacts/research_brief.md

```markdown
# Account Research Brief: TestCompany

## Snapshot
A test company for M1

## Key Pains

- Test pain 1


## Triggers


## Competitors


## Personalization Angles


### Angle: Market Expansion
- **Fact**: TestCompany is expanding into new markets (ASSUMPTION)


### Angle: Cost Optimization
- **Fact**: TestCompany seeks to optimize operational costs (ASSUMPTION)


### Angle: Digital Transformation
- **Fact**: TestCompany is undergoing digital transformation (ASSUMPTION)
```

### logs/agent_worklog.jsonl

```jsonl
{"timestamp": "2026-01-25T16:27:18.238658+00:00", "phase": "1", "action": "Start research for TestCompany", "status": "success", "changes_made": [], "tests_run": [], "verification_results": {}, "next_action": "Ingest sources", "issues_discovered": []}
{"timestamp": "2026-01-25T16:27:18.241076+00:00", "phase": "2", "action": "Generate research brief", "status": "success", "changes_made": [], "tests_run": [], "verification_results": {}, "next_action": "Create artifacts", "issues_discovered": []}
{"timestamp": "2026-01-25T16:27:18.255283+00:00", "phase": "2", "action": "Complete research command", "status": "success", "changes_made": ["...artifacts/research_brief.md", "...artifacts/research_brief.json"], "tests_run": [], "verification_results": {}, "next_action": null, "issues_discovered": []}
```

### logs/agent_status.json

```json
{
  "session_id": "20260125_162718__testcompany__research",
  "started_at": "2026-01-25T16:27:18.235973+00:00",
  "last_updated": "2026-01-25T16:27:18.254369+00:00",
  "current_phase": "2",
  "phases_completed": [
    "0",
    "1"
  ],
  "phases_in_progress": [
    "2"
  ],
  "phases_blocked": [],
  "issues_fixed": [],
  "issues_remaining": [],
  "metrics": {
    "tests_passing": 0,
    "lint_status": "not_run",
    "coverage": 0.0
  }
}
```

---

## 10. Config System

**Location**: `src/agnetwork/config.py`

```python
class Config:
    """Central configuration object."""

    def __init__(self):
        # Load .env file if it exists
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        # Get project root
        self.project_root = Path(__file__).parent.parent.parent

        # Database
        self.db_path: Path = Path(
            os.getenv("AG_DB_PATH", "data/ag.sqlite")
        )
        if not self.db_path.is_absolute():
            self.db_path = self.project_root / self.db_path

        # Runs directory
        self.runs_dir: Path = Path(
            os.getenv("AG_RUNS_DIR", "runs")
        )
        if not self.runs_dir.is_absolute():
            self.runs_dir = self.project_root / self.runs_dir

        # Logging
        self.log_level: str = os.getenv("AG_LOG_LEVEL", "INFO")

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)


# Global config instance
config = Config()
```

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AG_DB_PATH` | `data/ag.sqlite` | SQLite database path |
| `AG_RUNS_DIR` | `runs` | Run output directory |
| `AG_LOG_LEVEL` | `INFO` | Logging level |

---

## 11. Templates

Templates are **inline Jinja2** in skill classes.

**Example** from `src/agnetwork/skills/research_brief.py`:

```python
class ResearchBriefSkill:
    """Generates account research briefs."""

    def __init__(self):
        self.template = self._get_template()

    def _get_template(self) -> Template:
        template_str = """# Account Research Brief: {{ company }}

## Snapshot
{{ snapshot }}

## Key Pains
{% for pain in pains %}
- {{ pain }}
{% endfor %}

## Triggers
{% for trigger in triggers %}
- {{ trigger }}
{% endfor %}

## Competitors
{% for competitor in competitors %}
- {{ competitor }}
{% endfor %}

## Personalization Angles

{% for angle in personalization_angles %}
### Angle: {{ angle.name }}
- **Fact**: {{ angle.fact }} {% if angle.is_assumption %}(ASSUMPTION){% endif %}

{% endfor %}
"""
        return Template(template_str)

    def generate(
        self,
        company: str,
        snapshot: str,
        pains: List[str],
        triggers: List[str],
        competitors: List[str],
        personalization_angles: List[Dict[str, Any]],
    ) -> tuple[str, Dict[str, Any]]:
        """Generate research brief markdown and JSON data."""
        markdown = self.template.render(...)
        json_data = {...}
        return markdown, json_data
```

The `templates/` folder exists but is currently **empty** (reserved for future externalized templates).

---

## 12. Validation System (M1)

**Location**: `src/agnetwork/validate.py`

### Required Keys

```python
# Required keys for agent_status.json
REQUIRED_STATUS_KEYS = {
    "session_id",
    "started_at",
    "last_updated",
    "current_phase",
    "phases_completed",
    "phases_in_progress",
}

# Required keys for agent_worklog.jsonl entries
REQUIRED_WORKLOG_KEYS = {
    "timestamp",
    "phase",
    "action",
    "status",
}

# Required keys in artifact meta block
REQUIRED_META_KEYS = {
    "artifact_version",
    "skill_name",
    "skill_version",
    "generated_at",
    "run_id",
}
```

### Validation Classes

```python
class ValidationError:
    """Represents a single validation error."""
    file_path: str
    message: str
    line: Optional[int]

class ValidationResult:
    """Result of a validation operation."""
    errors: List[ValidationError]
    warnings: List[ValidationError]
    
    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0
```

### CLI Command

```bash
ag validate-run runs/<run_folder>
```

---

## Summary

This document provides everything needed to:

1. ✅ Understand the new package structure (`agnetwork`)
2. ✅ Know where CLI/kernel/skills/tools/storage live
3. ✅ See the exact entrypoints and console scripts
4. ✅ Understand the run system and logging contracts
5. ✅ Know the Pydantic models and artifact schemas
6. ✅ Review the SQLite schema
7. ✅ See test structure and tooling config
8. ✅ Have real example artifacts to validate against

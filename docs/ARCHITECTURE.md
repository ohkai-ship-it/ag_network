# AG Network Architecture

> **Version**: 0.2.0  
> **Package**: `ag-network`  
> **License**: MIT  
> **Last Updated**: January 28, 2026

---

## Development Coordination

For multi-agent or multi-session development workflows, see:

- **[docs/dev/agent_handoff/](dev/agent_handoff/)** — Source of truth for handoff coordination
  - `CURRENT_STATE.md` — Active branch, test status, remaining tasks
  - `NEXT_PR_PROMPT.md` — Ready-to-paste prompt for next PR
  - `DECISIONS.md` — Architecture Decision Records (ADRs)

---

## Table of Contents

1. [Overview & Purpose](#1-overview--purpose)
2. [Module Responsibilities](#2-module-responsibilities)
3. [Execution Flow](#3-execution-flow)
4. [Data Contracts](#4-data-contracts)
5. [Integration Points](#5-integration-points)
6. [CLI Command Reference](#6-cli-command-reference)
7. [Appendix A: Full Schemas](#appendix-a-full-schemas)
8. [Appendix B: Configuration Reference](#appendix-b-configuration-reference)

---

## 1. Overview & Purpose

**AG Network** is an **autonomous business development (BD) workflow orchestration agent** that automates the research-to-outreach pipeline for sales and business development teams.

### Core Capabilities

- **Multi-step BD pipelines**: research → targets → outreach → meeting prep → follow-up
- **Work Ops & Personal Ops skill packs** for productivity workflows
- **LLM integration** with structured output validation and repair loops
- **Workspace isolation** for multi-context usage (work, personal, clients)
- **CRM integration** via export-first architecture with future vendor adapters
- **Memory/RAG** via SQLite FTS5 full-text search for evidence retrieval

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLI LAYER                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ag research | targets | outreach | prep | followup | run-pipeline  │   │
│  │  ag workspace | crm | sequence | memory | prefs | status            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────────┐
│                            KERNEL LAYER                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────────┐  │
│  │   TaskSpec   │───▶│   Planner    │───▶│     KernelExecutor           │  │
│  │   (inputs)   │    │   (routing)  │    │  (step iteration + verify)   │  │
│  └──────────────┘    └──────────────┘    └──────────────────────────────┘  │
│                                                                             │
│  Execution Modes: MANUAL (deterministic) | LLM (AI-assisted)               │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────────┐
│                            SKILLS LAYER                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  BD Pack         │  Work Ops         │  Personal Ops                │   │
│  │  ─────────────   │  ─────────────    │  ─────────────               │   │
│  │  research_brief  │  meeting_summary  │  weekly_plan                 │   │
│  │  target_map      │  status_update    │  errand_list                 │   │
│  │  outreach        │  decision_log     │  travel_outline              │   │
│  │  meeting_prep    │                   │                              │   │
│  │  followup        │                   │                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────────┐
│                            TOOLS LAYER                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────┐    │
│  │  LLM Adapters  │  │   Web Tools    │  │   CRM Adapters             │    │
│  │  ────────────  │  │   ─────────    │  │   ────────────             │    │
│  │  Anthropic     │  │   fetch        │  │   FileCRMAdapter           │    │
│  │  OpenAI        │  │   clean        │  │   (future: HubSpot,        │    │
│  │  Fake (test)   │  │   deep_links   │  │    Salesforce, Pipedrive)  │    │
│  └────────────────┘  └────────────────┘  └────────────────────────────┘    │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────────┐
│                           STORAGE LAYER                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Episodic Memory          │  Semantic Memory      │  CRM Store      │   │
│  │  ─────────────────        │  ───────────────      │  ─────────      │   │
│  │  Run Folders              │  SQLite + FTS5        │  Accounts       │   │
│  │  (inputs, artifacts,      │  (sources, claims,    │  Contacts       │   │
│  │   logs, sources)          │   artifacts indexes)  │  Activities     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Workspaces: Isolated databases, runs, preferences, policies        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Diagram Description**: The architecture follows a 5-layer design where commands flow down from the CLI through the Kernel (orchestration), Skills (domain logic), Tools (integrations), and finally to Storage. Each layer has clear contracts with the layers above and below it.

---

## 2. Module Responsibilities

### Core Modules

| Module | Path | Responsibility |
|--------|------|----------------|
| **CLI** | `cli.py` | Typer-based CLI with 19+ commands, argument parsing, workspace resolution |
| **Config** | `config.py` | Global configuration, `LLMConfig` from environment variables |
| **Orchestrator** | `orchestrator.py` | `RunManager` for run folder creation and logging |
| **Validate** | `validate.py` | Run folder validation utilities |
| **Versioning** | `versioning.py` | Artifact version metadata injection |

### Kernel Module

| File | Responsibility |
|------|----------------|
| `kernel/models.py` | `TaskType`, `ExecutionMode`, `TaskSpec`, `Plan`, `Step`, `StepStatus` |
| `kernel/contracts.py` | `Skill` protocol, `SkillContext`, `SkillResult`, `Claim`, `ClaimKind`, `ArtifactRef` |
| `kernel/planner.py` | Deterministic task-to-plan mapping, step dependency resolution |
| `kernel/executor.py` | `KernelExecutor`, `ExecutionResult`, step iteration with status tracking |
| `kernel/llm_executor.py` | `LLMSkillExecutor` for AI-assisted generation with repair loops |

### Skills Module

| Directory | Skills | Description |
|-----------|--------|-------------|
| `skills/` | `research_brief`, `target_map`, `outreach`, `meeting_prep`, `followup` | Core BD pipeline skills |
| `skills/work_ops/` | `meeting_summary`, `status_update`, `decision_log` | Work productivity skills |
| `skills/personal_ops/` | `weekly_plan`, `errand_list`, `travel_outline` | Personal productivity skills |

### Tools Module

| Directory | Responsibility |
|-----------|----------------|
| `tools/llm/` | LLM factory, adapters (Anthropic, OpenAI, Fake), structured output parsing |
| `tools/web/` | URL fetching via httpx, HTML cleaning, deep link discovery |
| `tools/ingest.py` | Source ingestion (text, files, URLs) with deduplication |

### Storage Module

| File | Responsibility |
|------|----------------|
| `storage/sqlite.py` | `SQLiteStore` for sources, claims, artifacts with FTS5 indexes |
| `storage/memory.py` | `MemoryStore`, `MemoryRetriever` for RAG-style evidence retrieval |

### CRM Module

| File | Responsibility |
|------|----------------|
| `crm/models.py` | `Account`, `Contact`, `Activity`, `CRMExportPackage`, `CRMExportManifest` |
| `crm/mapping.py` | `PipelineMapper` converts run artifacts to CRM objects |
| `crm/storage.py` | `CRMStore` SQLite tables for accounts, contacts, activities |
| `crm/registry.py` | `CRMAdapterRegistry`, `@crm_adapter` decorator |
| `crm/sequence.py` | `SequenceEngine` for outreach sequence planning |
| `crm/ids.py` | Deterministic ID generation for deduplication |
| `crm/adapters/` | `FileCRMAdapter` (implemented), vendor adapters (planned) |

### Workspaces Module

| File | Responsibility |
|------|----------------|
| `workspaces/context.py` | `WorkspaceContext` dataclass with isolated paths |
| `workspaces/registry.py` | `WorkspaceRegistry` lifecycle management |
| `workspaces/manifest.py` | `WorkspaceManifest` TOML format handling |
| `workspaces/preferences.py` | Per-workspace user preferences |
| `workspaces/policy.py` | Policy enforcement (memory, web, privacy modes) |

---

## 3. Execution Flow

### Main Execution Sequence

```
┌─────────┐     ┌───────────┐     ┌─────────┐     ┌──────────┐     ┌─────────┐
│   CLI   │     │  Kernel   │     │ Planner │     │ Executor │     │  Skill  │
└────┬────┘     └─────┬─────┘     └────┬────┘     └────┬─────┘     └────┬────┘
     │                │                │               │                │
     │  parse args    │                │               │                │
     │───────────────▶│                │               │                │
     │                │                │               │                │
     │  resolve       │                │               │                │
     │  workspace     │                │               │                │
     │───────────────▶│                │               │                │
     │                │                │               │                │
     │  create        │                │               │                │
     │  TaskSpec      │                │               │                │
     │───────────────▶│                │               │                │
     │                │  route task    │               │                │
     │                │───────────────▶│               │                │
     │                │                │               │                │
     │                │  return Plan   │               │                │
     │                │◀───────────────│               │                │
     │                │                │               │                │
     │                │  execute plan  │               │                │
     │                │───────────────────────────────▶│                │
     │                │                │               │                │
     │                │                │               │  for each step │
     │                │                │               │───────────────▶│
     │                │                │               │                │
     │                │                │               │  SkillResult   │
     │                │                │               │◀───────────────│
     │                │                │               │                │
     │                │                │               │  persist       │
     │                │                │               │  artifacts     │
     │                │                │               │────────┐       │
     │                │                │               │        │       │
     │                │                │               │◀───────┘       │
     │                │                │               │                │
     │                │  ExecutionResult               │                │
     │                │◀───────────────────────────────│                │
     │                │                │               │                │
     │  display       │                │               │                │
     │  output        │                │               │                │
     │◀───────────────│                │               │                │
     │                │                │               │                │
```

**Diagram Description**: This sequence shows the typical command execution flow. The CLI parses arguments and resolves the workspace context, then creates a `TaskSpec`. The Planner routes the task to create a `Plan` with ordered `Steps`. The `KernelExecutor` iterates through steps, invoking skills, and persisting artifacts after each successful execution.

### LLM-Assisted Generation Flow

```
┌───────────────────────────────────────────────────────────────────────────┐
│                        LLM SKILL EXECUTION                                │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                │
│   │   Prompt    │────▶│  LLM Call   │────▶│   Parse     │                │
│   │   Builder   │     │  (Adapter)  │     │   Response  │                │
│   └─────────────┘     └─────────────┘     └──────┬──────┘                │
│                                                  │                        │
│                                                  ▼                        │
│                                           ┌─────────────┐                │
│                                           │  Validate   │                │
│                                           │  (Pydantic) │                │
│                                           └──────┬──────┘                │
│                                                  │                        │
│                              ┌───────────────────┼───────────────────┐   │
│                              │                   │                   │   │
│                              ▼                   ▼                   │   │
│                        ┌──────────┐        ┌──────────┐             │   │
│                        │  Valid   │        │ Invalid  │─────────────┘   │
│                        └────┬─────┘        └────┬─────┘                 │
│                             │                   │      Repair Loop      │
│                             │                   │      (max 3 tries)    │
│                             ▼                   │                        │
│                       ┌───────────┐             │                        │
│                       │  Critic   │◀────────────┘                        │
│                       │   Pass    │  (optional)                          │
│                       └─────┬─────┘                                      │
│                             │                                            │
│                             ▼                                            │
│                       ┌───────────┐                                      │
│                       │  Extract  │                                      │
│                       │  Claims   │                                      │
│                       └─────┬─────┘                                      │
│                             │                                            │
│                             ▼                                            │
│                       ┌───────────┐                                      │
│                       │  Build    │                                      │
│                       │  Result   │                                      │
│                       └───────────┘                                      │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

**Diagram Description**: When using LLM mode, the executor builds a prompt, calls the LLM adapter, and parses the JSON response. Pydantic validates the output; if invalid, a repair loop attempts to fix the response (up to 3 times). Optionally, a critic pass reviews quality. Finally, claims are extracted with evidence links, and the `SkillResult` is built.

### CRM Export Flow

```
┌─────────────┐     ┌────────────────┐     ┌───────────────┐     ┌──────────┐
│  Run Folder │────▶│ PipelineMapper │────▶│ CRMExport     │────▶│  File    │
│  (artifacts)│     │                │     │ Package       │     │  Adapter │
└─────────────┘     └────────────────┘     └───────────────┘     └────┬─────┘
                                                                      │
                                                                      ▼
                                                               ┌─────────────┐
                                                               │  exports/   │
                                                               │  ─────────  │
                                                               │  manifest   │
                                                               │  accounts   │
                                                               │  contacts   │
                                                               │  activities │
                                                               └─────────────┘
```

**Diagram Description**: The CRM export flow reads run artifacts, uses `PipelineMapper` to create canonical CRM objects (Account, Contacts, Activities), packages them into a `CRMExportPackage`, and writes to the exports directory via the `FileCRMAdapter`.

---

## 4. Data Contracts

### 4.1 Core Domain Models

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `Source` | Ingested content (URL, text, file) | `id`, `source_type`, `content`, `title`, `metadata` |
| `EvidenceSnippet` | Verbatim quote from source | `source_id`, `url`, `quote` (≤220 chars), `start_char`, `end_char` |
| `PersonalizationAngle` | BD insight for outreach | `name`, `fact`, `is_assumption`, `source_ids`, `evidence` |
| `ResearchBrief` | Company research output | `company`, `snapshot`, `pains`, `triggers`, `competitors`, `personalization_angles` |
| `TargetMap` | Stakeholder mapping | `company`, `personas` (role, title, hypotheses) |
| `OutreachDraft` | Multi-channel messages | `company`, `persona`, `variants`, `sequence_steps`, `objection_responses` |
| `MeetingPrepPack` | Meeting preparation | `company`, `meeting_type`, `agenda`, `questions`, `stakeholder_map`, `close_plan` |
| `FollowUpSummary` | Post-meeting actions | `company`, `meeting_date`, `summary`, `next_steps`, `tasks`, `crm_notes` |

### 4.2 Kernel Models

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `TaskType` | Enum of task kinds | `RESEARCH`, `TARGETS`, `OUTREACH`, `PREP`, `FOLLOWUP`, `PIPELINE` |
| `ExecutionMode` | How to execute | `MANUAL` (template), `LLM` (AI-assisted) |
| `TaskSpec` | Execution request | `task_type`, `workspace`, `inputs`, `constraints`, `requested_artifacts` |
| `Plan` | Execution plan | `plan_id`, `task_spec`, `steps`, `created_at` |
| `Step` | Single execution step | `step_id`, `skill_name`, `input_ref`, `depends_on`, `status` |
| `SkillContext` | Skill execution context | `run_id`, `workspace`, `config`, `sources`, `step_inputs`, `memory_enabled` |
| `SkillResult` | Skill execution output | `output`, `artifacts`, `claims`, `warnings`, `next_actions`, `metrics` |

### 4.3 Evidence & Traceability

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `ClaimKind` | Claim classification | `FACT`, `ASSUMPTION`, `INFERENCE` |
| `Claim` | Traceable assertion | `text`, `kind`, `evidence` (SourceRefs), `confidence` |
| `SourceRef` | Reference to source | `source_id`, `source_type`, `title`, `uri`, `excerpt` |
| `ArtifactRef` | Reference to artifact | `name`, `kind` (MARKDOWN/JSON), `content`, `metadata` |

### 4.4 CRM Models

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `Account` | Company record | `account_id`, `name`, `domain`, `industry`, `tags`, `external_refs` |
| `Contact` | Person record | `contact_id`, `account_id`, `full_name`, `role_title`, `persona_type` |
| `Activity` | Interaction record | `activity_id`, `activity_type`, `subject`, `body`, `run_id`, `artifact_refs` |
| `ActivityType` | Activity classification | `EMAIL`, `LINKEDIN`, `CALL`, `MEETING`, `NOTE`, `TASK` |
| `CRMExportPackage` | Export bundle | `manifest`, `accounts`, `contacts`, `activities` |

### 4.5 Workspace Models

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `WorkspaceContext` | Isolated workspace | `name`, `workspace_id`, `root_dir`, `runs_dir`, `db_path`, `prefs_path` |
| `WorkspaceManifest` | Workspace metadata | `name`, `workspace_id`, `created_at`, `paths`, `policy` |
| `WorkspacePolicy` | Workspace rules | `allow_memory`, `allow_web_fetch`, `privacy_mode` |

---

## 5. Integration Points

### 5.1 LLM Adapters

| Provider | Adapter Class | Status | Capabilities |
|----------|---------------|--------|--------------|
| Anthropic Claude | `AnthropicAdapter` | ✅ Implemented | JSON schema, streaming, tools |
| OpenAI GPT | `OpenAIAdapter` | ✅ Implemented | JSON schema, streaming, tools |
| Fake (Testing) | `FakeAdapter` | ✅ Implemented | Deterministic responses for tests |

**LLM Adapter Protocol:**
```python
@runtime_checkable
class LLMAdapter(Protocol):
    @property
    def provider(self) -> str: ...
    
    @property
    def capabilities(self) -> Dict[str, bool]:
        # supports_json_schema, supports_streaming, supports_tools
        ...
    
    def complete(self, request: LLMRequest) -> LLMResponse: ...
```

### 5.2 CRM Adapters

| System | Adapter Class | Status |
|--------|---------------|--------|
| Local Files | `FileCRMAdapter` | ✅ Implemented |
| HubSpot | `HubSpotAdapter` | 🔮 Planned |
| Salesforce | `SalesforceAdapter` | 🔮 Planned |
| Pipedrive | `PipedriveAdapter` | 🔮 Planned |

**CRM Adapter Protocol:**
```python
@runtime_checkable
class CRMAdapter(Protocol):
    def list_accounts(self, limit: int = 100) -> List[Account]: ...
    def search_accounts(self, query: str, limit: int = 20) -> List[Account]: ...
    def list_contacts(self, account_id: Optional[str], limit: int) -> List[Contact]: ...
    def list_activities(self, account_id: Optional[str], limit: int) -> List[Activity]: ...
    def import_package(self, package: CRMExportPackage, dry_run: bool) -> ImportResult: ...
    def export_package(self, package: CRMExportPackage, output_dir: Path) -> ExportResult: ...
```

### 5.3 Storage Schema

**SQLite Tables:**

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `sources` | Ingested content | `id`, `source_type`, `content`, `title`, `created_at` |
| `claims` | Traceable assertions | `id`, `text`, `kind`, `source_ids`, `confidence` |
| `artifacts` | Generated outputs | `id`, `name`, `kind`, `content`, `run_id` |
| `workspace_meta` | Workspace guard | `workspace_id`, `name`, `created_at` |
| `crm_accounts` | CRM accounts | `account_id`, `name`, `domain`, `industry` |
| `crm_contacts` | CRM contacts | `contact_id`, `account_id`, `full_name`, `role_title` |
| `crm_activities` | CRM activities | `activity_id`, `activity_type`, `run_id`, `artifact_refs` |

**FTS5 Indexes:**
- `sources_fts` — Full-text search on source content
- `artifacts_fts` — Full-text search on artifact content

### 5.4 Run Folder Structure

```
runs/
└── 20260128_143052__acme_corp__research/
    ├── inputs.json                    # Command inputs (company, snapshot, etc.)
    │
    ├── sources/
    │   ├── src_a1b2c3__raw.html       # Raw fetched HTML
    │   ├── src_a1b2c3__clean.txt      # Cleaned text content
    │   ├── src_a1b2c3__meta.json      # Source metadata
    │   └── deeplinks.json             # Deep link discovery audit
    │
    ├── artifacts/
    │   ├── research_brief.md          # Human-readable output
    │   ├── research_brief.json        # Structured output with meta block
    │   ├── target_map.md
    │   ├── target_map.json
    │   ├── outreach.md
    │   └── outreach.json
    │
    └── logs/
        ├── run.log                    # Debug log
        ├── agent_worklog.jsonl        # JSONL action log
        └── agent_status.json          # Run status tracking
```

**Diagram Description**: Each run creates an isolated folder with timestamp, company slug, and command name. Sources are stored with raw/clean/meta triplets. Artifacts are dual-format (Markdown for humans, JSON for machines). Logs capture debug info and structured action tracking.

### 5.5 Artifact JSON Meta Block

Every JSON artifact includes a `meta` block for traceability:

```json
{
  "company": "Acme Corp",
  "snapshot": "Enterprise SaaS for logistics",
  "pains": ["..."],
  "meta": {
    "artifact_version": "1.0",
    "skill_name": "research_brief",
    "skill_version": "1.0",
    "generated_at": "2026-01-28T14:30:52Z",
    "run_id": "20260128_143052__acme_corp__research"
  }
}
```

---

## 6. CLI Command Reference

### 6.1 BD Pipeline Commands

| Command | Description | Key Arguments |
|---------|-------------|---------------|
| `ag research <company>` | Generate research brief | `--snapshot`, `--pain`, `--url`, `--mode` |
| `ag targets <company>` | Map target personas | `--persona`, `--mode` |
| `ag outreach <company>` | Draft outreach messages | `--persona`, `--channel`, `--mode` |
| `ag prep <company>` | Create meeting prep pack | `--type` (discovery/demo/negotiation) |
| `ag followup <company>` | Generate follow-up summary | `--notes`, `--meeting-date` |
| `ag run-pipeline <company>` | Run full BD pipeline | `--mode`, `--deep-links`, `--skip` |

### 6.2 Work Ops Commands

| Command | Description | Key Arguments |
|---------|-------------|---------------|
| `ag meeting-summary` | Summarize meeting notes | `--notes`, `--attendees` |
| `ag status-update` | Generate status update | `--accomplishments`, `--blockers`, `--next` |
| `ag decision-log` | Log a decision | `--title`, `--context`, `--options`, `--decision` |

### 6.3 Personal Ops Commands

| Command | Description | Key Arguments |
|---------|-------------|---------------|
| `ag weekly-plan` | Plan the week | `--goals`, `--constraints` |
| `ag errand-list` | Organize errands | `--items`, `--location` |
| `ag travel-outline` | Plan travel | `--destination`, `--dates`, `--purpose` |

### 6.4 Workspace Commands

| Command | Description |
|---------|-------------|
| `ag workspace create <name>` | Create new workspace |
| `ag workspace list` | List all workspaces |
| `ag workspace show <name>` | Show workspace details |
| `ag workspace set-default <name>` | Set default workspace |
| `ag workspace doctor <name>` | Diagnose workspace issues |

### 6.5 CRM Commands

| Command | Description |
|---------|-------------|
| `ag crm export-run <run_id>` | Export run to CRM format |
| `ag crm export-latest` | Export most recent run |
| `ag crm import <file>` | Import CRM data |
| `ag crm list accounts\|contacts\|activities` | List CRM records |
| `ag crm search <query>` | Search CRM |
| `ag crm stats` | Show CRM statistics |

### 6.6 Memory & Sequence Commands

| Command | Description |
|---------|-------------|
| `ag memory search <query>` | Search memory store |
| `ag memory rebuild-index` | Rebuild FTS5 indexes |
| `ag sequence plan <run_id>` | Generate sequence plan |
| `ag sequence list-templates` | List sequence templates |
| `ag sequence show-template <name>` | Show template details |

### 6.7 Utility Commands

| Command | Description |
|---------|-------------|
| `ag status` | Show system status |
| `ag validate-run <path>` | Validate run folder |
| `ag prefs show` | Show preferences |
| `ag prefs set <key> <value>` | Set preference |
| `ag prefs reset` | Reset to defaults |

---

## Appendix A: Full Schemas

### A.1 Core Domain Models

```python
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class Source(BaseModel):
    """Ingested content from URL, pasted text, or file."""
    id: str
    source_type: str  # "url", "pasted_text", "file"
    content: str
    title: Optional[str] = None
    created_at: datetime
    metadata: Dict[str, Any] = {}


class EvidenceSnippet(BaseModel):
    """Verbatim quote from a source for traceability."""
    source_id: str
    url: Optional[str] = None
    quote: str  # Verbatim quote, max 220 chars
    start_char: Optional[int] = None
    end_char: Optional[int] = None


class PersonalizationAngle(BaseModel):
    """A BD insight that can be used for personalized outreach."""
    name: str
    fact: str
    is_assumption: bool = True
    source_ids: List[str] = []
    evidence: List[EvidenceSnippet] = []  # Required if not assumption


class ResearchBrief(BaseModel):
    """Company research output for BD pipeline."""
    company: str
    snapshot: str
    pains: List[str]
    triggers: List[str]
    competitors: List[str]
    personalization_angles: List[Dict[str, Any]]
    created_at: datetime


class TargetMap(BaseModel):
    """Stakeholder mapping for a company."""
    company: str
    personas: List[Dict[str, Any]]  # Each has: role, title, hypotheses, etc.
    created_at: datetime


class OutreachVariant(BaseModel):
    """Single outreach message variant."""
    channel: str  # "email" or "linkedin"
    subject_or_hook: Optional[str] = None
    body: str
    personalization_notes: Optional[str] = None


class OutreachDraft(BaseModel):
    """Multi-channel outreach drafts for a persona."""
    company: str
    persona: str
    variants: List[OutreachVariant]
    sequence_steps: List[str]
    objection_responses: Dict[str, str]
    created_at: datetime


class MeetingPrepPack(BaseModel):
    """Meeting preparation materials."""
    company: str
    meeting_type: str  # "discovery", "demo", "negotiation"
    agenda: List[str]
    questions: List[str]
    stakeholder_map: Dict[str, str]
    listen_for_signals: List[str]
    close_plan: str
    created_at: datetime


class FollowUpSummary(BaseModel):
    """Post-meeting follow-up summary and actions."""
    company: str
    meeting_date: datetime
    summary: str
    next_steps: List[str]
    tasks: List[Dict[str, Any]]
    crm_notes: str
    created_at: datetime
```

### A.2 Kernel Models

```python
from enum import Enum
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime


class TaskType(str, Enum):
    """Types of tasks the kernel can execute."""
    RESEARCH = "research"
    TARGETS = "targets"
    OUTREACH = "outreach"
    PREP = "prep"
    FOLLOWUP = "followup"
    PIPELINE = "pipeline"


class ExecutionMode(str, Enum):
    """How to execute a task."""
    MANUAL = "manual"   # Deterministic template-based
    LLM = "llm"         # AI-assisted with validation


class StepStatus(str, Enum):
    """Status of a plan step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Constraints(BaseModel):
    """Execution constraints for a task."""
    max_tokens: Optional[int] = None
    timeout_s: Optional[int] = None
    require_evidence: bool = True
    allow_assumptions: bool = True


class TaskSpec(BaseModel):
    """Specification for a task to execute."""
    task_type: TaskType
    workspace: str
    inputs: Dict[str, Any]
    constraints: Constraints = Constraints()
    requested_artifacts: List[str] = []
    workspace_context: Optional[Any] = None  # WorkspaceContext


class Step(BaseModel):
    """A single step in an execution plan."""
    step_id: str
    skill_name: str
    input_ref: Dict[str, Any]
    depends_on: List[str] = []
    expected_artifacts: List[str] = []
    status: StepStatus = StepStatus.PENDING


class Plan(BaseModel):
    """Execution plan with ordered steps."""
    plan_id: str
    task_spec: TaskSpec
    steps: List[Step]
    created_at: datetime
```

### A.3 Skill Contract Models

```python
from enum import Enum
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Protocol, runtime_checkable


class ClaimKind(str, Enum):
    """Classification of a claim's evidence basis."""
    FACT = "fact"           # Verified from source
    ASSUMPTION = "assumption"  # Assumed without evidence
    INFERENCE = "inference"    # Inferred from other facts


class ArtifactKind(str, Enum):
    """Type of artifact output."""
    MARKDOWN = "markdown"
    JSON = "json"


class SourceRef(BaseModel):
    """Reference to a source document."""
    source_id: str
    source_type: str
    title: Optional[str] = None
    uri: Optional[str] = None
    excerpt: Optional[str] = None


class Claim(BaseModel):
    """A traceable assertion with evidence."""
    text: str
    kind: ClaimKind
    evidence: List[SourceRef] = []
    confidence: Optional[float] = None


class ArtifactRef(BaseModel):
    """Reference to a generated artifact."""
    name: str  # e.g., "research_brief"
    kind: ArtifactKind
    content: str
    metadata: Dict[str, Any] = {}


class NextAction(BaseModel):
    """Suggested next action after skill execution."""
    action_type: str
    description: str
    priority: int = 0


class SkillMetrics(BaseModel):
    """Execution metrics for a skill."""
    duration_ms: int
    llm_calls: int = 0
    tokens_used: int = 0
    repair_attempts: int = 0


class SkillContext(BaseModel):
    """Context provided to a skill during execution."""
    run_id: str
    workspace: str
    config: Dict[str, Any] = {}
    sources: List[SourceRef] = []
    step_inputs: Dict[str, Any] = {}
    evidence_bundle: Optional[Any] = None  # EvidenceBundle
    memory_enabled: bool = True


class SkillResult(BaseModel):
    """Result of skill execution."""
    output: Any  # Typed Pydantic model
    artifacts: List[ArtifactRef]
    claims: List[Claim]
    warnings: List[str] = []
    next_actions: List[NextAction] = []
    metrics: SkillMetrics
    skill_name: str
    skill_version: str


@runtime_checkable
class Skill(Protocol):
    """Protocol that all skills must implement."""
    name: str
    version: str
    
    def run(self, inputs: Dict[str, Any], context: SkillContext) -> SkillResult:
        """Execute skill with inputs and context."""
        ...
```

### A.4 CRM Models

```python
from enum import Enum
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime


class ActivityType(str, Enum):
    """Types of CRM activities."""
    EMAIL = "email"
    LINKEDIN = "linkedin"
    CALL = "call"
    MEETING = "meeting"
    NOTE = "note"
    TASK = "task"


class ActivityDirection(str, Enum):
    """Direction of an activity."""
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class ExternalRef(BaseModel):
    """Reference to an external CRM system."""
    provider: str  # "hubspot", "salesforce", etc.
    external_id: str
    last_synced_at: Optional[datetime] = None
    sync_hash: Optional[str] = None


class Account(BaseModel):
    """CRM account (company) record."""
    account_id: str
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    employee_count: Optional[int] = None
    tags: List[str] = []
    external_refs: List[ExternalRef] = []
    metadata: Dict[str, Any] = {}


class Contact(BaseModel):
    """CRM contact (person) record."""
    contact_id: str
    account_id: Optional[str] = None
    full_name: str
    role_title: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    persona_type: Optional[str] = None  # "champion", "economic_buyer", "blocker"
    hypothesis: Optional[str] = None
    external_refs: List[ExternalRef] = []
    metadata: Dict[str, Any] = {}


class Activity(BaseModel):
    """CRM activity record with BD traceability."""
    activity_id: str
    account_id: str
    contact_id: Optional[str] = None
    activity_type: ActivityType
    subject: str
    body: str
    direction: ActivityDirection = ActivityDirection.OUTBOUND
    is_planned: bool = True
    scheduled_for: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    sequence_step: Optional[int] = None
    run_id: Optional[str] = None  # BD traceability
    artifact_refs: List[str] = []
    source_ids: List[str] = []
    external_refs: List[ExternalRef] = []
    metadata: Dict[str, Any] = {}


class CRMExportManifest(BaseModel):
    """Manifest for a CRM export package."""
    export_id: str
    crm_export_version: str = "1.0"
    run_id: str
    company: str
    account_count: int
    contact_count: int
    activity_count: int
    run_source_ids: List[str] = []
    exported_at: datetime


class CRMExportPackage(BaseModel):
    """Complete CRM export bundle."""
    manifest: CRMExportManifest
    accounts: List[Account]
    contacts: List[Contact]
    activities: List[Activity]


class ImportResult(BaseModel):
    """Result of CRM import operation."""
    success: bool
    accounts_imported: int = 0
    contacts_imported: int = 0
    activities_imported: int = 0
    errors: List[str] = []
    warnings: List[str] = []


class ExportResult(BaseModel):
    """Result of CRM export operation."""
    success: bool
    output_path: str
    files_written: List[str] = []
    errors: List[str] = []
```

### A.5 Workspace Models

```python
from dataclasses import dataclass
from pathlib import Path
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class WorkspaceContext:
    """Isolated workspace context with derived paths."""
    name: str
    workspace_id: str  # UUID
    root_dir: Path
    
    @property
    def runs_dir(self) -> Path:
        return self.root_dir / "runs"
    
    @property
    def db_path(self) -> Path:
        return self.root_dir / "db" / "workspace.sqlite"
    
    @property
    def prefs_path(self) -> Path:
        return self.root_dir / "prefs.json"
    
    @property
    def exports_dir(self) -> Path:
        return self.root_dir / "exports"
    
    @property
    def sources_cache_dir(self) -> Path:
        return self.root_dir / "sources_cache"


class WorkspacePolicy(BaseModel):
    """Policy settings for a workspace."""
    allow_memory: bool = True
    allow_web_fetch: bool = True
    privacy_mode: bool = False


class WorkspacePaths(BaseModel):
    """Path configuration for a workspace."""
    runs: str = "runs"
    db: str = "db/workspace.sqlite"
    exports: str = "exports"


class WorkspaceManifest(BaseModel):
    """TOML manifest for a workspace."""
    name: str
    workspace_id: str
    created_at: datetime
    paths: WorkspacePaths = WorkspacePaths()
    policy: WorkspacePolicy = WorkspacePolicy()


class WorkspacePreferences(BaseModel):
    """User preferences for a workspace."""
    default_mode: str = "manual"
    default_llm_provider: Optional[str] = None
    default_llm_model: Optional[str] = None
    auto_open_artifacts: bool = True
    custom_settings: Dict[str, Any] = {}
```

### A.6 LLM Models

```python
from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class LLMMessage(BaseModel):
    """A message in an LLM conversation."""
    role: str  # "system", "user", "assistant"
    content: str


class LLMRequest(BaseModel):
    """Request to an LLM adapter."""
    messages: List[LLMMessage]
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    json_schema: Optional[Dict[str, Any]] = None
    stop_sequences: List[str] = []


class LLMResponse(BaseModel):
    """Response from an LLM adapter."""
    content: str
    model: str
    usage: Dict[str, int]  # prompt_tokens, completion_tokens, total_tokens
    finish_reason: str  # "stop", "length", "content_filter"
    raw_response: Optional[Dict[str, Any]] = None


class LLMConfig(BaseModel):
    """Configuration for LLM usage."""
    enabled: bool = False
    default_provider: str = "anthropic"
    default_model: str = "claude-sonnet-4-20250514"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout_s: int = 60
    
    # Role-specific overrides
    critic_provider: Optional[str] = None
    critic_model: Optional[str] = None
    draft_provider: Optional[str] = None
    draft_model: Optional[str] = None
```

---

## Appendix B: Configuration Reference

### B.1 Environment Variables

#### LLM Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AG_LLM_ENABLED` | `0` | Enable LLM mode (`1` = enabled) |
| `AG_LLM_DEFAULT_PROVIDER` | `anthropic` | Default LLM provider |
| `AG_LLM_DEFAULT_MODEL` | `claude-sonnet-4-20250514` | Default model |
| `AG_LLM_TEMPERATURE` | `0.7` | Generation temperature |
| `AG_LLM_MAX_TOKENS` | `4096` | Max output tokens |
| `AG_LLM_TIMEOUT_S` | `60` | Request timeout in seconds |

#### Role-Specific LLM Overrides

| Variable | Description |
|----------|-------------|
| `AG_LLM_CRITIC_PROVIDER` | Provider for critic pass |
| `AG_LLM_CRITIC_MODEL` | Model for critic pass |
| `AG_LLM_DRAFT_PROVIDER` | Provider for draft generation |
| `AG_LLM_DRAFT_MODEL` | Model for draft generation |

#### API Keys

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENAI_API_KEY` | OpenAI API key |

#### Storage Configuration

| Variable | Default | Description | Status |
|----------|---------|-------------|--------|
| `AG_DB_PATH` | `data/ag.sqlite` | Bootstrap default for single-workspace setups | **Legacy/dev only** |
| `AG_RUNS_DIR` | `runs` | Bootstrap default for single-workspace setups | **Legacy/dev only** |

> **Note:** Workspace-aware commands MUST use `ws_ctx.db_path` and `ws_ctx.runs_dir`. These env vars only influence bootstrap tooling and legacy single-workspace dev setups.

#### Workspace Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AG_WORKSPACE` | `default` | Active workspace name |
| `AG_WORKSPACES_ROOT` | `~/.ag_network/workspaces` | Workspaces root directory |

#### CRM Configuration

| Variable | Default | Description | Status |
|----------|---------|-------------|--------|
| `AG_CRM_ADAPTER` | `file` | CRM adapter type | Stable |
| `AG_CRM_PATH` | — | Export/import **directory** for file adapter | **Dev override only** |

> **Note:** `AG_CRM_PATH` is a development override for the file adapter's export/import directory. Stable/multi-user deployments MUST use workspace-scoped storage via `ws_ctx.exports_dir` (from `workspace.toml`).

#### Configuration Precedence & Stability Policy

**Precedence (highest → lowest):**

1. `workspace.toml` paths (`runs`, `db`, `exports`)
2. CLI flags / explicit `ws_ctx` injection
3. Dev-only env overrides (`AG_CRM_PATH`, `AG_DB_PATH`, `AG_RUNS_DIR`) — NOT for stable multi-user
4. Hardcoded defaults (used only when creating a workspace / dev tools)

**Stability contract:**

- Once declared "stable", config/env var meanings become a contract.
- Non-disposable DB implies schema versioning + migrations; no silent path reinterpretations.
- Workspace isolation remains non-negotiable; global fallbacks stay forbidden.

### B.2 Workspace Manifest (workspace.toml)

```toml
[workspace]
name = "work"
workspace_id = "550e8400-e29b-41d4-a716-446655440000"
created_at = "2026-01-28T14:30:00Z"

[paths]
runs = "runs"
db = "db/workspace.sqlite"
exports = "exports"

[policy]
allow_memory = true      # Enable FTS5 memory search
allow_web_fetch = true   # Allow URL fetching
privacy_mode = false     # Disable telemetry/logging
```

### B.3 Preferences (prefs.json)

```json
{
  "default_mode": "manual",
  "default_llm_provider": "anthropic",
  "default_llm_model": "claude-sonnet-4-20250514",
  "auto_open_artifacts": true,
  "custom_settings": {
    "preferred_channels": ["email", "linkedin"],
    "meeting_types": ["discovery", "demo", "negotiation"]
  }
}
```

---

## Appendix C: Design Patterns

### C.1 Registry Pattern

Used for skill and CRM adapter discovery:

```python
# Skill registration
@skill_registry.register
class ResearchBriefSkill:
    name = "research_brief"
    version = "1.0"

# CRM adapter registration
@crm_adapter("file")
class FileCRMAdapter:
    ...
```

### C.2 Factory Pattern

Used for adapter instantiation with configuration:

```python
# LLM factory with role-based routing
adapter = LLMFactory.create(provider="anthropic", role="critic")

# CRM factory from config
adapter = CRMAdapterFactory.from_config(config)
```

### C.3 Approval Gate Pattern

Used for side-effect operations requiring user confirmation:

```python
@requires_approval("CRM write operation")
def import_package(self, package: CRMExportPackage) -> ImportResult:
    ...
```

### C.4 Evidence Traceability Pattern

Every claim and activity links back to sources:

```python
# Claims link to source_ids
claim = Claim(text="...", kind=ClaimKind.FACT, evidence=[source_ref])

# Activities link to run_id and artifact_refs
activity = Activity(
    run_id="20260128_143052__acme__research",
    artifact_refs=["research_brief", "outreach"]
)
```

---

*Document generated for AG Network v0.2.0*

# Changelog

All notable changes to AG Network will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] - 2026-01-27

### Added

#### Workspaces & Isolation (M7)
- **Workspace Registry** — Create, list, switch between isolated workspaces
- **Workspace Doctor** — Diagnose and repair workspace issues
- **Per-workspace storage** — Separate SQLite databases, runs folders, preferences
- **Global `--workspace` flag** — Scope any command to a specific workspace
- **Environment variable support** — `AG_WORKSPACE` for default workspace

#### Preferences System (M7)
- **Configurable preferences** — Language, tone, formality per workspace
- **CLI management** — `ag prefs show`, `ag prefs set`, `ag prefs reset`
- **Template integration** — Preferences flow into artifact generation

#### Work Ops Skill Pack (M7)
- `ag meeting-summary` — Generate meeting summaries from notes
- `ag status-update` — Generate status update reports
- `ag decision-log` — Generate ADR-style decision logs

#### Personal Ops Skill Pack (M7)
- `ag weekly-plan` — Generate weekly plans
- `ag errand-list` — Generate organized errand lists
- `ag travel-outline` — Generate travel itinerary outlines

#### CRM Integration (M6)
- **CRM import** — Import contacts from CSV/JSON
- **CRM export** — Export contacts with approval gate
- **Adapter pattern** — Extensible for different CRM systems

#### Sequence Planning (M6)
- `ag sequence create` — Create multi-touch outreach sequences
- `ag sequence list` — List saved sequences
- `ag sequence show` — Display sequence details

#### Deep Link Discovery (M8)
- **Homepage link extraction** — Discover relevant subpages
- **Deterministic mode** — Category-based link selection
- **Agent mode** — LLM-powered link relevance scoring
- **Configurable limits** — `--deep-links-max` parameter

#### Memory & Retrieval (M4/M5)
- **FTS5 search** — Full-text search over sources and artifacts
- **Memory CLI** — `ag memory search`, `ag memory stats`, `ag memory index`
- **Evidence retrieval** — Skills can cite stored sources
- **Auto-enable** — Memory enabled when URLs provided

### Changed

- **Pipeline command enhanced** — Now supports `--mode llm`, `--use-memory`, `--deep-links`
- **README updated** — Comprehensive command reference and examples
- **Test suite expanded** — 484 tests (up from 33 in v0.1)

### Fixed

- Windows SQLite locking issues in concurrent tests
- CLI workspace scoping for all commands
- Artifact schema validation edge cases
- Deep link URL encoding for special characters

---

## [0.1.0] - 2025-12-15

### Added

#### Core Platform (M0/M1)
- **Package structure** — `agnetwork` installable package
- **CLI foundation** — Typer-based command interface
- **Run system** — Immutable timestamped run folders
- **Artifact system** — Markdown + JSON outputs with version metadata
- **Logging** — JSONL worklog + JSON status tracking
- **SQLite storage** — Sources, companies, artifacts, claims tables
- **CI pipeline** — GitHub Actions for ruff + pytest

#### Agent Kernel (M2)
- **TaskSpec model** — Normalized request format
- **Plan/Step models** — Explicit execution graph
- **Skill interface** — Standardized skill contract
- **KernelExecutor** — Orchestrates multi-step plans
- **Verifier module** — Completeness and evidence checks

#### LLM Integration (M3)
- **Adapter pattern** — Anthropic, OpenAI, Fake providers
- **LLMFactory** — Role-based adapter routing
- **Structured outputs** — Pydantic validation + repair loop
- **Prompt library** — Skill-specific prompt templates
- **Critic pass** — Validate claims and coverage

#### BD Skill Pack
- `ag research` — Account research brief
- `ag targets` — Prospect target map
- `ag outreach` — Outreach message drafts
- `ag prep` — Meeting preparation pack
- `ag followup` — Post-meeting follow-up
- `ag run-pipeline` — Full BD pipeline (all 5 artifacts)

#### Validation & Quality
- `ag validate-run` — Run folder integrity checks
- `ag status` — Show recent run status
- Golden tests — Regression tests for artifact structure
- Schema versioning — `artifact_version`, `skill_version` in metadata

---

## Version History

| Version | Date | Milestone | Key Feature |
|---------|------|-----------|-------------|
| 0.2.0 | 2026-01-27 | M1-M8 | Workspaces, Work/Personal Ops, Deep Links |
| 0.1.0 | 2025-12-15 | M0-M3 | Core platform, Agent Kernel, LLM integration |

---

[0.2.0]: https://github.com/your-org/ag-network/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/your-org/ag-network/releases/tag/v0.1.0

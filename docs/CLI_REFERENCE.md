# AG Network CLI Reference

Complete reference for the `ag` command-line interface.

---

## Table of Contents

1. [Global Options](#global-options)
2. [Pipeline Commands](#pipeline-commands)
3. [Research Commands](#research-commands)
4. [Workspace Management](#workspace-management)
5. [Preferences Management](#preferences-management)
6. [CRM Commands](#crm-commands)
7. [Sequence Commands](#sequence-commands)
8. [Memory Commands](#memory-commands)
9. [Work Ops Skills](#work-ops-skills)
10. [Personal Ops Skills](#personal-ops-skills)

---

## Global Options

All commands support the following global option:

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--workspace` | `-w` | Use a specific workspace | Default workspace |

**Environment Variable:** `AG_WORKSPACE` can also set the workspace.

```powershell
# Use a specific workspace for any command
ag --workspace myproject run-pipeline "Acme Corp"

# Or set via environment variable
$env:AG_WORKSPACE = "myproject"
ag run-pipeline "Acme Corp"
```

---

## Pipeline Commands

### `ag run-pipeline`

Run the full BD pipeline for a company, generating all 5 artifacts.

```powershell
ag run-pipeline <company> [OPTIONS]
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `company` | Yes | Company name to run pipeline for |

**Options:**
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--snapshot` | `-s` | Company snapshot/description | Auto-generated |
| `--pain` | `-p` | Key pain point (repeatable) | None |
| `--trigger` | `-t` | Trigger event (repeatable) | None |
| `--competitor` | `-c` | Competitor (repeatable) | None |
| `--url` | `-u` | URL to fetch as source (repeatable) | None |
| `--persona` | | Target persona | `VP Sales` |
| `--channel` | | Outreach channel: `email` or `linkedin` | `email` |
| `--meeting-type` | | Meeting type: `discovery`, `demo`, `negotiation` | `discovery` |
| `--notes` | `-n` | Meeting notes for follow-up | Default text |
| `--mode` | `-m` | Execution mode: `manual` or `llm` | `manual` |
| `--verify/--no-verify` | | Run verification on results | `--verify` |
| `--use-memory/--no-memory` | | Enable FTS5 memory retrieval | `--no-memory` |
| `--deep-links/--no-deep-links` | | Enable deep link discovery (M8) | `--no-deep-links` |
| `--deep-links-mode` | | Selection mode: `deterministic` or `agent` | `deterministic` |
| `--deep-links-max` | | Maximum deep links to fetch | `4` |

**Execution Modes:**
- `manual`: Deterministic template-based generation (no API keys needed)
- `llm`: LLM-assisted generation (requires `AG_LLM_ENABLED=1` and API keys)

**Examples:**
```powershell
# Basic pipeline run (manual mode)
ag run-pipeline "Acme Corp"

# With company details
ag run-pipeline "Acme Corp" --snapshot "Enterprise SaaS" --pain "slow sales" --pain "manual processes"

# Full LLM mode with URL and deep links
ag run-pipeline "Acme Corp" --url https://www.acme.com --mode llm --deep-links

# LinkedIn channel targeting CTO
ag run-pipeline "Acme Corp" --persona "CTO" --channel linkedin
```

**Generated Artifacts:**
1. `research_brief.md/json` - Account research brief
2. `target_map.md/json` - Prospect target map
3. `outreach.md/json` - Outreach message drafts
4. `meeting_prep.md/json` - Meeting preparation pack
5. `followup.md/json` - Post-meeting follow-up

---

### `ag status`

Show status of recent runs in the active workspace.

```powershell
ag status
```

---

### `ag validate-run`

Validate a run folder for integrity.

```powershell
ag validate-run <run_path> [OPTIONS]
```

**Options:**
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--require-meta` | `-m` | Require meta blocks in artifacts | `false` |
| `--check-evidence` | `-e` | Check claim evidence consistency (M4) | `false` |

**Example:**
```powershell
ag validate-run C:\runs\20260129_101234__acme__pipeline --check-evidence
```

---

## Research Commands

### `ag research`

Generate an account research brief for a company.

```powershell
ag research <company> --snapshot <text> [OPTIONS]
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `company` | Yes | Company name to research |

**Options:**
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--snapshot` | `-s` | Company snapshot (required) | — |
| `--pain` | `-p` | Key pain (repeatable) | None |
| `--trigger` | `-t` | Trigger (repeatable) | None |
| `--competitor` | `-c` | Competitor (repeatable) | None |
| `--sources` | `-f` | JSON file with sources | None |
| `--url` | `-u` | URL to fetch (repeatable) | None |
| `--use-memory/--no-memory` | | Enable memory retrieval | `false` |
| `--deep-links/--no-deep-links` | | Enable deep link discovery | `false` |
| `--deep-links-mode` | | `deterministic` or `agent` | `deterministic` |
| `--deep-links-max` | | Max deep links to fetch | `4` |

**Example:**
```powershell
ag research "Acme Corp" --snapshot "Enterprise SaaS platform" --url https://www.acme.com
```

---

### `ag targets`

Generate a prospect target map.

```powershell
ag targets <company> [OPTIONS]
```

### `ag outreach`

Generate outreach message drafts.

```powershell
ag outreach <company> [OPTIONS]
```

### `ag prep`

Generate a meeting preparation pack.

```powershell
ag prep <company> [OPTIONS]
```

### `ag followup`

Generate post-meeting follow-up content.

```powershell
ag followup <company> [OPTIONS]
```

---

## Workspace Management

### `ag workspace create`

Create a new workspace with isolated storage.

```powershell
ag workspace create <name> [OPTIONS]
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Workspace name |

**Options:**
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--root` | `-r` | Custom root directory | `~/.agnetwork/workspaces/<name>` |
| `--set-default` | | Set as default workspace | `false` |

**Examples:**
```powershell
# Create with defaults
ag workspace create myproject

# Create with custom path and set as default
ag workspace create work --root ~/work/agdata --set-default
```

---

### `ag workspace list`

List all registered workspaces.

```powershell
ag workspace list
```

---

### `ag workspace show`

Show detailed information about a workspace.

```powershell
ag workspace show [name]
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `name` | No | Workspace name (default: current default) |

---

### `ag workspace set-default`

Set the default workspace.

```powershell
ag workspace set-default <name>
```

---

### `ag workspace doctor`

Run health checks on a workspace.

```powershell
ag workspace doctor [name]
```

**Checks performed:**
- Directory existence (runs, exports, db)
- Database file integrity
- Workspace ID consistency
- Manifest file presence

---

## Preferences Management

### `ag prefs show`

Show current preferences for a workspace.

```powershell
ag prefs show [OPTIONS]
```

**Options:**
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--workspace` | `-w` | Workspace name | Default workspace |

---

### `ag prefs set`

Set a preference value.

```powershell
ag prefs set <key> <value> [OPTIONS]
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `key` | Yes | Preference key (e.g., `tone`, `language`) |
| `value` | Yes | Preference value |

**Examples:**
```powershell
ag prefs set tone casual
ag prefs set language de --workspace myproject
```

---

### `ag prefs reset`

Reset preferences to defaults.

```powershell
ag prefs reset --confirm [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--confirm` | Required to confirm reset | `false` |
| `--workspace` | Workspace name | Default workspace |

---

## CRM Commands

### `ag crm export-run`

Export a pipeline run as a CRM package.

```powershell
ag crm export-run <run_id> [OPTIONS]
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `run_id` | Yes | Run ID to export |

**Options:**
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--format` | `-f` | Output format: `json` or `csv` | `json` |
| `--out` | `-o` | Output directory path | Workspace exports dir |

**Examples:**
```powershell
ag crm export-run 20260129_101234__acme__pipeline
ag crm export-run 20260129_101234__acme__pipeline --format csv --out ./exports
```

---

### `ag crm export-latest`

Export the most recent pipeline run.

```powershell
ag crm export-latest [OPTIONS]
```

**Options:**
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--format` | `-f` | Output format | `json` |
| `--out` | `-o` | Output directory | Workspace exports dir |
| `--pipeline-only/--all` | | Only export pipeline runs | `--pipeline-only` |

---

### `ag crm import`

Import CRM data from files.

```powershell
ag crm import <file> [OPTIONS]
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `file` | Yes | Path to import file or directory |

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run/--no-dry-run` | Validate without persisting | `--dry-run` |

**Examples:**
```powershell
# Validate only (dry run)
ag crm import ./exports/accounts.json

# Actually import
ag crm import ./exports/ --no-dry-run
```

---

### `ag crm list`

List CRM entities (accounts, contacts, activities).

```powershell
ag crm list <entity_type> [OPTIONS]
```

### `ag crm search`

Search CRM entities.

```powershell
ag crm search <query> [OPTIONS]
```

### `ag crm stats`

Show CRM storage statistics.

```powershell
ag crm stats
```

---

## Sequence Commands

### `ag sequence plan`

Generate an outreach sequence plan from a pipeline run.

```powershell
ag sequence plan <run_id> [OPTIONS]
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `run_id` | Yes | Run ID to build sequence from |

**Options:**
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--channel` | `-c` | Channel: `email` or `linkedin` | `email` |
| `--start` | `-s` | Start date (YYYY-MM-DD) | Today |
| `--out` | `-o` | Output directory | None |

**Example:**
```powershell
ag sequence plan 20260129_101234__acme__pipeline --channel linkedin --start 2026-02-01
```

---

### `ag sequence list-templates`

List available sequence templates.

```powershell
ag sequence list-templates
```

---

### `ag sequence show-template`

Show details of a specific template.

```powershell
ag sequence show-template <name>
```

---

## Memory Commands

### `ag memory rebuild-index`

Rebuild FTS5 search indexes.

```powershell
ag memory rebuild-index
```

Use this if FTS indexes get out of sync with sources/artifacts tables.

---

### `ag memory search`

Search stored sources and artifacts using FTS5.

```powershell
ag memory search <query> [OPTIONS]
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `query` | Yes | Search query |

**Options:**
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--sources` | `-s` | Search sources only | `false` |
| `--artifacts` | `-a` | Search artifacts only | `false` |
| `--limit` | `-l` | Maximum results | `10` |

**Examples:**
```powershell
ag memory search "machine learning"
ag memory search "VP Sales" --artifacts
ag memory search "cloud solutions" --sources --limit 5
```

---

## Work Ops Skills

### `ag meeting-summary`

Generate a meeting summary from notes.

```powershell
ag meeting-summary --topic <topic> --notes <notes> [OPTIONS]
```

**Required Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--topic` | `-t` | Meeting topic |
| `--notes` | `-n` | Meeting notes (text or file path) |

**Optional:**
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--date` | `-d` | Meeting date (YYYY-MM-DD) | Today |
| `--attendees` | `-a` | Comma-separated attendees | `N/A` |

**Examples:**
```powershell
ag meeting-summary --topic "Q1 Planning" --notes "- Discussed budget..."
ag meeting-summary --topic "Standup" --notes notes.txt --attendees "Alice, Bob"
```

---

### `ag status-update`

Generate a status update report.

```powershell
ag status-update [OPTIONS]
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--accomplishment` | `-a` | Accomplishment (repeatable) |
| `--in-progress` | `-i` | In-progress item (repeatable) |
| `--blocker` | `-b` | Blocker (repeatable) |
| `--next` | `-n` | Next week priority (repeatable) |
| `--period` | `-p` | Report period |
| `--author` | | Report author |

**Example:**
```powershell
ag status-update -a "Completed M7" -a "Fixed bugs" -i "Testing" -n "Release prep"
```

---

### `ag decision-log`

Generate an ADR-style decision log.

```powershell
ag decision-log --title <title> --context <context> --decision <decision> [OPTIONS]
```

**Required Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--title` | `-t` | Decision title |
| `--context` | `-c` | Context/background |
| `--decision` | `-d` | The decision made |

**Optional:**
| Option | Short | Description |
|--------|-------|-------------|
| `--option` | `-o` | Option considered (format: `name: description`) |
| `--consequence` | | Consequence of the decision |
| `--decision-makers` | | Who made the decision |
| `--status` | `-s` | Status: `Proposed`, `Accepted`, `Deprecated` |

---

## Personal Ops Skills

### `ag weekly-plan`

Generate a weekly plan.

```powershell
ag weekly-plan [OPTIONS]
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--goal` | `-g` | Weekly goal (repeatable) |
| `--monday` | | Monday task (repeatable) |
| `--tuesday` | | Tuesday task (repeatable) |
| `--wednesday` | | Wednesday task (repeatable) |
| `--thursday` | | Thursday task (repeatable) |
| `--friday` | | Friday task (repeatable) |
| `--note` | `-n` | Note/reminder (repeatable) |
| `--week-of` | `-w` | Week start date |

**Example:**
```powershell
ag weekly-plan --goal "Exercise 3x" --monday "Team standup" --wednesday "Review meeting"
```

---

### `ag errand-list`

Generate an organized errand list.

```powershell
ag errand-list [OPTIONS]
```

**Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--errand` | `-e` | Errand (repeatable) |
| `--location` | `-l` | Location for errands (format: `location: task`) |
| `--date` | `-d` | Date for errands |

**Example:**
```powershell
ag errand-list --location "Grocery: Milk, Bread" --location "Post Office: Mail package"
```

---

### `ag travel-outline`

Generate a travel itinerary outline.

```powershell
ag travel-outline --destination <dest> --start <date> --end <date> [OPTIONS]
```

**Required Options:**
| Option | Short | Description |
|--------|-------|-------------|
| `--destination` | `-d` | Travel destination |
| `--start` | `-s` | Start date (YYYY-MM-DD) |
| `--end` | `-e` | End date (YYYY-MM-DD) |

**Optional:**
| Option | Short | Description |
|--------|-------|-------------|
| `--accommodation` | `-a` | Accommodation details |
| `--activity` | | Activity (repeatable) |
| `--packing` | `-p` | Packing list item (repeatable) |
| `--note` | `-n` | Important note (repeatable) |

**Example:**
```powershell
ag travel-outline -d "Paris" -s 2026-02-10 -e 2026-02-17 --activity "Visit Louvre"
```

---

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AG_WORKSPACE` | Default workspace name | `myproject` |
| `AG_LLM_ENABLED` | Enable LLM mode | `1` |
| `AG_LLM_PROVIDER` | LLM provider | `openai` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-...` |

---

## Output Labels

The CLI uses truthful labels to indicate execution mode:

| Label | Meaning |
|-------|---------|
| `[LLM]` | Generated using LLM |
| `[computed]` | Deterministic template-based (manual mode) |
| `[fetched]` | Fetched from URL |
| `[cached]` | Retrieved from cache |
| `[placeholder]` | Stub/placeholder content |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Error (validation, missing data, API failure, etc.) |

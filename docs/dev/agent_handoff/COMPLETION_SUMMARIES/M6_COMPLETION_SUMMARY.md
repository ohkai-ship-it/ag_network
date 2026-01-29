# M6 Completion Summary: BD Workflow Automation + CRM-Ready Integration

## Milestone Overview

**Goal:** Build a CRM-neutral core layer that can export BD pipeline data to **any** CRM system via adapters—without vendor lock-in.

**Non-negotiables implemented:**
- ✅ No third-party CRM SDK dependencies (Salesforce, HubSpot, etc.)
- ✅ Export-only in M6 (no API writes)
- ✅ Existing CLI structure preserved and extended
- ✅ All artifacts remain auditable through `run_id` traceability

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BD Pipeline (M1-M5)                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ research_   │  │ target_     │  │ outreach    │  │ meeting_    │  ...   │
│  │ brief.json  │  │ map.json    │  │ .json       │  │ prep.json   │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │               │
│         └────────────────┴────────────────┴────────────────┘               │
│                                   │                                         │
│                                   ▼                                         │
│                        ┌─────────────────────┐                              │
│                        │   PipelineMapper    │ (mapping.py)                 │
│                        │  - map_run()        │                              │
│                        │  - source_ids       │                              │
│                        │  - artifact_refs    │                              │
│                        └──────────┬──────────┘                              │
│                                   │                                         │
│                                   ▼                                         │
│                     ┌──────────────────────────────┐                        │
│                     │    Canonical CRM Models      │ (models.py)            │
│                     │ ┌────────┐ ┌────────┐ ┌─────┐│                        │
│                     │ │Account │ │Contact │ │Acti-││                        │
│                     │ │        │ │        │ │vity ││                        │
│                     │ └────────┘ └────────┘ └─────┘│                        │
│                     │ + ExternalRef, Opportunity   │                        │
│                     └──────────────┬───────────────┘                        │
│                                    │                                        │
│                                    ▼                                        │
│                     ┌──────────────────────────────┐                        │
│                     │     CRMExportPackage         │                        │
│                     │ - manifest (with run_id)     │                        │
│                     │ - accounts[]                 │                        │
│                     │ - contacts[]                 │                        │
│                     │ - activities[]               │                        │
│                     └──────────────┬───────────────┘                        │
│                                    │                                        │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
                                     ▼
             ┌──────────────────────────────────────────────┐
             │              Adapter Interface               │
             │           (adapters/base.py)                 │
             │  Protocol: CRMAdapter                        │
             │  - list_accounts/contacts/activities         │
             │  - search_*                                  │
             │  - import_data / export_data                 │
             │  + @requires_approval decorator              │
             └──────────────────────┬───────────────────────┘
                                    │
              ┌─────────────────────┼────────────────────────┐
              │                     │                        │
              ▼                     ▼                        ▼
    ┌──────────────────┐  ┌──────────────────┐    ┌──────────────────┐
    │ FileCRMAdapter   │  │ SalesforceCRM    │    │ HubSpotCRM       │
    │ (Reference Impl) │  │ Adapter (Future) │    │ Adapter (Future) │
    │ - JSON/CSV       │  │                  │    │                  │
    │ - No API deps    │  │                  │    │                  │
    └──────────────────┘  └──────────────────┘    └──────────────────┘
```

---

## Components Implemented

### A. Canonical CRM Models (`src/agnetwork/crm/models.py`)

```python
# Core entities (vendor-agnostic)
Account(account_id, name, domain, industry, location, tags, external_refs, ...)
Contact(contact_id, account_id, full_name, role_title, email, linkedin_url, persona_type, ...)
Activity(activity_id, account_id, activity_type, subject, body, run_id, source_ids, artifact_refs, ...)

# Supporting types
ExternalRef(provider, external_id, last_synced_at, sync_hash)  # For future CRM sync
ActivityType(EMAIL, CALL, MEETING, NOTE, TASK, LINKEDIN_MESSAGE, LINKEDIN_CONNECTION)
ActivityDirection(INBOUND, OUTBOUND, INTERNAL)
Opportunity(opportunity_id, account_id, name, stage, ...)  # Interface stub

# Export structures
CRMExportManifest(export_id, crm_export_version, run_id, company, ...)
CRMExportPackage(manifest, accounts, contacts, activities)
```

### B. CRM Storage (`src/agnetwork/crm/storage.py`)

SQLite tables for local CRM data:
- `crm_accounts` - Company records
- `crm_contacts` - People records  
- `crm_activities` - Touchpoints/interactions

Methods:
```python
storage = CRMStorage()
storage.insert_account(account) / get_account(id) / list_accounts()
storage.insert_contact(contact) / get_contact(id) / search_contacts(query)
storage.insert_activity(activity) / list_activities(account_id=, run_id=)
storage.bulk_insert_accounts/contacts/activities([...])
storage.get_stats()  # Returns {"accounts": N, "contacts": M, "activities": K}
```

### C. Adapter Interface (`src/agnetwork/crm/adapters/`)

**Protocol** (`base.py`):
```python
class CRMAdapter(Protocol):
    name: str
    supports_push: bool
    
    def list_accounts(limit: int) -> List[Account]
    def search_accounts(query: str, limit: int) -> List[Account]
    def import_data(file_path: str, dry_run: bool) -> ImportResult
    def export_data(package: CRMExportPackage, output_path: str, format: str) -> ExportResult
```

**Approval Gate** (for future writes):
```python
@requires_approval(SideEffectCategory.CRM_WRITE)
def push_to_crm(self, package: CRMExportPackage, token: ApprovalToken):
    # Only executes if valid approval token provided
    ...
```

**FileCRMAdapter** (`file_adapter.py`):
- Reference implementation (no vendor dependencies)
- Export to JSON or CSV
- Import from JSON/CSV files or directories
- Round-trip tested

### D. Mapping Layer (`src/agnetwork/crm/mapping.py`)

```python
mapper = PipelineMapper(runs_dir=Path("runs/"))
package = mapper.map_run("20260126_101856__testcompany__pipeline")

# Returns CRMExportPackage with:
# - Account created from company name/domain
# - Contacts extracted from target_map.json personas
# - Activities for each artifact (outreach, meeting_prep, followup, research_brief)
# - Traceability: run_id, artifact_refs, source_ids (deduped, sorted)
```

**Source ID Collection:**
- All `source_ids` from all artifacts are collected, deduplicated, and sorted
- This enables mapping back to original evidence in claims/sources tables

### E. CLI Commands

**CRM Export/Import** (`ag crm ...`):
```bash
# Export a specific run to CRM package
ag crm export-run 20260126_101856__testcompany__pipeline --format json

# Export the latest run
ag crm export-latest --company testcompany --format csv

# Import CRM data (dry-run by default)
ag crm import ./crm_exports/package_dir/
ag crm import ./crm_exports/accounts.csv --persist

# List/search CRM data
ag crm list accounts
ag crm list contacts --account-id acc_123
ag crm search accounts "tech"
ag crm search contacts "CEO"

# Stats
ag crm stats
```

**Sequence Planning** (`ag sequence ...`):
```bash
# Create a sequence plan for a contact
ag sequence plan --contact-id con_123 --template default
ag sequence plan --contact-id con_123 --template linkedin --start-date 2026-01-30

# List available templates
ag sequence templates
```

### F. Approval Gate Infrastructure (`src/agnetwork/crm/approval.py`)

```python
# Create approval token (for future CRM writes)
token = create_approval_token(
    side_effect=SideEffectCategory.CRM_WRITE,
    granted_by="user@example.com",
    ttl_seconds=3600
)

# Validate token
is_valid = validate_approval_token(token, SideEffectCategory.CRM_WRITE)

# Methods decorated with @requires_approval will raise ApprovalRequiredError
# if no valid token is provided
```

### G. Sequence Builder (`src/agnetwork/crm/sequence.py`)

```python
builder = SequenceBuilder()

# Build a sequence plan
plan = builder.build_plan(
    contact=contact,
    template_name="default",  # or "linkedin"
    start_date=datetime(2026, 1, 26),
    context={"company_name": "Acme Corp"},
)

# Plan contains ordered steps with scheduled dates
for step in plan.steps:
    print(f"Day {step.day_offset}: {step.channel} - {step.subject_template}")

# Convert to planned activities
activities = plan.to_activities(account_id="acc_123")
```

**Templates:**
- `default`: Day 0, 3, 7, 14 email sequence
- `linkedin`: Day 0 connection, Day 2 email, Day 7 message

---

## Files Created

```
src/agnetwork/crm/
├── __init__.py              # Module exports
├── models.py                # Account, Contact, Activity, ExternalRef, etc.
├── storage.py               # CRMStorage (SQLite tables)
├── mapping.py               # PipelineMapper (BD→CRM conversion)
├── approval.py              # Approval token utilities
├── sequence.py              # SequenceBuilder, SequencePlan
└── adapters/
    ├── __init__.py          # Adapter exports
    ├── base.py              # CRMAdapter Protocol, @requires_approval
    └── file_adapter.py      # FileCRMAdapter (JSON/CSV reference impl)

tests/
├── test_crm_models.py       # Model creation, serialization
├── test_crm_storage.py      # CRUD, bulk ops, stats
├── test_crm_adapters.py     # Export, import, round-trip, approval gate
├── test_crm_mapping.py      # Pipeline mapping, source_ids collection
└── test_crm_sequence.py     # Sequence building, templates, determinism
```

---

## How to Add a Vendor Adapter (Future)

1. Create `src/agnetwork/crm/adapters/salesforce_adapter.py`:

```python
from agnetwork.crm.adapters.base import BaseCRMAdapter, requires_approval, SideEffectCategory

class SalesforceAdapter(BaseCRMAdapter):
    name = "salesforce"
    supports_push = True  # This adapter can write to CRM
    
    def __init__(self, api_key: str, instance_url: str):
        self.client = SalesforceClient(api_key, instance_url)
    
    def list_accounts(self, limit: int = 100) -> List[Account]:
        # Query Salesforce API, convert to canonical Account model
        ...
    
    @requires_approval(SideEffectCategory.CRM_WRITE)
    def push_accounts(self, accounts: List[Account], approval: ApprovalToken):
        # Push to Salesforce with approval gate
        ...
```

2. Register in `adapters/__init__.py`:
```python
from .salesforce_adapter import SalesforceAdapter
AdapterRegistry.register("salesforce", SalesforceAdapter)
```

3. Use via CLI:
```bash
ag crm push --adapter salesforce --run-id 20260126_...
# Will prompt for approval or require --approve flag
```

---

## Export Package Structure

When you run `ag crm export-run <run_id>`:

```
crm_exports/<export_id>/
├── manifest.json           # Metadata (run_id, company, counts, timestamp)
├── accounts.json           # Account records
├── contacts.json           # Contact records
└── activities.json         # Activity records with source_ids, artifact_refs
```

Each activity links back to the run system:
```json
{
  "activity_id": "act_123",
  "account_id": "acc_456",
  "activity_type": "EMAIL",
  "subject": "Meeting follow-up",
  "run_id": "20260126_101856__testcompany__pipeline",
  "artifact_refs": ["outreach.json", "followup.json"],
  "source_ids": ["src_001", "src_002", "src_003"]
}
```

---

## Test Results

All 75 CRM tests pass:
- `test_crm_models.py`: 17 tests (model creation, serialization)
- `test_crm_storage.py`: 14 tests (CRUD, bulk ops, stats)
- `test_crm_adapters.py`: 17 tests (export, import, round-trip, approval)
- `test_crm_mapping.py`: 10 tests (pipeline mapping, source_ids)
- `test_crm_sequence.py`: 17 tests (sequences, templates, determinism)

---

## Acceptance Criteria Status

| Criterion | Status |
|-----------|--------|
| No vendor SDK dependencies | ✅ |
| Canonical models (Account, Contact, Activity) | ✅ |
| File adapter as reference implementation | ✅ |
| Export produces JSON/CSV packages | ✅ |
| Import validates and loads from packages | ✅ |
| Round-trip (export→import) preserves data | ✅ |
| Approval gate infrastructure for future writes | ✅ |
| CLI commands for export/import/list/search/stats | ✅ |
| Sequence builder with templates | ✅ |
| Source IDs collected and stable-ordered | ✅ |
| Run traceability (run_id, artifact_refs) | ✅ |
| Tests cover all new functionality | ✅ |

---

## Next Steps (M7+)

1. **Salesforce Adapter** - Implement `SalesforceAdapter` using simple-salesforce
2. **HubSpot Adapter** - Implement `HubSpotAdapter` using hubspot-api-client
3. **Approval Flow** - Add interactive approval prompt for CRM writes
4. **Sync Status Tracking** - Track which records have been synced via `ExternalRef`
5. **Incremental Sync** - Only push changed records based on `sync_hash`

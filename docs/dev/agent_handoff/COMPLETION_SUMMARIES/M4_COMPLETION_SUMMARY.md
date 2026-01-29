# M4 Completion Summary: Memory Retrieval (FTS5) + Evidence via Claims

## ✅ Implementation Status: COMPLETE

All M4 tasks have been implemented and tested:

| Task | Description | Status |
|------|-------------|--------|
| A | Normalize `claims.source_ids` to canonical JSON array | ✅ Complete |
| B | Add SQLite FTS5 tables with sync triggers | ✅ Complete |
| C | Create Memory API (search + retrieve_context) | ✅ Complete |
| D | Evidence propagation via claims table | ✅ Complete |
| E | Kernel integration with `--use-memory` toggle | ✅ Complete |
| F | Verifier + validate-run evidence checks | ✅ Complete |

## Architecture Overview

### Database Schema Additions

```sql
-- FTS5 virtual table for sources (full-text search)
CREATE VIRTUAL TABLE sources_fts USING fts5(
    source_id,
    title,
    uri,
    content
);

-- FTS5 virtual table for artifacts (full-text search)
CREATE VIRTUAL TABLE artifacts_fts USING fts5(
    artifact_id,
    name,
    artifact_type,
    content
);

-- Automatic sync triggers maintain FTS indexes
-- sources_ai, sources_ad, sources_au (INSERT, DELETE, UPDATE)
-- artifacts_ai, artifacts_ad, artifacts_au (INSERT, DELETE, UPDATE)
```

### Claims Source IDs Format

**New canonical format (JSON array):**
```json
["src_1", "src_2", "src_3"]
```

**Backward-compatible reading supports:**
- Legacy CSV: `src_1,src_2,src_3`
- Legacy JSON: `["src_1", "src_2"]`
- New JSON: `["src_1", "src_2", "src_3"]`

### Memory API (`storage/memory.py`)

```python
from agnetwork.storage.memory import MemoryAPI, get_memory_api

# Initialize
api = MemoryAPI(db_path)  # or get_memory_api(db_path)

# Search sources
hits = api.search_sources("company name", limit=10)
# Returns: List[SourceHit] with id, source_type, title, excerpt, score

# Search artifacts
hits = api.search_artifacts("research brief", limit=10)
# Returns: List[ArtifactHit] with id, artifact_type, name, excerpt, score

# Retrieve context for a skill task
bundle = api.retrieve_context(task_spec)
# Returns: EvidenceBundle with sources, artifacts, query, retrieved_at
```

### Evidence Flow

```
Skill Execution → Claims with evidence (SourceRef) → claims.source_ids (JSON) → DB
                                                                               ↓
Memory API ← FTS5 search ← Triggers sync ← sources/artifacts tables ← Run storage
```

**Important:** Evidence is stored in `claims.source_ids`, NOT in artifact JSON fields.

## CLI Usage

### Pipeline with Memory

```bash
# Enable memory retrieval during pipeline execution
ag run-pipeline --company "ACME Corp" --use-memory

# Memory provides evidence context to skills
```

### Validate with Evidence Check

```bash
# Validate run folder with evidence consistency check
ag validate-run runs/20260126_101856__testcompany__pipeline --check-evidence

# Warnings if facts lack source references
```

## Files Modified/Created

### New Files
- [src/agnetwork/storage/memory.py](src/agnetwork/storage/memory.py) - MemoryAPI implementation
- [tests/test_memory.py](tests/test_memory.py) - 35 comprehensive tests

### Modified Files
- [src/agnetwork/storage/sqlite.py](src/agnetwork/storage/sqlite.py)
  - Added `normalize_source_ids()`, `serialize_source_ids()` functions
  - Added FTS5 tables initialization (`_init_fts5`)
  - Added FTS5 sync triggers
  - Added `search_sources_fts()`, `search_artifacts_fts()` methods
  - Added `rebuild_fts_index()` method
  - Updated `insert_claim()` to serialize source_ids as JSON
  - Updated `get_claim()` to normalize source_ids

- [src/agnetwork/storage/__init__.py](src/agnetwork/storage/__init__.py)
  - Exported memory API components

- [src/agnetwork/kernel/contracts.py](src/agnetwork/kernel/contracts.py)
  - Added `Claim.source_ids` property
  - Added `Claim.is_sourced()` method
  - Added `SkillContext.evidence_bundle` field
  - Added `SkillContext.memory_enabled` field

- [src/agnetwork/kernel/executor.py](src/agnetwork/kernel/executor.py)
  - Added `use_memory` parameter to `KernelExecutor`
  - Added `_get_memory_api()` helper
  - Added `_persist_claims()` method
  - Updated `_execute_step()` to pass evidence bundle
  - Added `ExecutionResult.claims_persisted` counter

- [src/agnetwork/eval/verifier.py](src/agnetwork/eval/verifier.py)
  - Added `_check_evidence_consistency()` method
  - Added `memory_enabled` parameter to `verify_skill_result()`

- [src/agnetwork/validate.py](src/agnetwork/validate.py)
  - Added `_validate_claim_evidence()` function
  - Added `check_evidence` parameter to `validate_run_folder()`

- [src/agnetwork/cli.py](src/agnetwork/cli.py)
  - Added `--use-memory` flag to `run-pipeline` command
  - Added `--check-evidence` flag to `validate-run` command

## Test Results

```
151 passed, 2 skipped (118 warnings about deprecated datetime.utcnow)

Test coverage for M4:
- TestSourceIdsNormalization: 10 tests ✅
- TestClaimsSourceIdsPersistence: 4 tests ✅
- TestFTS5Search: 7 tests ✅
- TestMemoryAPI: 5 tests ✅
- TestClaimPersistenceIntegration: 2 tests ✅
- TestVerifierEvidenceConsistency: 4 tests ✅
- TestFTSTriggers: 3 tests ✅
```

## Non-Negotiable Rules Compliance

✅ **No artifact JSON changes** - Evidence stored in claims.source_ids only  
✅ **No web fetching** - FTS5 local search only  
✅ **No embeddings** - Pure FTS5 full-text search  
✅ **Backward compatible** - Reads legacy CSV and JSON formats  
✅ **FTS5 only** - No external dependencies for search  

## Migration Notes

1. **Existing databases**: FTS5 tables created automatically on first access
2. **Legacy claims**: Old CSV/JSON source_ids read correctly
3. **New claims**: Written as JSON arrays
4. **Index rebuild**: Use `SQLiteManager.rebuild_fts_index()` if needed

## Next Steps (Future Milestones)

- M5: Enhanced evidence linking with confidence scoring
- M6: Cross-run memory retrieval for company history
- M7: Evidence graph visualization

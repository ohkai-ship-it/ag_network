# Pre-M4 Additional Information

> Generated: 2026-01-26

---

## 1. Current SQLite Schema

From `src/agnetwork/storage/sqlite.py`:

```sql
-- SOURCES TABLE
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,      -- "url", "pasted_text", "file"
    title TEXT,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata TEXT                    -- JSON string
)

-- COMPANIES TABLE  
CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    metadata TEXT
)

-- ARTIFACTS TABLE
CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    run_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(company_id) REFERENCES companies(id)
)

-- CLAIMS TABLE (traceability)
CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL,
    claim_text TEXT NOT NULL,
    is_assumption INTEGER DEFAULT 0,
    source_ids TEXT,                 -- comma-separated or JSON array
    confidence REAL,                 -- 0.0 to 1.0
    FOREIGN KEY(artifact_id) REFERENCES artifacts(id)
)
```

### Key observations for M4/RAG:
- `sources.content` stores full text (no chunking/embedding yet)
- `claims.source_ids` loosely links claims → sources but no vector similarity
- No embedding columns, no FTS tables currently

---

## 2. Sample Pipeline Run

Fresh run created at: `runs/20260126_121036__samplecorp_m4__pipeline/`

### Structure:
```
20260126_121036__samplecorp_m4__pipeline/
├── inputs.json
├── artifacts/
│   ├── research_brief.json/.md
│   ├── target_map.json/.md
│   ├── outreach.json/.md
│   ├── meeting_prep.json/.md
│   └── followup.json/.md
├── logs/
│   ├── agent_status.json
│   └── agent_worklog.jsonl
└── sources/
```

### Evidence fields present in artifacts:

| Artifact | Evidence-related fields |
|----------|------------------------|
| `research_brief.json` | `personalization_angles[].is_assumption: true` |
| `target_map.json` | `personas[].is_assumption: true` |
| `outreach.json` | (none - no source linkage) |
| `meeting_prep.json` | (none) |
| `followup.json` | (none) |

### What's **missing** for RAG:
- No `source_ids: []` arrays on claims/facts
- No `confidence` scores  
- No `evidence_snippets` with text excerpts
- The `is_assumption` flag exists but `source_ids` is absent when `is_assumption=false`
- The `sources/` folder is empty (no ingested sources in this manual run)

---

## 3. M4 Minimal Refactor Hints

1. **Add FTS5 table** for sources:
   ```sql
   CREATE VIRTUAL TABLE sources_fts USING fts5(content, title, source_type);
   ```

2. **Extend artifact schema** to include `source_ids` on each claim/angle:
   ```python
   personalization_angles: List[Dict] = [
       {"angle": "...", "fact": "...", "is_assumption": False, "source_ids": ["src_123"]}
   ]
   ```

3. **Later (RAG)**: Add `embeddings` table with vector column for semantic search

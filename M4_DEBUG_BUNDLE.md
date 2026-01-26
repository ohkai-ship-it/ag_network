# M4 Debug Bundle

## Commands Run

```bash
# Test execution
pytest tests/test_memory.py -v --tb=short

# Full test suite
pytest --tb=line

# Linting
ruff check . --fix
```

## Test Results (Final)

```
================ 151 passed, 2 skipped, 118 warnings in 3.60s =================
```

No failures or errors.

## Database Configuration

- **DB Path**: `data/ag.sqlite` (configurable via `AG_DB_PATH` env var)
- **Type**: Fresh DB created per test (using `tmp_path` fixture)
- **Existing DB**: Schema auto-migrates (adds columns if missing)

## Migrations

No formal migration system - schema changes handled in `SQLiteManager.__init__()`:

```python
# Add columns if missing (backward compatible)
for col, default in [("kind", "'fact'"), ("confidence", "NULL"), ("source_ids", "NULL")]:
    try:
        cursor.execute(f"ALTER TABLE claims ADD COLUMN {col} TEXT DEFAULT {default}")
    except sqlite3.OperationalError:
        pass  # Column already exists
```

## FTS5 Implementation Details

### FTS5 Table Creation SQL

```sql
-- Sources FTS5 (stores content directly, not external content)
CREATE VIRTUAL TABLE IF NOT EXISTS sources_fts USING fts5(
    source_id,
    title,
    uri,
    content
);

-- Artifacts FTS5
CREATE VIRTUAL TABLE IF NOT EXISTS artifacts_fts USING fts5(
    artifact_id,
    name,
    artifact_type,
    content
);
```

### FTS5 Sync Triggers

```sql
-- Sources INSERT trigger
CREATE TRIGGER IF NOT EXISTS sources_ai AFTER INSERT ON sources BEGIN
    INSERT INTO sources_fts(source_id, title, uri, content)
    VALUES (NEW.id, NEW.title, NEW.uri, NEW.content);
END;

-- Sources DELETE trigger
CREATE TRIGGER IF NOT EXISTS sources_ad AFTER DELETE ON sources BEGIN
    DELETE FROM sources_fts WHERE source_id = OLD.id;
END;

-- Sources UPDATE trigger
CREATE TRIGGER IF NOT EXISTS sources_au AFTER UPDATE ON sources BEGIN
    DELETE FROM sources_fts WHERE source_id = OLD.id;
    INSERT INTO sources_fts(source_id, title, uri, content)
    VALUES (NEW.id, NEW.title, NEW.uri, NEW.content);
END;

-- Artifacts INSERT trigger
CREATE TRIGGER IF NOT EXISTS artifacts_ai AFTER INSERT ON artifacts BEGIN
    INSERT INTO artifacts_fts(artifact_id, name, artifact_type, content)
    VALUES (NEW.id, NEW.name, NEW.artifact_type,
            COALESCE(NEW.content_md, '') || ' ' || COALESCE(NEW.content_json, ''));
END;

-- Artifacts DELETE trigger
CREATE TRIGGER IF NOT EXISTS artifacts_ad AFTER DELETE ON artifacts BEGIN
    DELETE FROM artifacts_fts WHERE artifact_id = OLD.id;
END;

-- Artifacts UPDATE trigger
CREATE TRIGGER IF NOT EXISTS artifacts_au AFTER UPDATE ON artifacts BEGIN
    DELETE FROM artifacts_fts WHERE artifact_id = OLD.id;
    INSERT INTO artifacts_fts(artifact_id, name, artifact_type, content)
    VALUES (NEW.id, NEW.name, NEW.artifact_type,
            COALESCE(NEW.content_md, '') || ' ' || COALESCE(NEW.content_json, ''));
END;
```

### FTS5 Search Queries

```sql
-- Search sources
SELECT
    s.id,
    s.source_type,
    s.title,
    s.uri,
    s.created_at,
    s.metadata,
    snippet(sources_fts, 3, '<mark>', '</mark>', '...', 32) as excerpt,
    bm25(sources_fts) as score
FROM sources_fts
JOIN sources s ON sources_fts.source_id = s.id
WHERE sources_fts MATCH ?
ORDER BY score
LIMIT ?;

-- Search artifacts
SELECT
    a.id,
    a.company_id,
    a.artifact_type,
    a.run_id,
    a.name,
    a.created_at,
    snippet(artifacts_fts, 3, '<mark>', '</mark>', '...', 32) as excerpt,
    bm25(artifacts_fts) as score
FROM artifacts_fts
JOIN artifacts a ON artifacts_fts.artifact_id = a.id
WHERE artifacts_fts MATCH ?
ORDER BY score
LIMIT ?;
```

### Rebuild Index SQL

```sql
-- Rebuild sources_fts
DELETE FROM sources_fts;
INSERT INTO sources_fts(source_id, title, uri, content)
SELECT id, title, uri, content FROM sources;

-- Rebuild artifacts_fts
DELETE FROM artifacts_fts;
INSERT INTO artifacts_fts(artifact_id, name, artifact_type, content)
SELECT id, name, artifact_type,
       COALESCE(content_md, '') || ' ' || COALESCE(content_json, '')
FROM artifacts;
```

## Issues Encountered & Resolutions

### Issue 1: External Content FTS5 Failure

**Error:**
```
sqlite3.OperationalError: no such column: T.source_id
```

**Cause:** Using `content='sources', content_rowid='rowid'` creates an external content FTS5 table that requires exact column name mapping.

**Resolution:** Switched to regular (non-external-content) FTS5 tables that store content directly. Simpler and more reliable.

### Issue 2: Windows File Locking on Temp Directories

**Error:**
```
PermissionError: [WinError 32] Der Prozess kann nicht auf die Datei zugreifen, da sie von einem anderen Prozess verwendet wird
```

**Cause:** SQLite connections not fully closed before `TemporaryDirectory` cleanup on Windows.

**Resolution:** Changed test fixtures to use pytest's `tmp_path` fixture (handles cleanup better) + added `gc.collect()` helper.

### Issue 3: Duplicate Method Definitions

**Error:**
```
F811 Redefinition of unused `search_sources_fts`
```

**Cause:** Old method definitions not fully removed during editing.

**Resolution:** Removed duplicate method definitions from sqlite.py.

## Claims source_ids Format

### Normalization Function

```python
def normalize_source_ids(source_ids: Optional[Union[str, List[str]]]) -> List[str]:
    """Normalize source_ids from legacy formats to list."""
    if source_ids is None:
        return []
    if isinstance(source_ids, list):
        return source_ids
    if isinstance(source_ids, str):
        s = source_ids.strip()
        if not s:
            return []
        # Try JSON first
        if s.startswith("["):
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                pass
        # Fall back to CSV
        return [x.strip() for x in s.split(",") if x.strip()]
    return []
```

### Serialization Function

```python
def serialize_source_ids(source_ids: Optional[List[str]]) -> str:
    """Serialize source_ids to JSON array string for DB storage."""
    if source_ids is None:
        return "[]"
    return json.dumps(source_ids)
```

## Warnings Status

```
118 warnings about deprecated datetime.utcnow()
```

These are non-critical deprecation warnings. Can be fixed by replacing:
```python
datetime.utcnow()
# with
datetime.now(datetime.UTC)
```

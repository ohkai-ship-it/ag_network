# M5 Completion Summary: Web Fetch + Source Capture + Evidence Discipline

> Generated: 2026-01-26

---

## Overview

M5 adds **web-first source ingestion** capabilities to the ag_network system, enabling the pipeline to fetch and process URLs, extract clean text, cache sources in run folders, and link facts to their original sources.

---

## Implementation Summary

### Task A: Web Fetch Tool (`httpx`)

**File:** `src/agnetwork/tools/web/fetch.py`

- `FetchResult` dataclass with properties: `is_success`, `is_html`, `content_type`
- `fetch_url()` - synchronous URL fetching with:
  - Per-host rate limiting (1s minimum interval)
  - Configurable timeout (default 30s)
  - Max retries with exponential backoff
  - Content size limit (default 10MB)
  - SHA256 content hashing for deduplication
- `fetch_urls()` - batch fetching multiple URLs sequentially

```python
from agnetwork.tools.web.fetch import fetch_url

result = fetch_url("https://example.com/page")
if result.is_success:
    html = result.content_bytes
    hash = result.content_hash
```

---

### Task B: HTML Text Extraction

**File:** `src/agnetwork/tools/web/clean.py`

- `CleanResult` dataclass with extracted text, title, char_count
- `extract_text()` - BeautifulSoup + lxml based extraction:
  - Removes script/style/nav/header/footer tags
  - Finds main content area (article, main, content divs)
  - Normalizes whitespace
  - Extracts page title from `<title>`, `<h1>`, or og:title
- `extract_text_simple()` - convenience wrapper

```python
from agnetwork.tools.web.clean import extract_text

result = extract_text(html_bytes, url="https://example.com")
print(result.text)  # Clean text
print(result.title)  # Page title
```

---

### Task C: Source Capture + Caching

**File:** `src/agnetwork/tools/web/capture.py`

- `CapturedSource` dataclass tracking all source metadata
- `SourceCapture` class handles:
  - URL → filesystem-safe slug conversion
  - Caching captured sources to avoid refetch
  - Storing 3 files per source:
    - `{slug}__raw.html` - original HTML
    - `{slug}__clean.txt` - extracted text
    - `{slug}__meta.json` - metadata (URL, hash, title, etc.)

**File structure:**
```
runs/{run_folder}/
└── sources/
    ├── example_com_page_abc123__raw.html
    ├── example_com_page_abc123__clean.txt
    └── example_com_page_abc123__meta.json
```

---

### Task D: SQLite Upsert with Content Hash

**File:** `src/agnetwork/storage/sqlite.py` (modified)

New columns added to `sources` table:
- `content_hash TEXT` - SHA256 for deduplication
- `run_id TEXT` - links source to run that captured it

New methods:
- `upsert_source_from_capture()` - inserts or updates source with hash deduplication
- `get_source_by_hash()` - lookup by content hash

```sql
-- M5 migration (automatic)
ALTER TABLE sources ADD COLUMN content_hash TEXT;
ALTER TABLE sources ADD COLUMN run_id TEXT;
```

---

### Task E: CLI URL Integration

**File:** `src/agnetwork/cli.py` (modified)

#### Research command:
```bash
ag research "Company Name" --url https://example.com/about --use-memory
```
- `--url` can be repeated for multiple URLs
- `--use-memory` enables memory storage (auto-enabled when URLs provided)

#### Pipeline command:
```bash
ag run-pipeline "Company Name" --url https://company.com --url https://news.com/article
```
- Captures all URLs into `sources/` folder
- Upserts into memory database automatically
- All artifacts can reference source_ids

#### Memory commands:
```bash
ag memory rebuild-index   # Rebuild FTS5 index
ag memory search "query"  # Search sources by text
```

---

### Task F: Evidence Discipline

**Files:**
- `src/agnetwork/prompts/research_brief.py`
- `src/agnetwork/prompts/target_map.py`
- `src/agnetwork/skills/research_brief.py`
- `src/agnetwork/skills/target_map.py`

Updated JSON schema to include `source_ids` arrays:

```json
{
  "personalization_angles": [
    {
      "name": "Growth Initiative",
      "fact": "Company raised $50M Series B",
      "is_assumption": false,
      "source_ids": ["src_example_com_about_abc123"]
    }
  ]
}
```

Evidence rules in prompts:
1. If fact comes from source → `is_assumption: false` + `source_ids: ["id1", "id2"]`
2. If no source supports → `is_assumption: true` + `source_ids: []`
3. Skills extract `source_ids` into `Claim.evidence` field

---

## New Dependencies

Added to `pyproject.toml`:
```toml
dependencies = [
    "httpx>=0.27.0",       # HTTP client
    "beautifulsoup4>=4.12.0",  # HTML parsing
    "lxml>=5.0.0",         # Fast XML/HTML parser
]
```

---

## Test Coverage

**New test file:** `tests/test_web.py` (29 tests)

- `TestExtractText` - HTML extraction tests
- `TestCleanResult` - CleanResult dataclass
- `TestComputeHash` - SHA256 hashing
- `TestFetchResult` - FetchResult properties
- `TestFetchUrl` - Mocked URL fetching
- `TestCapturedSource` - CapturedSource properties
- `TestSourceCapture` - Directory creation, caching
- `TestCaptureSourcesForRun` - End-to-end capture
- `TestSQLiteSourceUpsert` - Database upsert + dedup
- `TestEdgeCases` - Unicode, binary, edge cases

All 180 tests pass.

---

## Bug Fixes

### `datetime.utcnow()` Deprecation

Fixed in Python 3.12+ deprecation warnings:

**Files modified:**
- `src/agnetwork/storage/sqlite.py`
- `src/agnetwork/tools/ingest.py`
- `tests/test_memory.py`

**Change:**
```python
# Before (deprecated)
datetime.utcnow()

# After
datetime.now(timezone.utc)
```

---

## Architecture Diagram

```
                      CLI: ag run-pipeline "Company" --url ...
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │       URL Processing          │
                    │  ┌────────┐  ┌────────────┐   │
                    │  │ fetch  │→ │   clean    │   │
                    │  │ (httpx)│  │(BeautifulSoup) │
                    │  └────────┘  └────────────┘   │
                    │          │                    │
                    │          ▼                    │
                    │  ┌─────────────────────┐      │
                    │  │   SourceCapture     │      │
                    │  │  (cache to disk)    │      │
                    │  └─────────────────────┘      │
                    └───────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
        ┌──────────────────┐           ┌──────────────────┐
        │   Run Folder     │           │   SQLite DB      │
        │ sources/         │           │ sources table    │
        │  *__raw.html     │           │ (content_hash,   │
        │  *__clean.txt    │           │  run_id columns) │
        │  *__meta.json    │           │ + FTS5 index     │
        └──────────────────┘           └──────────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │     Prompt Builders           │
                    │  (source_ids in schema)       │
                    └───────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │        LLM Skills             │
                    │  (evidence → claims)          │
                    └───────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │    Artifacts with source_ids  │
                    │  {"is_assumption": false,     │
                    │   "source_ids": ["src_..."]}  │
                    └───────────────────────────────┘
```

---

## Usage Examples

### Basic URL Research
```bash
# Research with company website
ag research "TechCorp Inc" --url https://techcorp.com/about --use-memory

# Full pipeline with multiple sources
ag run-pipeline "Acme Co" \
  --url https://acme.com \
  --url https://news.example.com/acme-raises-funding
```

### Memory Management
```bash
# Search ingested sources
ag memory search "funding round"

# Rebuild search index
ag memory rebuild-index
```

### Programmatic Usage
```python
from agnetwork.tools.web.capture import SourceCapture
from pathlib import Path

# Create capture for a run
capture = SourceCapture(Path("runs/my_run/sources"))

# Capture URLs
sources = capture.capture_urls([
    "https://example.com/page1",
    "https://example.com/page2",
])

for src in sources:
    if src.is_success:
        print(f"Captured: {src.url}")
        print(f"  Title: {src.title}")
        print(f"  Hash: {src.content_hash}")
```

---

## Next Steps (M6)

1. **RAG Enhancement**: Vector embeddings for semantic search
2. **Evidence Verification**: Fact-check claims against sources
3. **Source Quality Scoring**: Rank sources by reliability
4. **Incremental Updates**: Re-fetch only changed sources

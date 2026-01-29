# BI-0007 — Batch DB inserts for sources and claims

## Metadata
- **ID:** BI-0007
- **Type:** Performance
- **Status:** Proposed
- **Priority:** P2
- **Area:** Storage
- **Owner:** TBD
- **Target sprint:** TBD
- **Source:** BI-0003 code review (PERF-004, PERF-006)

## Problem

Currently, source upserts and claim inserts happen one-by-one in loops:

1. **Source upserts** (`commands_research.py:169-188`):
   ```python
   for url in urls:
       result = capture.capture_url(url)
       db.upsert_source_from_capture(...)  # Individual INSERT
   ```

2. **Claim inserts** (`kernel/executor.py:370-400`):
   ```python
   for claim in result.claims:
       db.insert_claim(...)  # Individual INSERT
   ```

This creates N+1-style overhead for runs with many URLs or claims.

## Goal

Implement batch insert methods for:
- `SQLiteManager.upsert_sources_batch(sources: List[CaptureResult])`
- `SQLiteManager.insert_claims_batch(claims: List[Claim], artifact_id: str)`

Reduce DB round-trips and leverage SQLite's efficient bulk insert.

## Non-goals

- Vector/embedding batch operations (out of scope)
- Async/concurrent fetching (separate concern)

## Acceptance criteria

- [ ] `upsert_sources_batch()` method exists and is used in research command
- [ ] `insert_claims_batch()` method exists and is used in executor
- [ ] Both methods use `executemany()` or multi-row INSERT
- [ ] FTS triggers still fire correctly for batched inserts
- [ ] Unit tests verify batch correctness
- [ ] (Optional) Benchmark shows measurable improvement for N≥10 items

## Implementation notes

SQLite `executemany()` example:
```python
def insert_claims_batch(self, claims: List[Tuple], artifact_id: str):
    with sqlite3.connect(self.db_path) as conn:
        conn.executemany(
            "INSERT INTO claims (id, artifact_id, claim_text, ...) VALUES (?, ?, ?, ...)",
            [(claim.id, artifact_id, claim.text, ...) for claim in claims]
        )
```

## Risks

- FTS triggers may need verification for batch inserts
- Transaction semantics on partial failure

## PR plan

1. PR (M): Add batch methods + update callers + tests

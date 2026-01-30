# Completion Summary: BI-0005 — Performance Baseline + Harness

**Backlog Item:** BI-0005  
**Sprint:** SPRINT-2026-01  
**Status:** ✅ Complete  
**Date:** 2026-01-30  
**Branch:** `chore/perf-baseline-bi0005`

---

## Summary

Created a minimal, offline performance harness for ag_network that:
- Measures CLI startup time, storage operations, and pipeline execution
- Runs entirely offline (no network, no LLM providers)
- Produces repeatable baseline numbers
- Integrates with pytest via `@pytest.mark.perf` marker

## Deliverables

| Artifact | Path | Description |
|----------|------|-------------|
| Performance Baseline Doc | `docs/dev/reviews/PERFORMANCE_BASELINE_SPRINT-2026-01.md` | Design, procedures, baseline numbers |
| Performance Harness | `tests/test_perf_baseline.py` | pytest module with 4 benchmarks |
| pytest marker | `pyproject.toml` | Registered `perf` marker |

## Baseline Numbers (v0.2.1)

| Benchmark | Median | Target | Status |
|-----------|--------|--------|--------|
| CLI Startup (warm) | 37ms | < 1500ms | ✅ |
| Storage Insert (100 records) | 568ms | < 1000ms | ✅ |
| Storage FTS Query (10 queries) | 10ms | < 50ms | ✅ |
| Pipeline Manual (5 artifacts) | 170ms | < 5000ms | ✅ |

### Machine Specs
- **Platform:** Windows 11 (10.0.22631)
- **Python:** 3.14.0
- **CPU:** 22-core

## Benchmarks Implemented

### 1. CLI Startup (Warm)
- Uses Typer's CliRunner for in-process invocation
- Warm-up run excluded from measurement
- 3 iterations, median reported

### 2. Storage Insert Batch
- Creates fresh SQLite DB each iteration (includes schema init)
- Inserts 100 synthetic source records
- Measures total and per-record time

### 3. Storage FTS Search
- Pre-populates 100 records
- Runs 10 diverse FTS queries
- Measures average query latency

### 4. Pipeline Manual Mode
- Runs full BD pipeline in manual mode (no LLM)
- Generates all 5 artifacts (research_brief, target_map, outreach, meeting_prep, followup)
- Uses isolated temp workspace

## Usage

```bash
# Run perf benchmarks only
pytest tests/test_perf_baseline.py -v

# Run with console output
pytest tests/test_perf_baseline.py -v -s

# Run with JSON output (future)
pytest tests/test_perf_baseline.py --perf-output docs/dev/_local/perf_baseline.json

# Full test suite (includes perf tests)
pytest

# Exclude perf tests (recommended for CI)
pytest -m "not perf"
```

## Verification

- **ruff check .**: All checks passed!
- **pytest -q**: 565 passed, 1 skipped

## Files Changed

```
docs/dev/reviews/PERFORMANCE_BASELINE_SPRINT-2026-01.md  (created)
tests/test_perf_baseline.py                              (created)
pyproject.toml                                           (updated — perf marker)
docs/dev/backlog/items/BI-0005-performance-baseline-harness.md (updated — status Done)
```

## Definition of Done Checklist

- [x] Perf doc exists with baseline procedures
- [x] Harness script runs offline
- [x] Baseline numbers captured for v0.2.1
- [x] No workspace isolation violations
- [x] No new dependencies added
- [x] ruff check passes
- [x] pytest passes (565 passed, 1 skipped)

## Future Work (PR #2 scope)

| Item | Priority | Notes |
|------|----------|-------|
| CI Integration | P2 | GitHub Actions job with threshold alerts |
| JSON output file | P3 | Write results to `docs/dev/_local/` |
| Historical tracking | P3 | Compare results across versions |

---

*Completion summary created as part of BI-0005 implementation.*

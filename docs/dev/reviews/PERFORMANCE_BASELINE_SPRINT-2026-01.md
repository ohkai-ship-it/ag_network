# Performance Baseline — SPRINT-2026-01

**Date:** 2026-01-30  
**Version:** v0.2.1  
**Branch:** `chore/perf-baseline-bi0005`  
**Backlog Item:** BI-0005

---

## 1. Objective

Establish a repeatable, offline performance baseline to:
- Detect regressions before they reach production
- Evaluate optimizations with data
- Provide a harness for CI integration (future)

## 2. Scope

### In Scope

| Area | Benchmark | Notes |
|------|-----------|-------|
| CLI Startup | `ag --help` cold start | Measures import + Typer init |
| Storage: Insert | 100 source records | FTS5 index overhead |
| Storage: Search (FTS) | 10 queries against 100 records | Query latency |
| Workflow: Pipeline (offline) | 5-artifact pipeline with `--mode manual` | Template-only, no LLM |

### Out of Scope

- Benchmarks requiring network access or paid APIs
- Micro-optimizations without measurement
- Memory profiling (future work)

## 3. Benchmark Definitions

### 3.1 CLI Startup Time

**Command:**
```bash
time ag --help
```

**Measures:**
- Python interpreter startup
- Module imports (typer, pydantic, httpx, etc.)
- Typer app initialization

**Target:** < 1500ms (warm) — generous initial threshold

### 3.2 Storage: Insert Operations

**Procedure:**
1. Create isolated temp workspace
2. Create fresh SQLite DB with schema init
3. Insert 100 synthetic source records with realistic field sizes
4. Measure total time and per-record average

**Target:** < 1000ms total (includes schema creation overhead)

### 3.3 Storage: FTS Search

**Procedure:**
1. Use workspace from insert benchmark
2. Run 10 diverse FTS queries
3. Measure average query latency

**Target:** < 50ms total for 10 queries

### 3.4 Pipeline Workflow (Offline)

**Procedure:**
1. Create isolated temp workspace
2. Run `ag run-pipeline "BenchmarkCorp"` in manual mode (no LLM)
3. Measure wall-clock time for full 5-artifact generation

**Target:** < 5000ms for manual mode (template-only)

## 4. Harness Design

### 4.1 Implementation

The harness is implemented as a pytest module with `@pytest.mark.perf` markers:

```
tests/test_perf_baseline.py
```

This allows:
- Running perf tests separately: `pytest -m perf`
- Excluding in CI: `pytest -m "not perf"` (recommended for CI config)
- Including in full local suite: `pytest` (runs all tests including perf)
- Outputting results to JSON

### 4.2 Output Schema

Results are written to `docs/dev/_local/perf_baseline.json` (gitignored):

```json
{
  "version": "0.2.1",
  "timestamp": "2026-01-30T10:00:00Z",
  "machine": {
    "platform": "Windows-10",
    "python": "3.14.0",
    "cpu_count": 8
  },
  "benchmarks": {
    "cli_startup_ms": 245.3,
    "storage_insert_100_ms": 32.1,
    "storage_insert_per_record_ms": 0.32,
    "storage_fts_query_avg_ms": 4.2,
    "pipeline_manual_ms": 1450.0
  },
  "notes": "Baseline capture on dev machine"
}
```

### 4.3 Running the Harness

```bash
# Run perf benchmarks only
pytest tests/test_perf_baseline.py -v

# Run with JSON output
pytest tests/test_perf_baseline.py -v --perf-output docs/dev/_local/perf_baseline.json
```

## 5. Baseline Results (v0.2.1)

> **Machine:** Windows 11 (10.0.22631), Python 3.14.0, 22-core  
> **Date:** 2026-01-30  
> **Runs:** 3 (median reported)  
> **Note:** Targets are generous initial thresholds; tighten after stable baseline established.

| Benchmark | Median | Min | Max | Target | Status |
|-----------|--------|-----|-----|--------|--------|
| CLI Startup (warm) | 37ms | 34ms | 50ms | < 1500ms | ✅ |
| Storage Insert (100) | 568ms | 550ms | 598ms | < 1000ms | ✅ |
| Storage FTS Query (avg) | 10ms | 9ms | 12ms | < 50ms | ✅ |
| Pipeline Manual | 170ms | 150ms | 227ms | < 5000ms | ✅ |

### Observations

1. **CLI Startup** is very fast (~37ms warm) - no optimization needed
2. **Storage Insert** at ~5.7ms/record includes DB creation + schema init overhead
3. **FTS Query** at ~1ms/query is well within target
4. **Pipeline Manual** at ~170ms for 5 artifacts is excellent

## 6. Variance Notes

Performance measurements are inherently noisy. To mitigate:

1. **Multiple runs:** Each benchmark runs 3x, median reported
2. **Warm-up:** CLI startup excludes first invocation
3. **Isolation:** Each benchmark uses fresh temp workspace
4. **Determinism:** No network, no LLM calls in baseline

## 7. Future Work

| Item | Priority | Notes |
|------|----------|-------|
| CI Integration | P2 | Add GitHub Actions job with threshold alerts |
| Memory Profiling | P3 | Track peak memory during pipeline |
| LLM Latency Tracking | P2 | Separate benchmark with mock timing |
| Historical Tracking | P3 | Store results across versions |

## 8. Related Items

- **BI-0005:** Performance baseline + harness (this work)
- **BI-0007:** Batch DB inserts (optimization candidate)
- **BI-0008:** Lazy workspace registry (startup optimization)
- **BI-0010:** LLM token tracking (related observability)

---

*Document created as part of BI-0005 implementation.*

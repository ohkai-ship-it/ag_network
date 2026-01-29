# PR4 Completion Summary

**Date:** 2026-01-29  
**Branch:** `pr4-truthful-cli-labels`  
**Commit:** `feat: truthful CLI labels (PR4)`

## Objective

Ensure CLI labels reflect actual execution behavior. Invariant: CLI labels (LLM/computed/placeholder/fetched/cached) MUST reflect reality.

## Changes

### A) New Module: `cli_labels.py`

**File:** [src/agnetwork/cli_labels.py](../../../src/agnetwork/cli_labels.py)

Created a truth labeling helper module with:
- `StepLabel` enum: `LLM`, `COMPUTED`, `PLACEHOLDER`, `FETCHED`, `CACHED`, `FTS`
- `format_label(label)` - Format single label with brackets
- `format_labels(labels)` - Format multiple labels
- `format_step_prefix(ws_ctx, primary_label, extra_labels)` - Full prefix with workspace
- `get_mode_labels(is_llm, is_cached, is_placeholder, is_fetched)` - Get appropriate labels

### B) Added `cached` Field to SkillMetrics

**File:** [src/agnetwork/kernel/contracts.py](../../../src/agnetwork/kernel/contracts.py)

```python
class SkillMetrics(BaseModel):
    cached: bool = False  # PR4: Track if result came from cache
```

### C) Fixed Misleading CLI Outputs

**Commands now showing truth labels:**

| Command | Before | After |
|---------|--------|-------|
| `outreach` | "📧 Creating outreach..." | "📧 [placeholder] Creating outreach..." |
| `prep` | "📋 Preparing for..." | "📋 [placeholder] Preparing for..." |
| `followup` | "📝 Creating follow-up..." | "📝 [placeholder] Creating follow-up..." |
| `research` | "🔍 Researching..." | "🔍 [computed] Starting research run..." |
| `memory search` | (no label) | "🔍 [computed] Searching (FTS)..." |
| URL fetch | "Fetching: ..." | "[fetched] ..." + "[cached]" if from cache |
| Pipeline result | "(mode: LLM)" | "[LLM]" or "[LLM] [cached]" or "[computed]" |

### D) Pipeline Mode Label

**File:** [src/agnetwork/cli.py](../../../src/agnetwork/cli.py)

Added `_build_mode_label()` helper that:
- Returns `[LLM]` when execution mode is LLM
- Appends `[cached]` if any step result has `metrics.cached=True`
- Returns `[computed]` for MANUAL mode

### E) URL Fetch Labels

All URL fetch operations now show:
- `[fetched]` prefix for fetch operations
- `[cached]` suffix when `result.is_cached` is True

## Tests

**File:** [tests/test_cli_labels_truthfulness.py](../../../tests/test_cli_labels_truthfulness.py)

23 new tests covering:

| Test Class | Count | Purpose |
|------------|-------|---------|
| `TestLabelHelpers` | 11 | Unit tests for label formatting functions |
| `TestPlaceholderLabels` | 3 | CLI placeholder commands show `[placeholder]` |
| `TestMemorySearchLabels` | 1 | Memory search shows `[computed]` and `(FTS)` |
| `TestResearchLabels` | 1 | Research shows `[computed]` |
| `TestPipelineModeLabelDistinguishesCached` | 5 | Pipeline mode labels with cache detection |
| `TestNoExternalProviderFailures` | 2 | Offline tests don't require API keys |

## Gate Results

| Check | Result |
|-------|--------|
| ruff check | ✅ All checks passed |
| pytest | ✅ 545 passed, 1 skipped |

## Test Count

| Phase | Count |
|-------|-------|
| Pre-PR4 | 522 |
| Post-PR4 | 545 (+23) |

## Backlog Update

| ID | Priority | Problem | Status |
|----|----------|---------|--------|
| 11 | P1 | Misleading output labels | **Done (PR4)** |

## How Cached Flag is Determined

Currently, `cached=True` is set when:
1. Web source fetch is served from local cache (`CapturedSource.is_cached`)

Future work (not in PR4 scope):
- LLM response caching (would set `SkillMetrics.cached=True` when LLM response is reused)

The infrastructure (`SkillMetrics.cached` field, `_build_mode_label()` function) is ready for LLM caching when implemented.

## Non-Goals (Explicitly Excluded)

- No refactoring of cli.py into submodules (ID #13 remains P2)
- No LLM response caching implementation
- No FTS workspace scoping (ID #12 remains P1)

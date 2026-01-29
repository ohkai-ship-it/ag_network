# Bug Report: Evidence Not Populated in Research Brief

**Date:** 2026-01-29  
**Reporter:** GitHub Copilot  
**Status:** � PARTIALLY FIXED - Template & Encoding Issues Resolved  
**Severity:** Low - Core functionality working, minor issues remain

---

## Summary

When running the BD pipeline with `--mode llm --deep-links --url`, the research brief's `personalization_angles` always have `is_assumption: true` with empty `source_ids` and `evidence` arrays, even though sources are successfully fetched, stored in the database, and should be available to the LLM.

---

## Steps to Reproduce

```powershell
ag run-pipeline "von Rundstedt" --url https://www.rundstedt.de --mode llm --deep-links
```

**Expected:** Personalization angles should include:
- `is_assumption: false` for facts derived from sources
- Populated `source_ids` referencing the fetched URLs
- `evidence` array with verbatim quotes from source content

**Actual:** All personalization angles have:
```json
{
  "name": "Market Leadership",
  "fact": "von Rundstedt is recognized as the market leader...",
  "is_assumption": true,
  "source_ids": [],
  "evidence": []
}
```

---

## Observations

### 1. Sources ARE Successfully Fetched and Stored

The CLI correctly:
- Fetches the homepage and 4 deep links
- Stores them in the workspace database
- Reports "✅ Captured 5 URLs"
- Sets `source_ids` in `inputs.json`

**Evidence - inputs.json:**
```json
{
  "company": "von Rundstedt",
  "source_ids": [
    "src_www_rundstedt_de_a77e3816",
    "src_www_rundstedt_de_newsletter_6e26a923",
    "src_www_rundstedt_de_berufliche_veraenderung_perspektivenberatung_5ad7200e",
    "src_www_rundstedt_de_berufliche_veraenderung_beratungsteam_4c2c799a",
    "src_www_rundstedt_de_karriere_0d5ecaab"
  ],
  ...
}
```

**Evidence - Database query confirms sources exist:**
```
src_www_rundstedt_de_karriere_0d5ecaab: Jobs & Karriere bei von Rundstedt
src_www_rundstedt_de_berufliche_veraenderung_beratungsteam_4c2c799a: Ihr Team für die berufliche Veränderung
src_www_rundstedt_de_berufliche_veraenderung_perspektivenberatung_5ad7200e: Perspektivenberatung
src_www_rundstedt_de_newsletter_6e26a923: Rundstedt News
src_www_rundstedt_de_a77e3816: von Rundstedt - Partner für die Workforce Transformation
```

### 2. Memory Retrieval Reports Success

The run log shows:
```
[memory] Retrieved evidence context - success
```

### 3. Evidence Bundle May Not Contain the Correct Source IDs

When testing the MemoryAPI's `retrieve_context` method directly:
```python
bundle = memory_api.retrieve_context(task_spec)
print(bundle.source_ids)
# Output: ['src_www_rundstedt_de_1d01dd13', 'src_www_rundstedt_de_1d01dd13', ...]
```

The bundle returns **old cached source IDs** (repeated `src_www_rundstedt_de_1d01dd13`) instead of the newly captured source IDs from the current run.

### 4. Code Flow Analysis

**Expected flow:**
1. CLI captures URLs → stores in DB with source_ids → passes to TaskSpec.inputs
2. Executor retrieves evidence_bundle via MemoryAPI
3. LLM executor calls `_load_sources_from_bundle(evidence_bundle, inputs.get("source_ids", []))`
4. Sources loaded from DB using `source_ids` from inputs (preferred over bundle.source_ids)
5. Prompt built with `require_evidence=True` and sources included
6. LLM generates facts with evidence

**Suspected break point:**
- `retrieve_context()` in MemoryAPI builds a FTS search query from the company name
- Returns whatever matches the search, NOT the explicit source_ids from TaskSpec.inputs
- The explicit source_ids in inputs ARE passed to `_load_sources_from_bundle` but...
- Either the sources aren't being loaded, OR they're not being included in the prompt

### 5. Key Code Locations

| File | Function | Purpose |
|------|----------|---------|
| `cli/commands_pipeline.py:420` | `_fetch_urls_for_pipeline()` | Captures URLs, returns source_ids |
| `cli/commands_pipeline.py:452` | TaskSpec creation | Passes `source_ids` in inputs |
| `kernel/executor.py:230` | `execute_plan()` | Retrieves evidence_bundle |
| `kernel/executor.py:474` | `_execute_step()` | Creates SkillContext with evidence_bundle |
| `kernel/llm_executor.py:123` | `execute_research_brief()` | Should load sources from bundle |
| `kernel/llm_executor.py:796` | `_load_sources_from_bundle()` | Loads source content from DB |
| `prompts/research_brief.py:6` | `build_research_brief_prompt()` | Builds prompt with sources |

### 6. Logging Gap

The LLM executor uses `logging.getLogger(__name__)` with DEBUG level logging, but these logs don't appear in the run.log file. Only INFO level logs from the orchestrator appear.

---

## Hypotheses

### Hypothesis A: Sources Not Loaded from Bundle
The `_load_sources_from_bundle` method may not be executing, or is returning an empty list.

**Test:** Add debug prints to trace execution.

### Hypothesis B: Sources Loaded but Not Passed to Prompt
The sources may be loaded but `require_evidence` is False, or sources aren't included in the prompt.

**Test:** Print the prompt being sent to the LLM.

### Hypothesis C: LLM Ignoring Evidence Instructions
The LLM receives sources but doesn't follow the evidence extraction instructions.

**Test:** Examine the actual prompt sent and LLM response.

### Hypothesis D: Workspace Context Mismatch
The workspace name passed to `_load_sources_from_bundle` may not match the actual workspace.

**Test:** Verify `context.workspace` value during execution.

---

## Debug Code Added

Temporary debug prints added to `llm_executor.py:120`:
```python
print(f"DEBUG M8: sources={len(sources)}, evidence_bundle={context.evidence_bundle is not None}, memory_enabled={context.memory_enabled}", file=sys.stderr)
print(f"DEBUG M8: source_ids from inputs={inputs.get('source_ids', [])}", file=sys.stderr)
```

**Status:** Not yet executed - user cancelled to create this report first.

---

## Resolution

### Root Cause
~~The feature was working correctly. The initial test runs used a workspace (`test_demo`) with **stale cached data** from previous runs, causing the FTS search to return old source IDs instead of freshly captured ones.~~

**Updated Finding:** The evidence extraction IS working - sources are loaded, and the LLM extracts verbatim quotes. However, the LLM incorrectly sets `is_assumption: true` even when providing evidence.

### Verification
Running with debug prints confirmed:
```
DEBUG M8: sources=0, evidence_bundle=True, memory_enabled=True
DEBUG M8: source_ids from inputs=['src_www_rundstedt_de_a77e3816', ...]
DEBUG M8: Loaded 5 sources from bundle
```

### Actual Result (test02 workspace - fresh)
The LLM provides evidence but marks ALL facts as assumptions:
```json
{
  "name": "Market Leadership",
  "fact": "German market leader in outplacement services.",
  "is_assumption": true,  // ❌ WRONG - should be false
  "source_ids": ["src_www_rundstedt_de_a77e3816"],
  "evidence": [{
    "source_id": "src_www_rundstedt_de_a77e3816",
    "quote": "Nach fast vier Jahrzehnten am Markt sind wir heute mit Abstand deutscher Marktführer im Bereich Outplacement."
  }]
}
```

### The Bug
The LLM ignores the instruction: *"If a fact comes from sources, set is_assumption: false"*

Even when the LLM:
1. ✅ Correctly identifies source_ids
2. ✅ Extracts verbatim quotes as evidence
3. ❌ Still sets `is_assumption: true`

### Possible Fixes
1. **Prompt engineering**: Reinforce the `is_assumption` logic in the prompt
2. **Post-processing**: If `evidence` array is non-empty, force `is_assumption: false`
3. **Schema validation**: Add Pydantic validator to enforce consistency

### Lesson Learned
When debugging, use a fresh workspace to avoid interference from cached data.

---

## Session Summary (2026-01-29)

### ✅ Fixed This Session

1. **Template Rendering** - `_render_research_brief_md()` in `llm_executor.py` now includes sources and evidence
2. **UTF-8 Encoding** - `orchestrator.py` `save_artifact()` now uses `encoding="utf-8"` for German characters
3. **Evidence Display** - research_brief.md now shows verbatim quotes from sources

### Files Modified (Uncommitted)

- `src/agnetwork/kernel/llm_executor.py` - Evidence rendering in markdown
- `src/agnetwork/orchestrator.py` - UTF-8 encoding for artifact files  
- `src/agnetwork/skills/research_brief.py` - Jinja2 template update (not used in LLM mode)

### 🔶 Remaining Items to Review

1. Run test suite to validate changes don't break existing tests
2. Consider adding evidence display to other artifact templates (target_map, outreach, etc.)
3. Verify behavior in computed mode (non-LLM)

---

## Related Files

- `src/agnetwork/kernel/llm_executor.py` - LLM skill execution
- `src/agnetwork/prompts/research_brief.py` - Prompt building with evidence rules
- `src/agnetwork/storage/memory.py` - MemoryAPI and EvidenceBundle
- `src/agnetwork/cli/commands_pipeline.py` - Pipeline command and URL fetching
- `src/agnetwork/kernel/executor.py` - Task/plan execution

---

## Appendix: Evidence Rules in Prompt

When `require_evidence=True`, the prompt includes:
```
EVIDENCE RULES (M8 - CRITICAL - READ CAREFULLY):
1. If a fact comes from sources, set is_assumption: false, list source_ids, AND include evidence quotes
2. QUOTES MUST BE COPIED CHARACTER-FOR-CHARACTER from the source text
...
```

This suggests the LLM is either:
- Not receiving the sources in the prompt
- Receiving sources but not understanding/following the evidence extraction rules

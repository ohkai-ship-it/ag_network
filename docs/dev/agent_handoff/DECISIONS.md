# Architecture Decisions

Log of significant design choices made during hardening.

## DECISION-0002 — Langfuse observability export is LLM-only (canonical trace stays local)

- **Date:** 2026-01-30
- **Status:** Accepted
- **Context:**
  - `agnetwork` is expected to run primarily in **LLM mode**.
  - We still require **deterministic, offline-friendly manual mode** for tests and predictable workflows.
  - Observability must not break local-first, workspace isolation, or auditability.

- **Decision:**
  1) The **canonical** observability record is a **workspace-scoped run trace** stored in the run folder (`trace.jsonl`).
  2) External observability (Langfuse) is supported only as an **optional exporter** and is enabled **only when `mode==llm`**.
  3) Manual mode must never export traces or require any network backend.
  4) Default trace capture is **redacted** (no full prompts/tool payloads), with optional debug capture only via explicit opt-in later.

- **Consequences:**
  - The system remains local-first and auditable even without Langfuse.
  - LLM runs can be debugged and analyzed in Langfuse without coupling the core to any vendor/backend.
  - CI/tests remain offline and deterministic.


## ADR-001: Workspace Isolation via Constructor Enforcement (PR1)
**Date:** 2026-01-28  
**Status:** Accepted

**Context:** `SQLiteManager` and `CRMStorage` allowed parameterless construction, defaulting to global paths. This violated workspace isolation.

**Decision:** 
- `SQLiteManager` requires `db_path` + `workspace_id` (enforced in constructor)
- `CRMStorage` requires `db_path` + `workspace_id` (enforced in constructor)
- Factory methods `for_workspace(ws_ctx)` provide ergonomic construction
- `unscoped()` escape hatch for tests/migrations only

**Consequences:**
- All storage access is workspace-scoped by default
- Tests must use `unscoped()` or create proper workspace contexts
- AST tests prevent re-introduction of global fallbacks

## ADR-002: CLI Must Use WorkspaceContext (PR2)
**Date:** 2026-01-28  
**Status:** Accepted

**Context:** CLI commands used `config.runs_dir` and `config.db_path` directly, bypassing workspace context.

**Decision:**
- All CLI commands call `get_workspace_context(ctx)` first
- Paths derived from `ws_ctx.runs_dir`, `ws_ctx.db_path`, `ws_ctx.exports_dir`
- No direct usage of `config.*` paths in CLI commands

**Consequences:**
- Each workspace has isolated runs, database, and exports
- `--workspace` flag works consistently across all commands

## ADR-003: CRM Adapter Factory Requires Workspace (PR3)
**Date:** 2026-01-29  
**Status:** Accepted

**Context:** `CRMAdapterFactory.create()` allowed `db_path=` without workspace_id.

**Decision:**
- `create()` requires `ws_ctx=` or `base_path= + workspace_id=`
- `from_env()` requires both `AG_CRM_PATH` and `AG_CRM_WORKSPACE_ID`
- Removed `db_path=` shortcut that bypassed workspace

**Consequences:**
- CRM operations are always workspace-scoped
- Dev tools must set both env vars

## ADR-004: Truthful CLI Labels (PR4)
**Date:** 2026-01-29  
**Status:** Accepted

**Context:** CLI output labels ("LLM", "manual") didn't accurately reflect execution mode or cache status.

**Decision:**
- Labels: `[LLM]`, `[computed]`, `[placeholder]`, `[fetched]`, `[cached]`
- `SkillMetrics.cached` field tracks cache hits
- `_build_mode_label()` derives label from execution mode + cache state

**Consequences:**
- Users can trust output labels
- Placeholder commands clearly marked as stubs
- Cache hits are evidence-based (not guessed)

## ADR-005: FTS Search Requires Workspace (PR5)
**Date:** 2026-01-29  
**Status:** Accepted

**Context:** FTS5 search queries (`search_sources_fts`, `search_artifacts_fts`) had no workspace filter. While isolation was achieved via separate DB files, there was no defense-in-depth.

**Decision:**
- FTS methods raise `TypeError` if `_workspace_id` is `None`
- SQL queries include `EXISTS (SELECT 1 FROM workspace_meta WHERE workspace_id = ?)` filter
- Existing tests updated to use workspace_id in fixtures

**Consequences:**
- FTS search cannot be performed without workspace context
- Even if DB files are shared/tampered, results are filtered
- Performance impact minimal (EXISTS check on 1-row table)

**Note:** FTS scoping relies on per-workspace DB files; row-level workspace filtering deferred until schema includes `workspace_id` in content tables (`sources`, `artifacts`).

## DECISION-0004: All CLI Commands Must Implement `--mode` (BI-0004)
**Date:** 2026-01-30  
**Status:** Accepted

**Context:** The `run-pipeline` command has `--mode {manual,llm}` but individual skill commands (`research`, `targets`, etc.) and work ops commands (`meeting-summary`, etc.) do not. This creates inconsistency and makes truthfulness labels unreliable — CLI-001 identified `[computed]` being printed even when LLM paths might be invoked.

**Decision:**
- **All CLI commands that generate content must implement `--mode {manual,llm}`**
- Default is `manual` (deterministic, no API keys needed)
- `llm` mode requires explicit opt-in (`--mode llm` or `AG_LLM_ENABLED=1`)
- Truthfulness labels (`[LLM]`, `[computed]`, etc.) **must reflect actual execution mode**
- Help text must be consistent across all commands

**Consequences:**
- Users can trust that `[computed]` means no LLM was invoked
- Users can run any command in LLM mode if desired
- Commands without working LLM paths may treat `--mode llm` as no-op (with warning)
- CLI_REFERENCE.md must document `--mode` for all commands
- BI-0014 is now P1 (policy enforcement, not polish)

---

## Template for New Decisions

```markdown
## ADR-XXX: Title (PR#)
**Date:** YYYY-MM-DD  
**Status:** Proposed | Accepted | Deprecated | Superseded

**Context:** What is the issue?

**Decision:** What did we decide?

**Consequences:** What are the trade-offs?
```

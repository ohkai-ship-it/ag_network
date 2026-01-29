# Architecture Decisions

Log of significant design choices made during hardening.

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

# ag_network Build Playbook (M1–M8)
**Purpose:** A repeatable, end-to-end template for building a local, auditable agent network that supports BD workflows and personal/work tasks.  
**Last updated:** 2026-01-28 (Europe/Berlin)  
**Recommended copilot model:** Opus 4.5 (VS Code)

---

## 0) What you’re building

**ag_network** is a local-first agent system that turns messy inputs (URLs, notes, intent) into **structured artifacts** (research briefs, target maps, outreach drafts, meeting prep, follow-ups, etc.) with:

- **Deterministic defaults** (LLM usage is explicit and labeled)
- **Evidence discipline** (sources captured; claims reference `source_ids`; evidence snippets can be verified)
- **Workspace isolation** (separate roots/DBs; no cross-workspace leakage)
- **Tested reliability** (ruff + pytest + golden runs + smoke tests)

The system is designed to be extended safely: add tools/components/skills/workflows without turning the codebase into “magic”.

---

## 1) Core principles (non-negotiables)

1. **Truthful CLI**  
   CLI output must match what actually happened (e.g., deterministic vs LLM; retrieved vs generated; cached vs fetched).

2. **Auditable outputs**  
   Every artifact can be traced back to sources. Evidence is embedded (JSON) and queryable (DB).

3. **Determinism by default**  
   LLM calls are opt-in and clearly marked. Deep link enrichment or other “extra fetch” behavior is opt-in.

4. **Isolation**  
   Workspace boundaries are enforced at storage boundaries (DB + run roots), not only in prompts.

5. **Small increments**  
   Every milestone is shippable. Each prompt has a tight scope, explicit acceptance criteria, and regression tests.

---

## 2) Architecture overview

### 2.1 High-level flow
```
CLI (Typer) 
  -> WorkspaceContext (manifest + policy + prefs)
    -> Kernel (TaskSpec -> Plan -> Execute)
      -> Skills (bd/work_ops/personal_ops)
        -> Tools/Components (web fetch/clean, deeplinks, memory, evidence, CRM IO)
          -> Storage (SQLite) + FTS (memory) + Run filesystem (artifacts/sources/logs)
            -> Verifier (contracts + evidence checks)
```

### 2.2 Key building blocks
- **WorkspaceContext:** roots + DB path + prefs + policy; required everywhere.
- **RunManager:** creates run folders, stores inputs, logs, artifacts, sources.
- **SQLite storage:** sources/artifacts/claims/CRM objects; plus `workspace_meta` guard.
- **FTS5 memory:** workspace-scoped search for sources/artifacts/claims.
- **Contracts:** strict models for inputs, artifacts, claims, evidence, errors.
- **Verifier:** enforces contract validity and evidence correctness; fails loudly.

---

## 3) Repository conventions

### 3.1 Suggested folder layout (conceptual)
```
src/agnetwork/
  cli.py
  config.py
  kernel/
  skills/
  tools/
  storage/
  verifier/
tests/
runs/   (optional legacy; in practice workspaces own runs/)
```

### 3.2 Run folder shape (per run)
```
<workspace_root>/runs/<run_id>__<slug>__<task>/
  inputs.json
  artifacts/
    *.json
    *.md
  sources/
    <source_id>__raw.html
    <source_id>__clean.txt
    <source_id>__meta.json
    deeplinks.json (optional)
  logs/
    agent_status.json
    agent_worklog.jsonl
    run.log
```

### 3.3 “Do not regress” guardrails
- `ruff check .` must pass
- `pytest` must pass offline
- “golden” BD runs must not change unless explicitly versioned

---

## 4) How to run (operator view)

### 4.1 Workspace basics
- Create workspace(s): `ag workspace create <name>`
- Switch workspace per command: `ag --workspace <name> ...`
- Diagnose workspace health: `ag workspace doctor <name>`

### 4.2 Core BD pipeline usage (example)
- `ag --workspace <ws> research "<company>" --url <homepage> [--deep-links] [--deep-links-mode deterministic|agent]`
- `ag --workspace <ws> targets ...`
- `ag --workspace <ws> outreach ...`
- `ag --workspace <ws> meeting-prep ...`
- `ag --workspace <ws> followup ...`

### 4.3 Validation
- `ag --workspace <ws> validate-run <run_id>` (or equivalent)
- Evidence checks should fail if quotes are not found in sources

---

## 5) The “Prompt Style” template (copy/paste scaffold)

Use this template for every milestone prompt:

- Identify repo + package + CLI
- State goal and non-negotiables
- Break into tasks with acceptance criteria
- Include tests + docs updates
- Require a final summary with proof (tests, ruff, golden)

---

# Milestone Prompts (Refined) — M1 to M8

> Each prompt below is ready to paste into VS Code (Opus 4.5).  
> Keep scope tight. Do not add “bonus features”.

---

## M1 — Foundation: Repo Skeleton + CLI + Run Files + Golden Tests + Validation

### Goal
Create the initial project skeleton with:
- working CLI entrypoint
- RunManager producing the standard run folder structure
- Artifact write/read helpers
- minimal config system
- baseline tests and a “golden run” harness
- `validate-run` CLI command that checks run integrity

### Prompt (paste into VS Code)
```
You are an autonomous development agent working in repo:
- Python package: src/agnetwork/
- CLI: ag

M1 Goal: establish a stable foundation for an auditable agent system.

Non-negotiables:
- Deterministic offline tests.
- Clear run folder shape (inputs/artifacts/sources/logs).
- ruff + pytest green.

Deliverables:
A) CLI skeleton (Typer) with a small set of commands (at least: run-pipeline, validate-run).
B) RunManager that:
   - creates run folders with timestamped run_id
   - writes inputs.json
   - writes artifacts (md/json)
   - writes logs (status/worklog)
C) Config system with sensible defaults; support overrides via env/config file.
D) Golden test harness under tests/golden/:
   - run a small deterministic flow
   - compare structural outputs (avoid brittle content)
E) validate-run:
   - checks presence of required files
   - checks JSON schema validity
   - checks artifact refs resolve

Acceptance criteria:
- `ruff check .` passes
- `pytest` passes
- at least one golden test passes
- validate-run works on a run folder and returns non-zero on missing components

Final summary must include:
- repo layout
- sample run folder
- how to run CLI + tests
```

---

## M2 — Kernel: TaskSpec + Planner + Executor + Skill Contracts + Verifier Hooks

### Goal
Introduce a kernel layer that can run multiple skills through a uniform contract:
- `TaskSpec` -> plan -> execute
- Skill contracts for inputs/outputs
- Claims model (source_ids, evidence refs)
- Verifier integration (contract-level)

### Prompt
```
You are an autonomous development agent in:
- src/agnetwork/
- CLI: ag

M2 Goal: Implement kernel architecture so all skills run through a uniform TaskSpec contract.

Non-negotiables:
- Keep deterministic default (LLM not required).
- Additive changes; do not break M1 goldens.

Deliverables:
A) TaskSpec models for core BD tasks (research_brief, target_map, outreach, meeting_prep, followup).
B) Planner producing single-step plans (no complex planning yet).
C) Executor that resolves TaskSpec -> Skill -> SkillResult.
D) SkillResult includes:
   - artifacts list (md/json)
   - optional claims (with source_ids)
   - warnings/errors
E) Verifier integration:
   - validates artifacts against schema/contracts
   - validates required fields are present

Acceptance criteria:
- Existing CLI uses kernel path for at least one task
- Tests cover TaskSpec execution and verifier
- ruff + pytest green
- goldens remain stable

Final summary:
- architecture diagram (ASCII ok)
- example TaskSpec JSON
- how to run one task via CLI
```

---

## M3 — LLM Tooling: Provider Adapters + Interchangeable Models + Roles + Structured Output

### Goal
Add LLM support without locking into one provider:
- adapter interface
- model selection via config
- roles (writer/critic/verifier) ready for later
- strict structured outputs (JSON schemas)

### Prompt
```
You are an autonomous development agent in repo:
- src/agnetwork/
- CLI: ag

M3 Goal: Add LLM tooling with provider-agnostic adapters and structured JSON output.

Non-negotiables:
- LLM must be optional; deterministic mode remains default.
- No provider-specific code outside adapters.
- All LLM outputs must be schema-validated.

Deliverables:
A) LLMAdapter interface + factory:
   - supports at least one provider stub
   - supports local mock adapter for tests
B) Role support:
   - writer role (default)
   - critic role (optional)
   - future extensibility for multiple roles
C) Structured output pipeline:
   - define JSON schemas for key artifacts
   - validate after generation; fail gracefully
D) CLI flags/config:
   - `--mode manual|llm`
   - model/provider selection via config

Acceptance criteria:
- One end-to-end task can run in LLM mode and produces schema-valid artifact JSON.
- Tests run offline using Mock adapter (no network).
- ruff + pytest green.

Final summary:
- adapter design + config examples
- how to run manual vs llm mode
```

---

## M4 — Memory: FTS5 Retrieval + Evidence Linking + Claim Traceability

### Goal
Add workspace-scoped memory and make evidence/claims traceable:
- FTS5 indexing on sources/artifacts
- retrieval API
- store claims with evidence refs
- show “retrieved vs generated” truthfully

### Prompt
```
You are an autonomous development agent in:
- src/agnetwork/
- CLI: ag

M4 Goal: Implement workspace-scoped memory retrieval (FTS5) and evidence/claims linking.

Non-negotiables:
- No cross-workspace reads.
- Deterministic retrieval tests.
- CLI must label retrieval mode truthfully.

Deliverables:
A) SQLite schema for sources/artifacts/claims plus FTS tables.
B) Memory APIs:
   - index sources/artifacts
   - search(query, workspace)
   - retrieve_context(task, workspace)
C) Claims table:
   - evidence field referencing source_ids (JSON)
D) CLI commands:
   - `ag memory search`
   - `ag memory rebuild-index`

Acceptance criteria:
- Search results are workspace-scoped.
- Tests prove no leakage.
- ruff + pytest green.

Final summary:
- schema overview
- example search usage
```

---

## M5 — Web Fetch: Source Capture (raw/clean/meta) + Caching + Evidence-Friendly Inputs

### Goal
Fetch webpages deterministically (with caching), store raw and cleaned text, and prepare evidence-friendly source objects.

### Prompt
```
You are an autonomous development agent in:
- src/agnetwork/
- CLI: ag

M5 Goal: Implement robust web fetch + source capture pipeline.

Non-negotiables:
- No network in tests (mock fetch).
- Files written in UTF-8.
- Caching must be deterministic and transparent.

Deliverables:
A) Web fetch tool:
   - fetch(url) with cache key
   - store __raw.html, __clean.txt, __meta.json
B) Cleaner:
   - produce usable clean text
   - do not corrupt encoding; write as UTF-8
C) Integrate into research:
   - research consumes captured sources
D) Tests:
   - fixture HTML -> clean text output
   - caching behavior
   - Windows-friendly file handling

Acceptance criteria:
- research run captures at least one source with full trio of files
- ruff + pytest green
- goldens stable

Final summary:
- source file naming
- how caching works
```

---

## M6 — BD Workflow Automation + CRM-Ready Outputs + Connector Prep (Generic)

### Goal
Make the BD pipeline produce CRM-ready structured artifacts and prepare for generic connectors (without choosing a CRM).

### Prompt
```
You are an autonomous development agent in:
- src/agnetwork/
- CLI: ag

M6 Goal: End-to-end BD workflow automation with CRM-ready JSON outputs and generic connector prep.

Non-negotiables:
- No external CRM integration (local files/DB only).
- Outputs must include evidence pointers (source_ids) where relevant.
- Maintain test stability and goldens.

Deliverables:
A) Pipeline: research -> target_map -> outreach -> meeting_prep -> followup
B) Each artifact has:
   - MD + JSON
   - stable schema
   - embedded evidence pointers
C) CRM export/import (local):
   - accounts/contacts/activities mapping
   - dedupe keys + deterministic IDs where appropriate
D) Generic connector interface (skeleton only):
   - CRUD shapes; no vendor implementation yet
E) Regression fixes:
   - Windows SQLite locking (close hooks)
   - mapping tests

Acceptance criteria:
- Full pipeline runs and produces all 5 artifacts.
- CRM export/import works locally.
- ruff + pytest green + golden run green.

Final summary:
- artifact schemas + example fields
- dedupe strategy
```

---

## M7 — Configurable Workspaces + Isolation + Prefs/Policy + Work/Personal Skill Packs

### Goal
Make workspace configurable via manifest and enforce hard separation; add prefs + policy; add work_ops and personal_ops packs.

### Prompt
```
You are an autonomous development agent in:
- src/agnetwork/
- CLI: ag

M7 Goal: Implement manifest-based, configurable workspaces with hard isolation and per-workspace prefs/policy.

Non-negotiables:
- WorkspaceContext required everywhere (no globals).
- DB guard with workspace_meta mismatch error.
- Isolation tests that try to break it.

Deliverables:
A) Workspace registry + workspace.toml + commands:
   - create/list/show/set-default/doctor
B) Hard isolation:
   - per-workspace runs + db + prefs + exports
   - workspace_meta guard
C) Global `--workspace` support across CLI
D) Prefs model + CLI (show/set/reset)
E) Policy enforcement (allow_memory, allow_web_fetch)
F) New skill packs:
   - work_ops: meeting_summary, status_update, decision_log
   - personal_ops: weekly_plan, errand_list, travel_outline
G) Isolation test suite (runs/DB/FTS/export/mismatch)

Acceptance criteria:
- cross-workspace search returns empty
- mismatch guard tested
- all 6 new skills run and write artifacts
- ruff + pytest green + goldens stable
```

---

## M8 — Multi-Page Enrichment + Evidence Snippets (Deep Links: Deterministic + Agent-Assisted)

### Goal
Improve research quality without embeddings:
- fetch 2–4 deep links after homepage fetch
- convert assumptions into cited facts using verbatim evidence snippets
- verifier enforces quote correctness

### Prompt
```
You are an autonomous development agent in:
- src/agnetwork/
- CLI: ag

M8 Goal: Multi-page enrichment and evidence snippets for research artifacts.

Non-negotiables:
- Deep link discovery is auditable (deeplinks.json).
- Agent-assisted selection may only choose from deterministic candidates.
- Evidence snippets must be verifiable substrings in sources.
- New behavior must be opt-in (no golden break).

Deliverables:
A) Deep link discovery tool:
   - deterministic candidate extraction + scoring (config file)
   - optional agent selection constrained to candidates
   - persist sources/deeplinks.json (candidates + selection + reasons)
B) CLI flags:
   - --deep-links / --no-deep-links (default off)
   - --deep-links-mode deterministic|agent
C) EvidenceSnippet model:
   - source_id + quote (+ optional offsets)
D) Research brief schema extension:
   - if is_assumption=false -> requires evidence[]
E) Verifier enforcement:
   - quote must exist in corresponding __clean.txt
   - fail if missing evidence or quote mismatch
F) Tests (offline):
   - deterministic deeplink selection from HTML fixture
   - agent selection invalid -> fallback
   - evidence quote exists -> pass; tampered quote -> fail
   - integration smoke: --deep-links captures >1 source and writes deeplinks.json

Acceptance criteria:
- With --deep-links, research run captures multiple sources and logs deeplinks.json.
- Evidence snippets enforced by verifier.
- ruff + pytest green; goldens unchanged unless explicitly versioned.

Final summary:
- example deeplinks.json structure
- example evidence snippet in artifact JSON
- how to run and validate
```

---

# Appendix A — Hardening backlog (post-M8)
Use as the starting point for the next “stabilize” sprint:

1) timestamps inconsistent with CLI outputs  
2) performance regression  
3) CLI truthfulness (deterministic vs LLM/retrieval)  
4) CLI redesign (commands/flags)  
5) deep code inspection for hidden bugs/critical components  
6) better abstractions for extensibility  
7) agent-layer observability (not a blackbox run)  
8) complete documentation (starter + full architecture)  
9) consolidate this playbook + prompts into a repeatable “build template”  
10) GitHub CI/CD issues (dependency/version mismatches)

---

## Appendix B — Release checklist (before tagging a version)
- ruff clean
- pytest clean
- golden runs clean
- README aligns with CLI help
- no secrets committed
- version bumped + changelog entry
- tag created (e.g., v0.3.0 / v1.0.0)


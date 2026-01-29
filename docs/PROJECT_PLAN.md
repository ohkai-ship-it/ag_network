# Complete Project Plan: Work + Private Life Agent (BD-first)

## 0) Starting point (v0.1 baseline + M1)

Your repo is already **v0.1 + M1 complete** with:

- **Package**: `agnetwork`
- **CLI commands**: `research / targets / outreach / prep / followup / status / validate-run`
- **Run system**: immutable timestamped folders with `inputs.json`, `sources/`, `artifacts/`, `logs/`
- **Artifacts**: Markdown + JSON per command (with version metadata)
- **Logging**: `agent_worklog.jsonl` + `agent_status.json`
- **SQLite traceability**: `sources, companies, artifacts, claims`
- **Quality**: 33 tests passing + ruff clean
- **CI pipeline**: GitHub Actions for ruff + pytest (M1)
- **Golden tests**: Regression tests for artifact structure (M1)
- **Validation**: `bd validate-run` command (M1)
- **Known limitations**: no web scraping, no LLM generation yet

This is the foundation we will extend without breaking.

---

## 1) Target agent architecture

### 1.1 Layered design (keep the backbone, add an Agent Kernel)

```
Interfaces
  - CLI (now)
  - later: Web UI / Chat / API
        ↓
Agent Kernel (new)
  - TaskSpec normalization
  - Planner (optional at first)
  - Step executor (tool-using)
  - Verifier (checks + evidence)
  - Approval gates (human-in-loop)
        ↓
Skill Packs (domain logic)
  - BD pack (existing 5 deliverables)
  - Work Ops pack (docs, updates, meeting logs)
  - Personal Ops pack (planning, admin)
        ↓
Tools (I/O + integrations)
  - Ingest (exists)
  - LLM (next)
  - Web fetch/clean/cache (next)
  - later: Calendar / Email / CRM (gated)
        ↓
Memory / Data plane
  - Episodic: Runs (immutable history)
  - Semantic: SQLite (reusable facts + sources + claims)
  - later: Retrieval index (FTS + vector)
```

### 1.2 Safety & governance (non-negotiable)

- **Everything is a run with logs + artifacts** (auditability and reproducibility)
- **Approval gates** for any external impact (send/write/spend/delete)

---

## 2) Skill contracts (standard for all capabilities)

### 2.1 Definition

A **skill** is a bounded module that:

- accepts typed input (`Pydantic`)
- optionally consumes evidence (`SourceRef`s retrieved from memory)
- outputs a typed domain object (`Pydantic`) + renderable artifact
- emits **claims** that are either backed by sources or explicitly labeled assumption/inference

### 2.2 Contract model (what “done” looks like for every skill)

**Inputs**
- task parameters (company/persona/channel/meeting type/notes)
- constraints (tone, length, language)
- evidence bundle (list of `SourceRef`s + prior relevant artifacts)

**Outputs**
- `output: <DomainModel>` (e.g., `OutreachDraft`, `MeetingPrepPack`)
- `artifacts: [ArtifactRef]` (expects MD + JSON in run folder)
- `claims: [Claim]` (fact/assumption/inference + evidence links)
- `warnings / next_actions / metrics`

**Invariants**
- Skill has **no side effects** (no file/db/network writes directly)
- Orchestrator writes everything and logs it

---

## 3) Memory strategy and where RAG fits

### 3.1 Memory organization

- **Episodic memory = Runs** (what happened, with what inputs, outputs, logs)
- **Semantic memory = SQLite** (sources/claims/artifacts you can reuse)

### 3.2 RAG usefulness (yes — but staged)

RAG becomes a multiplier once you have a meaningful corpus:
- your old research briefs, outreach drafts, transcripts, personal notes, case studies
- and you want “reuse what worked” + “find similar accounts”

**Do it in phases:**
1. **FTS first (cheap win)**: SQLite FTS5 over artifact text + sources
2. **Chunking + hybrid retrieval**: BM25 (exact terms) + vector (semantic similarity)
3. **Evidence RAG**: retrieval returns source IDs/excerpts so skills can attach evidence to claims

RAG is not a substitute for web freshness; it amplifies *your own knowledge base*.

---

## 4) Milestone plan (M0 → M8)

### M0 — Baseline locked ✅ (done)

**Outcome:** v0.1 is stable and verified.

**DoD**
- All commands run successfully
- Artifacts created in correct locations (MD + JSON)
- Logs/status files updated
- Tests pass + ruff passes
- No secrets committed

---

### M1 — Platform hardening ✅ (done)

**Goal:** make changes safe and regression-proof.

**Deliverables**
- ✅ CI pipeline for `ruff + pytest` (`.github/workflows/ci.yml`)
- ✅ Artifact schema versioning (`artifact_version`, `skill_version` in meta block)
- ✅ "Golden runs" regression tests (`tests/golden/test_golden_runs.py`)
- ✅ Logging consistency checks (`bd validate-run` command)

**DoD**
- ✅ Any breaking change gets caught by CI or golden tests
- ✅ Refactors don't silently change outputs
- ✅ 33 tests passing

---

### M2 — Agent Kernel + Skill Contract Standardization

**Goal:** introduce the agent layer without breaking existing commands.

**Deliverables**
- `TaskSpec` (normalized request model)
- `Plan` + `Step` model (explicit step graph)
- `Skill` interface + `SkillResult` (skill contract)
- `Verifier` module (completeness + evidence + policy checks)
- Backward-compatible wrappers (CLI can call old flow or kernel flow)

**DoD**
- Existing commands still work identically
- Kernel can run a multi-step “BD pipeline run” as one run

---

### M3 — LLM integration (as a tool, not magic)

**Goal:** enable high-quality drafting while keeping determinism, auditability, and traceability.

**Deliverables**
- `LLMClient` interface + providers (Anthropic/OpenAI/etc.)
- Structured outputs enforced via Pydantic parsing
- “Critic pass” for unsupported claims / missing sections
- Manual/offline mode remains functional

**DoD**
- Each BD skill supports:
  - deterministic/manual mode
  - LLM-assisted mode (valid JSON + MD + claims)
- Tests run with a mocked LLM

---

### M4 — Evidence pipeline + Retrieval (RAG phase 1: FTS)

**Goal:** “search my own runs” and reuse proven material.

**Deliverables**
- Source normalization: consistent `Source` metadata + storage policy
- SQLite FTS5 over artifacts + ingested sources
- `memory.search_*()` API returning `SourceRef`s + excerpts

**DoD**
- Skills can retrieve prior relevant artifacts/sources and cite them
- Evidence gets attached to claims when used

---

### M5 — Web research automation (freshness + caching + evidence)

**Goal:** make web evidence real and reproducible.

**Deliverables**
- Fetch → clean → store pipeline (cached into `runs/.../sources/`)
- Source capture policy (store raw + cleaned text; store fetch metadata)
- Evidence-first research brief: key statements link to stored sources

**DoD**
- Research briefs cite captured sources (stored in runs and indexed in DB)
- Runs are reproducible without refetching

---

### M6 — BD workflow automation + CRM read-only (and gated export)

**Goal:** operate in “pipeline mode” and integrate with your pipeline tooling safely.

**Deliverables**
- Pipeline runner: “BD Pack Run” produces all 5 artifacts in one run
- Sequence builder (still draft-only; no auto-send)
- CRM integration:
  - read-only importer (contacts/accounts)
  - exporter for updates (CSV/JSON) behind approval gate

**DoD**
- One command produces a complete BD pack
- No external writes without explicit approval

---

### M7 — Work Ops + Personal Ops skill packs (workspace isolation)

**Goal:** expand beyond BD with privacy boundaries.

**Deliverables**
- Workspace split: `work` vs `personal`
  - separate DBs and runs folder namespaces
- Work skills: status update, one-pager, decision log, meeting summary
- Personal skills: planning, errands, travel outline, household admin
- Preference model: explicit editable defaults (tone, language, templates)

**DoD**
- No cross-contamination between work and personal memory
- Same skill contract + run audit applies everywhere

---

### M8 — RAG phase 2 (hybrid retrieval) + UX layer

**Goal:** daily usability at scale.

**Deliverables**
- Hybrid retrieval (FTS/BM25 + vectors) + reranking
- Chunking strategy for long docs/transcripts
- Web UI dashboard:
  - run history
  - artifact viewer
  - approve/export actions
  - search across memory

**DoD**
- “Find similar accounts” and “reuse what worked” becomes fast and reliable
- You can operate mostly via UI rather than filesystem

---

## 5) Cross-cutting rules (apply to every milestone)

- Master orchestrator discipline: verify after each step, log actions, keep run outputs stable
- Approval gates for anything external-impacting
- Regression safety: golden runs + schema versioning (start in M1)
- Evidence-first: claims cite sources or are explicitly labeled as assumptions

---

## 6) Suggested execution order

Recommended order for momentum with minimal risk:

1. **M1 Platform hardening**
2. **M2 Kernel + contracts**
3. **M3 LLM tool**
4. **M4 Retrieval (FTS)**
5. **M5 Web evidence**
6. Then M6–M8

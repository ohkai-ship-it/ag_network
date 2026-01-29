# Review Guide — How to run a thorough code review with Copilot (ag_network)

This guide tells you *how* to use Copilot to walk you through a systematic review while you fill:
- `CODE_REVIEW_NOTES.md`
- `FINDINGS_BACKLOG.md`

## 1) The workflow (repeatable)
1. **Pick a subsystem** (CLI, Workspace, Storage, Memory/FTS, Web, Evidence/Verifier, Kernel, Skills, Observability, CI/CD).
2. Ask Copilot to **review it in 8 dimensions**:
   - purpose & responsibilities
   - invariants and failure modes
   - boundary checks (workspace, storage, run manager, LLM adapter)
   - error handling/logging
   - performance risks
   - security/privacy risks
   - tests (what exists, what’s missing)
   - smallest safe fixes + tests
3. **Write findings into `CODE_REVIEW_NOTES.md`**:
   - Observations, Risks (P0/P1/P2), Recommendations, Tests to add
4. For each actionable item, create a backlog entry in `FINDINGS_BACKLOG.md`:
   - title, location, impact, smallest safe fix, proof/test, status
5. After every subsystem, **pick 1–3 P0/P1 items** to implement immediately (avoid scope creep).

## 2) Severity rubric
- **P0**: breaks trust/isolation/security; misleading CLI; evidence enforcement failing; data corruption.
- **P1**: performance regressions; intermittent failures; maintainability risks; missing tests around critical invariants.
- **P2**: readability; small refactors; UX polish; nice-to-have docs.

## 3) Copilot prompt snippet (use per subsystem)
Paste and adjust the file list:

```
Review the following subsystem thoroughly and walk me through it step-by-step:
FILES: <list>
Focus:
1) Purpose & responsibilities
2) Invariants + failure modes
3) Boundary checks (workspace context, storage factory, run manager, LLM adapter)
4) Error handling + logging
5) Performance risks
6) Security/privacy risks
7) Tests coverage gaps
8) Recommendations (smallest safe change + test)

Output:
- Observations
- Risks (P0/P1/P2)
- Recommendations
- Tests to add
- Next file/function to inspect (exact symbol names)
```

## 4) Recommended review order (high leverage first)
1) CLI + workspace propagation + truthfulness
2) Storage/DB factory + workspace_meta guard
3) Memory/FTS indexing + retrieval (and labeling)
4) Web ingestion + caching + evidence snippet enforcement
5) Kernel execution + skill registry
6) Skills consistency
7) Observability (traceability; explain runs)
8) CI/CD + packaging/versioning

## 5) Definition of Done for a “review pass”
- All subsystems reviewed and documented in `CODE_REVIEW_NOTES.md`
- Backlog created with priorities + tests specified
- At least the top 3 P0 issues have concrete fix plans and acceptance tests

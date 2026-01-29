# BUG-XXXX — <short, specific title>

## Metadata
- **ID:** BUG-XXXX
- **Status:** Open | Investigating | Blocked | Fixed | Won't fix
- **Priority:** P0 | P1 | P2
- **Area:** CLI | Kernel | Storage | Skills | Runs | Docs | CI
- **Owner:** <Kai / Jeff / Jacob>
- **Reported by:** <name>
- **First seen:** YYYY-MM-DD
- **Last verified:** YYYY-MM-DD
- **Version/branch:** v0.2 / main
- **Workspace:** <workspace_id> (if applicable)

## Summary (1–3 sentences)
What is broken and why it matters (user impact + invariant impact).

## Invariant impact
Check all that apply:
- [ ] Workspace isolation violated / suspicious
- [ ] “Truthful CLI” violated (labels don’t match reality)
- [ ] Non-deterministic behavior without opt-in
- [ ] Auditability broken (missing sources/evidence/run trace)
- [ ] Potential data corruption / unsafe writes

## Steps to reproduce
1. ...
2. ...
3. ...

### Minimal repro command(s)
```bash
# paste exact CLI commands
```

## Expected behavior
- ...

## Actual behavior
- ...

## Evidence
Attach or link:
- Run folder path(s): `runs/<run_id>/...`
- Logs / trace events (if available)
- Screenshots (if needed)

## Suspected root cause (optional)
- ...

## Proposed fix (optional)
- ...

## Regression test plan
- [ ] Add/extend unit test: <file>
- [ ] Add/extend integration test: <file>
- [ ] Add golden output update (only if versioned and intentional)

## Fix log
- YYYY-MM-DD: <note>
- PR: <link>

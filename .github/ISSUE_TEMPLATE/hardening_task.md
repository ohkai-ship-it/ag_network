---
name: Hardening Task
about: Fix a workspace isolation or trust issue from the backlog
title: '[HARDENING] '
labels: hardening, p0-trust
assignees: ''
---

## Backlog Reference
<!-- From docs/dev/reviews/FINDINGS_BACKLOG.md -->
- **ID:** #
- **Priority:** P0 / P1 / P2
- **Area:** Storage / CLI / CRM / Kernel

## Problem
<!-- What's the issue? -->

## Current Behavior
<!-- What happens now? -->

## Expected Behavior
<!-- What should happen? -->

## Proposed Fix
<!-- Smallest safe change -->

## Invariant to Enforce
<!-- Which rule does this protect? -->
- [ ] Workspace isolation (no cross-workspace leakage)
- [ ] Truthful CLI labels
- [ ] No global path fallbacks
- [ ] Other: ___

## Acceptance Criteria
- [ ] Fix implemented
- [ ] AST/regression test added
- [ ] `ruff check .` passes
- [ ] `pytest` passes
- [ ] CURRENT_STATE.md updated

## Test to Add
<!-- Name of the test that proves the fix works -->
`test_xxx`

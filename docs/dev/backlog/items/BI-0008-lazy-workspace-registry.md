# BI-0008 — Lazy workspace registry loading

## Metadata
- **ID:** BI-0008
- **Type:** Performance
- **Status:** Proposed
- **Priority:** P2
- **Area:** Workspaces
- **Owner:** TBD
- **Target sprint:** TBD
- **Source:** BI-0003 code review (PERF-002)

## Problem

`WorkspaceRegistry.list_workspaces()` scans the filesystem on every call. For CLI commands that only need a single workspace (most commands), this is unnecessary overhead.

Currently:
```python
# registry.py
def list_workspaces(self) -> List[str]:
    workspaces = []
    for item in self.workspaces_root.iterdir():
        if item.is_dir() and (item / "workspace.toml").exists():
            workspaces.append(item.name)
    return workspaces
```

## Goal

Implement lazy loading with optional caching:
1. Only scan when `list_workspaces()` is actually called
2. Cache result for duration of CLI invocation
3. Invalidate cache on workspace create/delete

## Non-goals

- Persistent cache across invocations (overkill for current scale)
- Watch-based invalidation (complexity not warranted)

## Acceptance criteria

- [ ] `list_workspaces()` result is cached after first call
- [ ] Cache invalidated when `create_workspace()` or `delete_workspace()` called
- [ ] `load_workspace(name)` does NOT trigger full scan
- [ ] Unit tests verify caching behavior
- [ ] (Optional) Benchmark shows improvement for repeated `list_workspaces()` calls

## Implementation notes

Simple approach:
```python
class WorkspaceRegistry:
    def __init__(self):
        self._workspace_cache: Optional[List[str]] = None
    
    def list_workspaces(self) -> List[str]:
        if self._workspace_cache is None:
            self._workspace_cache = self._scan_workspaces()
        return self._workspace_cache
    
    def _invalidate_cache(self):
        self._workspace_cache = None
```

## Risks

- Stale cache if external process modifies workspaces (acceptable for CLI)

## PR plan

1. PR (S): Add caching to WorkspaceRegistry + tests

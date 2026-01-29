# BI-0012 — CLI progress indicators for long operations

## Metadata
- **ID:** BI-0012
- **Type:** CLI UX
- **Status:** Proposed
- **Priority:** P2
- **Area:** CLI
- **Owner:** TBD
- **Target sprint:** TBD
- **Source:** BI-0003 code review (CLI-005)

## Problem

Long-running CLI operations (research, pipeline runs) give no feedback until completion. This leads to:

- Users wondering if the command hung
- No way to estimate remaining time
- No visibility into which step is running

Example: `agn research run von_rundstedt` takes 30-60s with no output until done.

## Goal

Add progress indicators for operations that take >2 seconds:
- Spinner for indeterminate progress
- Step indicators for multi-step operations
- Optional progress bar for deterministic operations

## Non-goals

- Real-time streaming of LLM responses (future feature)
- Detailed logs to stdout (already available via `--verbose`)
- GUI progress indicators

## Acceptance criteria

- [ ] `agn research run` shows spinner with current step name
- [ ] `agn pipeline run` shows step progress (e.g., "Step 2/5: research_brief")
- [ ] Progress is suppressed when `--quiet` is set
- [ ] Progress works correctly in non-TTY environments (CI/pipes)
- [ ] No progress spam in logs (only final status)
- [ ] Unit tests verify progress callbacks are invoked

## Proposed UX

### Spinner mode (indeterminate)
```
⠋ Researching von_rundstedt...
⠙ Researching von_rundstedt... (12s)
✓ Research complete (18s)
```

### Step mode (determinate)
```
Pipeline: golden_demo
[1/5] research_brief ⠋ Running...
[1/5] research_brief ✓ (8s)
[2/5] target_map ⠋ Running...
[2/5] target_map ✓ (12s)
[3/5] outreach ⠋ Running...
```

## Implementation notes

Use `rich.progress` or `rich.status`:
```python
from rich.console import Console
from rich.status import Status

console = Console()

with console.status("[bold blue]Researching...") as status:
    for step in steps:
        status.update(f"[bold blue]{step.name}...")
        execute_step(step)
        
console.print("[green]✓ Complete")
```

For step progress:
```python
from rich.progress import Progress

with Progress() as progress:
    task = progress.add_task("Pipeline", total=len(steps))
    for step in steps:
        # ... execute ...
        progress.advance(task)
```

## TTY detection

```python
import sys

if sys.stdout.isatty():
    # Use spinner/progress bar
else:
    # Use simple line-by-line output
    print(f"Running {step.name}...")
```

## Risks

- Rich progress may not work in all terminals
- Need to handle Ctrl+C gracefully with progress active

## Dependencies

- `rich` library (already a dependency)

## PR plan

1. PR (S): Add progress helper + integrate with research command
2. PR (S): Integrate with pipeline command

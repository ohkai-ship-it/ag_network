"""CLI label formatting for truthful output.

PR4: Truthful CLI Labels

Every user-visible output step must be prefixed with a truth label:
- [LLM] - LLM call was actually used
- [computed] - Deterministic code produced it (no LLM)
- [placeholder] - Output is a stub/template (not real logic/LLM)
- [fetched] - Network retrieval happened (web fetch)
- [cached] - Result came from cache (no new LLM/fetch call)

Labels can be combined: [LLM] [cached], [computed], [fetched] [cached]
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from agnetwork.workspaces.context import WorkspaceContext


class StepLabel(str, Enum):
    """Truth labels for CLI step output."""

    LLM = "LLM"  # LLM call was used
    COMPUTED = "computed"  # Deterministic code (no LLM)
    PLACEHOLDER = "placeholder"  # Stub/template output
    FETCHED = "fetched"  # Network retrieval (web fetch)
    CACHED = "cached"  # Result from cache (no new call)
    FTS = "FTS"  # Full-text search (sub-type of computed)


def format_label(label: StepLabel) -> str:
    """Format a single label with brackets.

    Args:
        label: The step label to format

    Returns:
        Formatted label string, e.g. "[LLM]"
    """
    return f"[{label.value}]"


def format_labels(labels: List[StepLabel]) -> str:
    """Format multiple labels with brackets.

    Args:
        labels: List of step labels to format

    Returns:
        Formatted labels string, e.g. "[LLM] [cached]"
    """
    if not labels:
        return ""
    return " ".join(format_label(label) for label in labels)


def format_step_prefix(
    ws_ctx: Optional["WorkspaceContext"] = None,
    primary_label: Optional[StepLabel] = None,
    extra_labels: Optional[List[StepLabel]] = None,
) -> str:
    """Format a step prefix with workspace and truth labels.

    Args:
        ws_ctx: Optional workspace context for workspace name
        primary_label: Primary truth label (LLM, computed, placeholder, fetched)
        extra_labels: Additional labels (e.g., cached)

    Returns:
        Formatted prefix string, e.g. "[workspace: my_ws] [LLM] [cached]"

    Examples:
        >>> format_step_prefix(ws_ctx, StepLabel.LLM)
        "[workspace: my_ws] [LLM]"
        >>> format_step_prefix(ws_ctx, StepLabel.COMPUTED, [StepLabel.CACHED])
        "[workspace: my_ws] [computed] [cached]"
        >>> format_step_prefix(None, StepLabel.PLACEHOLDER)
        "[placeholder]"
    """
    parts = []

    # Add workspace prefix if provided
    if ws_ctx is not None:
        parts.append(f"[workspace: {ws_ctx.name}]")

    # Add primary label
    if primary_label is not None:
        parts.append(format_label(primary_label))

    # Add extra labels
    if extra_labels:
        parts.extend(format_label(label) for label in extra_labels)

    return " ".join(parts)


def get_mode_labels(
    is_llm: bool = False,
    is_cached: bool = False,
    is_placeholder: bool = False,
    is_fetched: bool = False,
) -> List[StepLabel]:
    """Get appropriate labels based on execution mode.

    Args:
        is_llm: Whether LLM was used
        is_cached: Whether result was from cache
        is_placeholder: Whether this is placeholder/stub output
        is_fetched: Whether network fetch occurred

    Returns:
        List of appropriate labels
    """
    labels = []

    if is_placeholder:
        labels.append(StepLabel.PLACEHOLDER)
    elif is_llm:
        labels.append(StepLabel.LLM)
    elif is_fetched:
        labels.append(StepLabel.FETCHED)
    else:
        labels.append(StepLabel.COMPUTED)

    if is_cached:
        labels.append(StepLabel.CACHED)

    return labels

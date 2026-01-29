"""CLI app setup and common utilities.

This module creates the main Typer app and provides shared utilities
for workspace resolution and context management used by all commands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import typer
from typer import Context, Typer

from agnetwork.config import config

if TYPE_CHECKING:
    from agnetwork.workspaces.context import WorkspaceContext

# Initialize Typer app
app = Typer(
    name="ag_network",
    help="Agent network: Workflow orchestration for agentic AI with multiple workspaces and skillsets.",
)


# =============================================================================
# Global Context Object for Workspace Resolution
# =============================================================================


class CLIState:
    """Shared state object for CLI commands.

    Holds the resolved workspace context when --workspace is used.
    """

    def __init__(self):
        self.workspace_context: Optional["WorkspaceContext"] = None
        self.workspace_name: Optional[str] = None


def resolve_workspace(name: Optional[str]) -> "WorkspaceContext":
    """Resolve workspace by name, or return default.

    Args:
        name: Workspace name, or None for default.

    Returns:
        WorkspaceContext for the resolved workspace.

    Raises:
        typer.Exit: If workspace not found.
    """
    from agnetwork.workspaces import WorkspaceRegistry

    registry = WorkspaceRegistry()

    if name is None:
        # Use default workspace (or create "default" if none exists)
        try:
            return registry.get_or_create_default()
        except Exception as e:
            typer.echo(f"❌ Error loading default workspace: {e}", err=True)
            raise typer.Exit(1)

    # Explicit workspace name provided
    if not registry.workspace_exists(name):
        typer.echo(f"❌ Workspace not found: {name}", err=True)
        typer.echo("   Use 'ag workspace list' to see available workspaces.")
        raise typer.Exit(1)

    try:
        return registry.load_workspace(name)
    except Exception as e:
        typer.echo(f"❌ Error loading workspace '{name}': {e}", err=True)
        raise typer.Exit(1)


def get_workspace_context(ctx: Context) -> "WorkspaceContext":
    """Get workspace context from Typer context.

    The workspace is always resolved by the app callback (init_app),
    so this should never return None in normal CLI usage.

    Args:
        ctx: Typer context object.

    Returns:
        WorkspaceContext (never None in normal usage).

    Raises:
        RuntimeError: If called before init_app callback.
    """
    if ctx.obj is not None and ctx.obj.workspace_context is not None:
        return ctx.obj.workspace_context
    # This shouldn't happen in normal CLI usage since init_app always sets it
    raise RuntimeError("Workspace context not initialized - this is a bug")


@app.callback()
def init_app(
    ctx: Context,
    workspace: Optional[str] = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Use a specific workspace (default: configured default workspace)",
        envvar="AG_WORKSPACE",
    ),
):
    """Initialize the application with optional workspace selection.

    Use --workspace to run commands in a specific workspace context.
    All runs, artifacts, and database operations will be scoped to that workspace.
    """
    config.ensure_directories()

    # Initialize CLI state object
    ctx.ensure_object(CLIState)

    # Always resolve workspace - either explicit or default
    ctx.obj.workspace_name = workspace
    ctx.obj.workspace_context = resolve_workspace(workspace)

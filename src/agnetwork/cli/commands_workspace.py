"""Workspace and preferences CLI commands.

Commands for workspace management (M7):
- workspace create: Create a new workspace
- workspace list: List all registered workspaces
- workspace show: Show workspace details
- workspace set-default: Set the default workspace
- workspace doctor: Run health checks

Commands for preferences management (M7):
- prefs show: Show current preferences
- prefs set: Set a preference value
- prefs reset: Reset preferences to defaults
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from typer import Typer

from agnetwork.cli.app import app

# ============================================================================
# Workspace Management Commands (M7)
# ============================================================================

workspace_app = Typer(
    name="workspace",
    help="Manage workspaces with isolated storage, runs, and preferences.",
)
app.add_typer(workspace_app, name="workspace")


@workspace_app.command(name="create")
def workspace_create(
    name: str = typer.Argument(..., help="Workspace name"),
    root: Optional[Path] = typer.Option(
        None, "--root", "-r", help="Custom root directory (default: ~/.agnetwork/workspaces/<name>)"
    ),
    set_default: bool = typer.Option(False, "--set-default", help="Set as default workspace"),
):
    """Create a new workspace with isolated storage.

    Example:
        ag workspace create myproject
        ag workspace create work --root ~/work/agdata --set-default
    """
    from agnetwork.storage.sqlite import SQLiteManager
    from agnetwork.workspaces import WorkspaceRegistry

    try:
        registry = WorkspaceRegistry()
        context = registry.create_workspace(
            name=name,
            root_dir=root,
            set_as_default=set_default,
        )

        typer.echo(f"✅ Created workspace: {name}")
        typer.echo(f"   ID: {context.workspace_id}")
        typer.echo(f"   Root: {context.root_dir}")
        typer.echo(f"   Runs: {context.runs_dir}")
        typer.echo(f"   DB: {context.db_path}")

        # Initialize database with workspace_meta
        db = SQLiteManager(db_path=context.db_path, workspace_id=context.workspace_id)
        db.init_workspace_metadata(context.workspace_id)
        typer.echo("   ✓ Database initialized")

        if set_default:
            typer.echo("   ✓ Set as default workspace")

    except ValueError as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {e}", err=True)
        raise typer.Exit(1)


@workspace_app.command(name="list")
def workspace_list():
    """List all registered workspaces.

    Example:
        ag workspace list
    """
    from agnetwork.workspaces import WorkspaceRegistry

    registry = WorkspaceRegistry()
    workspaces = registry.list_workspaces()
    default_name = registry.get_default_workspace()

    if not workspaces:
        typer.echo("No workspaces found. Create one with: ag workspace create <name>")
        return

    typer.echo("📁 Registered workspaces:\n")
    for ws_name in workspaces:
        marker = " (default)" if ws_name == default_name else ""
        typer.echo(f"   • {ws_name}{marker}")


@workspace_app.command(name="show")
def workspace_show(
    name: Optional[str] = typer.Argument(None, help="Workspace name (default: current default)"),
):
    """Show detailed information about a workspace.

    Example:
        ag workspace show myproject
        ag workspace show  # shows default workspace
    """
    from agnetwork.workspaces import WorkspaceRegistry

    try:
        registry = WorkspaceRegistry()

        if name is None:
            name = registry.get_default_workspace()
            if name is None:
                typer.echo(
                    "❌ No default workspace set. Specify name or create default workspace.",
                    err=True,
                )
                raise typer.Exit(1)

        info = registry.get_workspace_info(name)

        typer.echo(f"📁 Workspace: {info['name']}")
        typer.echo(f"   ID: {info['workspace_id']}")
        typer.echo(f"   Root: {info['root_dir']}")
        typer.echo(f"   Default: {info['is_default']}")
        typer.echo("\n📂 Paths:")
        for path_name, path_val in info["paths"].items():
            exists = (
                "✓"
                if info["paths_exist"].get(
                    path_name.replace("_dir", "") if path_name.endswith("_dir") else path_name,
                    False,
                )
                else "✗"
            )
            typer.echo(f"   {exists} {path_name}: {path_val}")
        typer.echo("\n🔒 Policy:")
        for key, val in info["policy"].items():
            typer.echo(f"   {key}: {val}")

    except FileNotFoundError as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


@workspace_app.command(name="set-default")
def workspace_set_default(name: str = typer.Argument(..., help="Workspace name to set as default")):
    """Set the default workspace.

    Example:
        ag workspace set-default myproject
    """
    from agnetwork.workspaces import WorkspaceRegistry

    try:
        registry = WorkspaceRegistry()
        registry.set_default_workspace(name)
        typer.echo(f"✅ Set default workspace to: {name}")
    except ValueError as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


def _doctor_collect(context) -> list[tuple[str, str, bool, str]]:
    """Collect health check results for a workspace.

    Returns list of (category, label, ok, detail) tuples.
    """
    from agnetwork.storage.sqlite import SQLiteManager

    checks: list[tuple[str, str, bool, str]] = []

    # Directory checks
    path_checks = context.verify_paths()
    for path_name, exists in path_checks.items():
        checks.append(("📂 Directory", path_name, exists, ""))

    # Database checks
    if context.db_path.exists():
        checks.append(("💾 Database", "Database file exists", True, ""))
        try:
            db = SQLiteManager(db_path=context.db_path, workspace_id=context.workspace_id)
            ws_id = db.get_workspace_id()
            if ws_id == context.workspace_id:
                checks.append(("💾 Database", "Workspace ID matches", True, ""))
            else:
                checks.append(
                    (
                        "💾 Database",
                        "Workspace ID mismatch",
                        False,
                        f"expected {context.workspace_id}, got {ws_id}",
                    )
                )
        except Exception as e:
            checks.append(("💾 Database", "Database error", False, str(e)))
    else:
        checks.append(("💾 Database", "Database file missing", False, ""))

    # Manifest checks
    manifest_path = context.root_dir / "workspace.toml"
    checks.append(("📄 Manifest", "Manifest exists", manifest_path.exists(), ""))

    return checks


def _doctor_print(name: str, checks: list[tuple[str, str, bool, str]]) -> bool:
    """Print doctor check results and return True if all passed."""
    typer.echo(f"🔍 Checking workspace: {name}\n")

    current_category = None
    all_ok = True

    for category, label, ok, detail in checks:
        if category != current_category:
            if current_category is not None:
                typer.echo("")
            typer.echo(f"{category} checks:")
            current_category = category

        status = "✓" if ok else "✗"
        detail_str = f": {detail}" if detail else ""
        typer.echo(f"   {status} {label}{detail_str}")
        if not ok:
            all_ok = False

    if all_ok:
        typer.echo("\n✅ All checks passed")
    else:
        typer.echo("\n⚠️ Some checks failed")

    return all_ok


@workspace_app.command(name="doctor")
def workspace_doctor(
    name: Optional[str] = typer.Argument(None, help="Workspace name (default: current default)"),
):
    """Run health checks on a workspace.

    Example:
        ag workspace doctor myproject
        ag workspace doctor  # checks default workspace
    """
    from agnetwork.workspaces import WorkspaceRegistry

    try:
        registry = WorkspaceRegistry()

        if name is None:
            name = registry.get_default_workspace()
            if name is None:
                typer.echo("❌ No default workspace set.", err=True)
                raise typer.Exit(1)

        context = registry.load_workspace(name)
        checks = _doctor_collect(context)
        all_ok = _doctor_print(name, checks)

        if not all_ok:
            raise typer.Exit(1)

    except FileNotFoundError as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


# ============================================================================
# Preferences Commands (M7)
# ============================================================================

prefs_app = Typer(
    name="prefs",
    help="Manage workspace preferences (language, tone, defaults).",
)
app.add_typer(prefs_app, name="prefs")


@prefs_app.command(name="show")
def prefs_show(
    workspace: Optional[str] = typer.Option(
        None, "--workspace", "-w", help="Workspace name (default: current default)"
    ),
):
    """Show current preferences for a workspace.

    Example:
        ag prefs show
        ag prefs show --workspace myproject
    """
    from agnetwork.workspaces import WorkspaceRegistry
    from agnetwork.workspaces.preferences import PreferencesManager

    try:
        registry = WorkspaceRegistry()

        if workspace is None:
            workspace = registry.get_default_workspace()
            if workspace is None:
                typer.echo("❌ No default workspace set.", err=True)
                raise typer.Exit(1)

        context = registry.load_workspace(workspace)
        prefs_manager = PreferencesManager(context.prefs_path)
        prefs = prefs_manager.show()

        typer.echo(f"⚙️ Preferences for workspace: {workspace}\n")
        for key, value in prefs.items():
            typer.echo(f"   {key}: {value}")

    except FileNotFoundError as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


@prefs_app.command(name="set")
def prefs_set(
    key: str = typer.Argument(..., help="Preference key"),
    value: str = typer.Argument(..., help="Preference value"),
    workspace: Optional[str] = typer.Option(
        None, "--workspace", "-w", help="Workspace name (default: current default)"
    ),
):
    """Set a preference value for a workspace.

    Example:
        ag prefs set tone casual
        ag prefs set language de --workspace myproject
    """
    from agnetwork.workspaces import WorkspaceRegistry
    from agnetwork.workspaces.preferences import PreferencesManager

    try:
        registry = WorkspaceRegistry()

        if workspace is None:
            workspace = registry.get_default_workspace()
            if workspace is None:
                typer.echo("❌ No default workspace set.", err=True)
                raise typer.Exit(1)

        context = registry.load_workspace(workspace)
        prefs_manager = PreferencesManager(context.prefs_path)
        prefs_manager.set(key, value)

        typer.echo(f"✅ Set {key} = {value} for workspace: {workspace}")

    except FileNotFoundError as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


@prefs_app.command(name="reset")
def prefs_reset(
    workspace: Optional[str] = typer.Option(
        None, "--workspace", "-w", help="Workspace name (default: current default)"
    ),
    confirm: bool = typer.Option(False, "--confirm", help="Confirm reset to defaults"),
):
    """Reset preferences to defaults for a workspace.

    Example:
        ag prefs reset --confirm
        ag prefs reset --workspace myproject --confirm
    """
    from agnetwork.workspaces import WorkspaceRegistry
    from agnetwork.workspaces.preferences import PreferencesManager

    if not confirm:
        typer.echo("❌ Must use --confirm to reset preferences", err=True)
        raise typer.Exit(1)

    try:
        registry = WorkspaceRegistry()

        if workspace is None:
            workspace = registry.get_default_workspace()
            if workspace is None:
                typer.echo("❌ No default workspace set.", err=True)
                raise typer.Exit(1)

        context = registry.load_workspace(workspace)
        prefs_manager = PreferencesManager(context.prefs_path)
        prefs_manager.reset()

        typer.echo(f"✅ Reset preferences to defaults for workspace: {workspace}")

    except FileNotFoundError as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)

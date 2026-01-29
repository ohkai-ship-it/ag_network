"""CRM integration CLI commands.

Commands for CRM data management (M6):
- crm export-run: Export a pipeline run as CRM package
- crm export-latest: Export the most recent pipeline run
- crm import: Import CRM data from files
- crm list: List CRM entities
- crm search: Search CRM entities
- crm stats: Show CRM storage statistics
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from typer import Context, Typer

from agnetwork.cli.app import app, get_workspace_context

# =============================================================================
# CRM Subcommand Group (M6)
# =============================================================================

crm_app = Typer(help="CRM integration commands (M6)")
app.add_typer(crm_app, name="crm")


@crm_app.command(name="export-run")
def crm_export_run(
    ctx: Context,
    run_id: str = typer.Argument(..., help="Run ID to export"),
    format: str = typer.Option("json", "--format", "-f", help="Output format: json or csv"),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Output directory path"),
):
    """Export a pipeline run as a CRM package.

    Creates a directory with accounts.json/csv, contacts.json/csv,
    activities.json/csv, and manifest.json.

    Examples:
        ag crm export-run 20260126_101856__testcompany__pipeline
        ag crm export-run <run_id> --format csv --out ./exports
    """
    from agnetwork.crm.adapters import CRMAdapterFactory
    from agnetwork.crm.mapping import map_run_to_crm

    ws_ctx = get_workspace_context(ctx)
    typer.echo(f"[workspace: {ws_ctx.name}]")
    typer.echo(f"📦 Exporting run: {run_id}")

    # Map run to CRM objects
    try:
        package = map_run_to_crm(run_id)
    except ValueError as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)

    # Determine output path (workspace-scoped)
    if out is None:
        out = ws_ctx.exports_dir / run_id

    typer.echo(f"📁 Output directory: {out}")

    # Export using workspace-scoped adapter
    adapter = CRMAdapterFactory.create("file", ws_ctx=ws_ctx)
    result = adapter.export_data(package, str(out), format=format)

    if result.success:
        typer.echo("✅ Export completed successfully!")
        typer.echo(f"   Accounts: {result.accounts_exported}")
        typer.echo(f"   Contacts: {result.contacts_exported}")
        typer.echo(f"   Activities: {result.activities_exported}")
        typer.echo(f"   Manifest: {result.manifest_path}")
    else:
        typer.echo("❌ Export failed!", err=True)
        for error in result.errors:
            typer.echo(f"   Error: {error}", err=True)
        raise typer.Exit(1)


@crm_app.command(name="export-latest")
def crm_export_latest(
    ctx: Context,
    format: str = typer.Option("json", "--format", "-f", help="Output format: json or csv"),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Output directory path"),
    pipeline_only: bool = typer.Option(
        True, "--pipeline-only/--all", help="Only export pipeline runs"
    ),
):
    """Export the most recent pipeline run as a CRM package.

    Examples:
        ag crm export-latest
        ag crm export-latest --format csv
        ag crm export-latest --all  # Include non-pipeline runs
    """
    ws_ctx = get_workspace_context(ctx)
    typer.echo(f"[workspace: {ws_ctx.name}]")

    # Find latest run (workspace-scoped)
    runs = sorted(Path(ws_ctx.runs_dir).glob("*"), key=lambda x: x.name, reverse=True)

    if pipeline_only:
        runs = [r for r in runs if "__pipeline" in r.name]

    if not runs:
        typer.echo("❌ No runs found", err=True)
        raise typer.Exit(1)

    latest_run = runs[0]
    run_id = latest_run.name

    typer.echo(f"📌 Latest run: {run_id}")

    # Delegate to export-run
    from agnetwork.crm.adapters import CRMAdapterFactory
    from agnetwork.crm.mapping import map_run_to_crm

    try:
        package = map_run_to_crm(run_id)
    except ValueError as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)

    # Workspace-scoped output path
    if out is None:
        out = ws_ctx.exports_dir / run_id

    typer.echo(f"📁 Output directory: {out}")

    # Workspace-scoped adapter
    adapter = CRMAdapterFactory.create("file", ws_ctx=ws_ctx)
    result = adapter.export_data(package, str(out), format=format)

    if result.success:
        typer.echo("✅ Export completed successfully!")
        typer.echo(f"   Accounts: {result.accounts_exported}")
        typer.echo(f"   Contacts: {result.contacts_exported}")
        typer.echo(f"   Activities: {result.activities_exported}")
    else:
        typer.echo("❌ Export failed!", err=True)
        for error in result.errors:
            typer.echo(f"   Error: {error}", err=True)
        raise typer.Exit(1)


@crm_app.command(name="import")
def crm_import(
    ctx: Context,
    file: Path = typer.Argument(..., help="Path to import file or directory"),
    dry_run: bool = typer.Option(
        True, "--dry-run/--no-dry-run", help="Validate without persisting (default: dry-run)"
    ),
):
    """Import CRM data from CSV/JSON files.

    Default is dry-run mode (validate only). Use --no-dry-run to persist.

    Examples:
        ag crm import ./exports/accounts.json
        ag crm import ./exports/ --no-dry-run
    """
    from agnetwork.crm.adapters import CRMAdapterFactory

    ws_ctx = get_workspace_context(ctx)
    typer.echo(f"[workspace: {ws_ctx.name}]")

    mode = "DRY RUN" if dry_run else "LIVE"
    typer.echo(f"📥 Importing from: {file} ({mode})")

    # Workspace-scoped adapter
    adapter = CRMAdapterFactory.create("file", ws_ctx=ws_ctx)
    result = adapter.import_data(str(file), dry_run=dry_run)

    if result.success:
        typer.echo("✅ Import completed successfully!")
        typer.echo(f"   Accounts: {result.accounts_imported}")
        typer.echo(f"   Contacts: {result.contacts_imported}")
        typer.echo(f"   Activities: {result.activities_imported}")

        if dry_run:
            typer.echo("\n💡 This was a dry run. Use --no-dry-run to persist.")

        for warning in result.warnings:
            typer.echo(f"   ⚠️ {warning}")
    else:
        typer.echo("❌ Import failed!", err=True)
        for error in result.errors:
            typer.echo(f"   Error: {error}", err=True)
        raise typer.Exit(1)


# =============================================================================
# CRM List Helpers (M6.3 refactored)
# =============================================================================


def _render_accounts_list(accounts: list) -> None:
    """Render accounts list to terminal."""
    typer.echo(f"\n🏢 Accounts ({len(accounts)}):")
    for acc in accounts:
        typer.echo(f"  [{acc.account_id}] {acc.name}")
        if acc.domain:
            typer.echo(f"      Domain: {acc.domain}")


def _render_contacts_list(contacts: list) -> None:
    """Render contacts list to terminal."""
    typer.echo(f"\n👤 Contacts ({len(contacts)}):")
    for con in contacts:
        typer.echo(f"  [{con.contact_id}] {con.full_name}")
        if con.role_title:
            typer.echo(f"      Title: {con.role_title}")
        if con.email:
            typer.echo(f"      Email: {con.email}")


def _render_activities_list(activities: list) -> None:
    """Render activities list to terminal."""
    typer.echo(f"\n📋 Activities ({len(activities)}):")
    for act in activities:
        status = "📅 PLANNED" if act.is_planned else "✅"
        typer.echo(f"  {status} [{act.activity_id}] {act.subject}")
        typer.echo(f"      Type: {act.activity_type.value} | {act.direction.value}")
        if act.run_id:
            typer.echo(f"      Run: {act.run_id}")


@crm_app.command(name="list")
def crm_list(
    ctx: Context,
    entity: str = typer.Argument("accounts", help="Entity type: accounts, contacts, or activities"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results"),
    account_id: Optional[str] = typer.Option(None, "--account", "-a", help="Filter by account ID"),
):
    """List CRM entities from storage.

    Examples:
        ag crm list accounts
        ag crm list contacts --account acc_testcompany
        ag crm list activities --limit 10
    """
    # Validate entity type FIRST (before creating adapter)
    valid_entities = {"accounts", "contacts", "activities"}
    if entity not in valid_entities:
        typer.echo(f"❌ Unknown entity type: {entity}", err=True)
        typer.echo("   Valid types: accounts, contacts, activities")
        raise typer.Exit(1)

    from agnetwork.crm.adapters import CRMAdapterFactory

    ws_ctx = get_workspace_context(ctx)
    typer.echo(f"[workspace: {ws_ctx.name}]")

    # Workspace-scoped adapter
    adapter = CRMAdapterFactory.create("file", ws_ctx=ws_ctx)

    # Dispatch table for entity handlers
    handlers = {
        "accounts": lambda: _render_accounts_list(adapter.list_accounts(limit=limit)),
        "contacts": lambda: _render_contacts_list(
            adapter.list_contacts(account_id=account_id, limit=limit)
        ),
        "activities": lambda: _render_activities_list(
            adapter.list_activities(account_id=account_id, limit=limit)
        ),
    }

    handlers[entity]()


@crm_app.command(name="search")
def crm_search(
    ctx: Context,
    query: str = typer.Argument(..., help="Search query"),
    entity: str = typer.Option(
        "all", "--entity", "-e", help="Entity type: accounts, contacts, or all"
    ),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum results"),
):
    """Search CRM entities.

    Examples:
        ag crm search "tech" --entity accounts
        ag crm search "VP" --entity contacts
        ag crm search "startup"
    """
    from agnetwork.crm.adapters import CRMAdapterFactory

    ws_ctx = get_workspace_context(ctx)
    typer.echo(f"[workspace: {ws_ctx.name}]")

    # Workspace-scoped adapter
    adapter = CRMAdapterFactory.create("file", ws_ctx=ws_ctx)

    if entity in ("all", "accounts"):
        accounts = adapter.search_accounts(query, limit=limit)
        typer.echo(f"\n🏢 Accounts matching '{query}' ({len(accounts)}):")
        for acc in accounts:
            typer.echo(f"  [{acc.account_id}] {acc.name}")

    if entity in ("all", "contacts"):
        contacts = adapter.search_contacts(query, limit=limit)
        typer.echo(f"\n👤 Contacts matching '{query}' ({len(contacts)}):")
        for con in contacts:
            typer.echo(f"  [{con.contact_id}] {con.full_name} - {con.role_title or 'N/A'}")


@crm_app.command(name="stats")
def crm_stats(ctx: Context):
    """Show CRM storage statistics.

    Example:
        ag crm stats
    """
    from agnetwork.crm.storage import CRMStorage

    ws_ctx = get_workspace_context(ctx)
    typer.echo(f"[workspace: {ws_ctx.name}]")

    # Workspace-scoped storage
    storage = CRMStorage.for_workspace(ws_ctx)
    stats = storage.get_stats()

    typer.echo("\n📊 CRM Storage Statistics:")
    typer.echo(f"   Accounts:   {stats['accounts']}")
    typer.echo(f"   Contacts:   {stats['contacts']}")
    typer.echo(f"   Activities: {stats['activities']}")

"""Memory management CLI commands.

Commands for memory management (M5):
- memory rebuild-index: Rebuild FTS5 search indexes
- memory search: Search stored sources and artifacts
"""

from __future__ import annotations

import typer
from typer import Context, Typer

from agnetwork.cli.app import app, get_workspace_context

# Create memory subcommand group
memory_app = Typer(help="Memory management commands (M5)")
app.add_typer(memory_app, name="memory")


@memory_app.callback()
def memory_callback():
    """Memory management subcommands."""
    pass


@memory_app.command(name="rebuild-index")
def memory_rebuild_index(
    ctx: Context,
):
    """Rebuild FTS5 search indexes from base tables.

    Use this if FTS indexes get out of sync with sources/artifacts tables.
    """
    from agnetwork.storage.sqlite import SQLiteManager

    ws_ctx = get_workspace_context(ctx)
    typer.echo(f"📂 Workspace: {ws_ctx.name}")
    typer.echo("🔧 Rebuilding FTS5 indexes...")

    db = SQLiteManager(db_path=ws_ctx.db_path, workspace_id=ws_ctx.workspace_id)
    db.rebuild_fts_index()

    typer.echo("✅ FTS5 indexes rebuilt successfully!")


@memory_app.command(name="search")
def memory_search(
    ctx: Context,
    query: str = typer.Argument(..., help="Search query"),
    sources_only: bool = typer.Option(False, "--sources", "-s", help="Search sources only"),
    artifacts_only: bool = typer.Option(False, "--artifacts", "-a", help="Search artifacts only"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum results"),
):
    """Search stored sources and artifacts using FTS5.

    Examples:
        ag memory search "machine learning"
        ag memory search "VP Sales" --artifacts
        ag memory search "cloud solutions" --sources --limit 5
    """
    from agnetwork.storage.sqlite import SQLiteManager

    ws_ctx = get_workspace_context(ctx)
    typer.echo(f"📂 Workspace: {ws_ctx.name}")
    typer.echo("🔍 [computed] Searching (FTS)...")

    db = SQLiteManager(db_path=ws_ctx.db_path, workspace_id=ws_ctx.workspace_id)

    if not artifacts_only:
        typer.echo("\n📚 Sources:")
        sources = db.search_sources_fts(query, limit=limit)
        if sources:
            for s in sources:
                title = s.get("title") or s.get("id")
                excerpt = s.get("excerpt", "")[:80]
                typer.echo(f"  [{s['id']}] {title}")
                if excerpt:
                    typer.echo(f"      {excerpt}...")
        else:
            typer.echo("  No matches found")

    if not sources_only:
        typer.echo("\n📄 Artifacts:")
        artifacts = db.search_artifacts_fts(query, limit=limit)
        if artifacts:
            for a in artifacts:
                typer.echo(f"  [{a['id']}] {a.get('name', '')} ({a.get('artifact_type', '')})")
                excerpt = a.get("excerpt", "")[:80]
                if excerpt:
                    typer.echo(f"      {excerpt}...")
        else:
            typer.echo("  No matches found")

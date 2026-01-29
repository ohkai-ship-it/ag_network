"""Sequence CLI commands.

Commands for outreach sequence management (M6):
- sequence plan: Generate sequence plan from pipeline run
- sequence list-templates: List available templates
- sequence show-template: Show template details
- sequence templates: [Deprecated] Show built-in templates
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from typer import Context, Typer

from agnetwork.cli.app import app, get_workspace_context

# =============================================================================
# Sequence Subcommand Group (M6)
# =============================================================================

sequence_app = Typer(help="Outreach sequence commands (M6)")
app.add_typer(sequence_app, name="sequence")


@sequence_app.command(name="plan")
def sequence_plan(
    ctx: Context,
    run_id: str = typer.Argument(..., help="Run ID to build sequence from"),
    channel: str = typer.Option("email", "--channel", "-c", help="Channel: email or linkedin"),
    start_date: Optional[str] = typer.Option(
        None, "--start", "-s", help="Start date (YYYY-MM-DD, defaults to today)"
    ),
    out: Optional[Path] = typer.Option(
        None, "--out", "-o", help="Output directory for sequence export"
    ),
):
    """Generate an outreach sequence plan from a pipeline run.

    Creates planned activities with scheduled dates based on
    the outreach artifact's sequence_steps.

    Examples:
        ag sequence plan <run_id>
        ag sequence plan <run_id> --channel linkedin
        ag sequence plan <run_id> --start 2026-02-01 --out ./sequences
    """
    from agnetwork.crm.models import CRMExportManifest, CRMExportPackage
    from agnetwork.crm.sequence import SequenceBuilder

    ws_ctx = get_workspace_context(ctx)
    typer.echo(f"📂 Workspace: {ws_ctx.name}")
    typer.echo(f"📋 Building sequence plan for run: {run_id}")

    # Load run data from workspace runs_dir
    run_dir = ws_ctx.runs_dir / run_id
    if not run_dir.exists():
        typer.echo(f"❌ Run not found: {run_id}", err=True)
        raise typer.Exit(1)

    # Load outreach artifact
    outreach_file = run_dir / "artifacts" / "outreach.json"
    if not outreach_file.exists():
        typer.echo("❌ No outreach artifact found in run", err=True)
        raise typer.Exit(1)

    with open(outreach_file, "r", encoding="utf-8") as f:
        outreach = json.load(f)

    # Override channel if specified
    if channel:
        outreach["channel"] = channel

    # Parse start date
    seq_start = datetime.now(timezone.utc)
    if start_date:
        try:
            seq_start = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
        except ValueError:
            typer.echo(f"❌ Invalid date format: {start_date}", err=True)
            raise typer.Exit(1)

    # Build sequence
    company = outreach.get("company", "Unknown")
    account_id = f"acc_{company.lower().replace(' ', '_')}"
    contact_id = f"con_{account_id}_primary"

    builder = SequenceBuilder(mode="manual")
    sequence = builder.build_from_outreach(
        outreach_artifact=outreach,
        account_id=account_id,
        contact_id=contact_id,
        run_id=run_id,
        start_date=seq_start,
    )

    typer.echo(f"✅ Sequence plan created: {sequence.name}")
    typer.echo(f"   Company: {sequence.company}")
    typer.echo(f"   Channel: {sequence.channel}")
    typer.echo(f"   Steps: {len(sequence.steps)}")

    # Display steps
    typer.echo("\n📅 Sequence Steps:")
    for step in sequence.steps:
        scheduled = sequence.get_scheduled_date(step)
        typer.echo(f"   Day {step.day_offset}: {step.notes}")
        typer.echo(f"      Scheduled: {scheduled.strftime('%Y-%m-%d')}")

    # Convert to activities
    activities = sequence.to_activities()
    typer.echo(f"\n📋 Generated {len(activities)} planned activities")

    # Export if output path specified
    if out:
        manifest = CRMExportManifest(
            export_id=f"seq_{sequence.sequence_id}",
            crm_export_version="1.0",
            run_id=run_id,
            company=company,
            account_count=0,
            contact_count=0,
            activity_count=len(activities),
            files=["manifest.json", "activities.json"],
        )

        package = CRMExportPackage(
            manifest=manifest,
            accounts=[],
            contacts=[],
            activities=activities,
        )

        from agnetwork.crm.adapters import CRMAdapterFactory

        adapter = CRMAdapterFactory.from_env()
        result = adapter.export_data(package, str(out), format="json")

        if result.success:
            typer.echo(f"\n✅ Sequence exported to: {out}")
        else:
            typer.echo(f"❌ Export failed: {result.errors}", err=True)


@sequence_app.command(name="list-templates")
def sequence_list_templates():
    """List available sequence templates (M6.1).

    Templates are loaded from JSON file and can be edited without code changes.

    Example:
        ag sequence list-templates
    """
    from agnetwork.crm.sequence import get_template_loader

    loader = get_template_loader()
    templates = loader.list_templates()

    if not templates:
        typer.echo("⚠️ No templates found in JSON file, using built-in defaults.")
        typer.echo("\n📋 Built-in Templates:")
        typer.echo("  - email (Standard 4-step email sequence)")
        typer.echo("  - linkedin (3-step LinkedIn sequence)")
        return

    typer.echo(f"\n📋 Available Templates ({len(templates)}):")
    for name in sorted(templates):
        template = loader.get_template(name)
        if template:
            desc = template.get("description", "No description")
            channel = template.get("channel", "email")
            steps = len(template.get("steps", []))
            typer.echo(f"\n  {name}")
            typer.echo(f"    Channel: {channel}")
            typer.echo(f"    Steps: {steps}")
            typer.echo(f"    {desc}")


@sequence_app.command(name="show-template")
def sequence_show_template(
    name: str = typer.Argument(..., help="Template name to show"),
):
    """Show details of a specific sequence template (M6.1).

    Example:
        ag sequence show-template email_standard
        ag sequence show-template linkedin_connection
    """
    from agnetwork.crm.sequence import get_template_loader

    loader = get_template_loader()
    template = loader.get_template(name)

    if not template:
        typer.echo(f"❌ Template '{name}' not found.", err=True)
        typer.echo("\nAvailable templates:")
        for t in loader.list_templates():
            typer.echo(f"  - {t}")
        raise typer.Exit(1)

    typer.echo(f"\n📋 Template: {template.get('name', name)}")
    typer.echo(f"Channel: {template.get('channel', 'email')}")
    typer.echo(f"Description: {template.get('description', 'N/A')}")
    typer.echo("\n📅 Steps:")

    for step in template.get("steps", []):
        typer.echo(f"\n  Step {step['step_number']} (Day {step['offset_days']})")
        typer.echo(f"    Style: {step.get('message_style', 'N/A')}")
        typer.echo(f"    Subject: {step['subject_pattern']}")
        typer.echo(f"    Notes: {step.get('notes', 'N/A')}")


@sequence_app.command(name="templates")
def sequence_templates():
    """[Deprecated] Use 'list-templates' instead.

    Example:
        ag sequence templates
    """
    from agnetwork.crm.sequence import DEFAULT_SEQUENCE_STEPS, LINKEDIN_SEQUENCE_STEPS

    typer.echo("⚠️ This command is deprecated. Use 'ag sequence list-templates' instead.\n")

    typer.echo("📧 Built-in Email Sequence Template:")
    for step in DEFAULT_SEQUENCE_STEPS:
        typer.echo(f"   Step {step.step_number} (Day {step.day_offset}): {step.notes}")

    typer.echo("\n💼 Built-in LinkedIn Sequence Template:")
    for step in LINKEDIN_SEQUENCE_STEPS:
        typer.echo(f"   Step {step.step_number} (Day {step.day_offset}): {step.notes}")

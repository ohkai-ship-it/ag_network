"""Work ops and personal ops skill commands.

Commands for work operations (M7.1):
- meeting-summary: Generate meeting summaries
- status-update: Generate status update reports
- decision-log: Generate ADR-style decision logs

Commands for personal operations (M7.1):
- weekly-plan: Generate weekly plans
- errand-list: Generate organized errand lists
- travel-outline: Generate travel itinerary outlines
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import typer
from typer import Context

from agnetwork.cli.app import app, get_workspace_context
from agnetwork.orchestrator import RunManager

# ============================================================================
# Work Ops Skill Helpers
# ============================================================================


def _finalize_skill_run(run, result) -> None:
    """Persist artifacts and run verification on a skill result.

    Args:
        run: RunManager instance
        result: SkillResult from skill execution
    """
    from agnetwork.eval.verifier import Verifier

    # Write artifacts
    for artifact in result.artifacts:
        artifact_path = run.run_dir / "artifacts" / artifact.filename
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        with open(artifact_path, "w", encoding="utf-8") as f:
            f.write(artifact.content)
        typer.echo(f"   📄 {artifact.filename}")

    # Run verifier
    verifier = Verifier()
    issues = verifier.verify_skill_result(result)
    if issues:
        typer.echo("⚠️ Verification issues:")
        for issue in issues:
            typer.echo(f"   - [{issue.severity}] {issue.message}")


def _run_skill_command(
    ctx: Context,
    skill_name: str,
    inputs: dict,
    command_name: str,
    slug: str,
) -> None:
    """Execute a skill through the kernel and save artifacts.

    Args:
        ctx: Typer context
        skill_name: Name of the registered skill
        inputs: Input dictionary for the skill
        command_name: Command name for the run folder
        slug: Slug for the run folder
    """
    from agnetwork.kernel import SkillContext, skill_registry

    ws_ctx = get_workspace_context(ctx)
    typer.echo(f"📂 Workspace: {ws_ctx.name}")

    # Create run manager
    run = RunManager(command=command_name, slug=slug, workspace=ws_ctx)
    typer.echo(f"📁 Run folder: {run.run_dir}")

    # Get skill instance
    skill = skill_registry.get(skill_name)
    if skill is None:
        typer.echo(f"❌ Skill not found: {skill_name}", err=True)
        raise typer.Exit(1)

    # Create skill context
    skill_ctx = SkillContext(
        run_id=run.run_id,
        workspace=ws_ctx.name,
    )

    try:
        result = skill.run(inputs, skill_ctx)

        if result.has_errors():
            typer.echo("❌ Skill execution failed", err=True)
            for warning in result.warnings:
                typer.echo(f"   ⚠️ {warning}")
            raise typer.Exit(1)

        _finalize_skill_run(run, result)
        typer.echo("✅ Done!")

    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


# ============================================================================
# Work Ops Skill Commands (M7.1)
# ============================================================================


@app.command(name="meeting-summary")
def meeting_summary(
    ctx: Context,
    topic: str = typer.Option(..., "--topic", "-t", help="Meeting topic"),
    notes: str = typer.Option(..., "--notes", "-n", help="Meeting notes (text or file path)"),
    date: Optional[str] = typer.Option(
        None, "--date", "-d", help="Meeting date (YYYY-MM-DD, defaults to today)"
    ),
    attendees: str = typer.Option(
        "N/A", "--attendees", "-a", help="Comma-separated list of attendees"
    ),
):
    """Generate a meeting summary from notes.

    Examples:
        ag meeting-summary --topic "Q1 Planning" --notes "- Discussed budget..."
        ag meeting-summary --topic "Standup" --notes notes.txt --attendees "Alice, Bob"
    """
    typer.echo(f"📝 Creating meeting summary: {topic}")

    # Handle notes as file or text
    notes_path = Path(notes)
    if notes_path.exists():
        notes_content = notes_path.read_text(encoding="utf-8")
        typer.echo(f"   📄 Loaded notes from: {notes_path}")
    else:
        notes_content = notes

    # Set date
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    inputs = {
        "topic": topic,
        "notes": notes_content,
        "date": date,
        "attendees": attendees,
    }

    _run_skill_command(
        ctx=ctx,
        skill_name="meeting_summary",
        inputs=inputs,
        command_name="meeting_summary",
        slug=topic.lower().replace(" ", "_")[:20],
    )


@app.command(name="status-update")
def status_update(
    ctx: Context,
    accomplishments: Optional[List[str]] = typer.Option(
        None, "--accomplishment", "-a", help="Accomplishment (can be repeated)"
    ),
    in_progress: Optional[List[str]] = typer.Option(
        None, "--in-progress", "-i", help="In-progress item (can be repeated)"
    ),
    blockers: Optional[List[str]] = typer.Option(
        None, "--blocker", "-b", help="Blocker (can be repeated)"
    ),
    next_week: Optional[List[str]] = typer.Option(
        None, "--next", "-n", help="Next week priority (can be repeated)"
    ),
    period: str = typer.Option("This Week", "--period", "-p", help="Report period"),
    author: str = typer.Option("Team Member", "--author", help="Report author"),
):
    """Generate a status update report.

    Examples:
        ag status-update --accomplishment "Completed M7" --in-progress "Testing"
        ag status-update -a "Shipped feature" -a "Fixed bug" -n "Release prep"
    """
    typer.echo(f"📊 Creating status update: {period}")

    inputs = {
        "period": period,
        "author": author,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "accomplishments": accomplishments or [],
        "in_progress": in_progress or [],
        "blockers": blockers or [],
        "next_week": next_week or [],
    }

    _run_skill_command(
        ctx=ctx,
        skill_name="status_update",
        inputs=inputs,
        command_name="status_update",
        slug=period.lower().replace(" ", "_")[:20],
    )


@app.command(name="decision-log")
def decision_log(
    ctx: Context,
    title: str = typer.Option(..., "--title", "-t", help="Decision title"),
    context_text: str = typer.Option(
        ..., "--context", "-c", help="Context/background for the decision"
    ),
    decision: str = typer.Option(..., "--decision", "-d", help="The decision made"),
    options: Optional[List[str]] = typer.Option(
        None, "--option", "-o", help="Option considered (format: 'name: description')"
    ),
    consequences: Optional[List[str]] = typer.Option(
        None, "--consequence", help="Consequence of the decision"
    ),
    decision_makers: str = typer.Option("Team", "--decision-makers", help="Who made the decision"),
    status: str = typer.Option(
        "Accepted", "--status", "-s", help="Status: Proposed, Accepted, Deprecated"
    ),
):
    """Generate an ADR-style decision log.

    Examples:
        ag decision-log --title "Use PostgreSQL" --context "Need a database" \\
            --decision "PostgreSQL for reliability" --option "PostgreSQL: Mature RDBMS"
    """
    typer.echo(f"📋 Creating decision log: {title}")

    # Parse options into structured format
    parsed_options = []
    for opt in options or []:
        if ": " in opt:
            name, desc = opt.split(": ", 1)
            parsed_options.append(
                {
                    "name": name,
                    "description": desc,
                    "pros": [],
                    "cons": [],
                }
            )
        else:
            parsed_options.append(
                {
                    "name": opt,
                    "description": "",
                    "pros": [],
                    "cons": [],
                }
            )

    inputs = {
        "title": title,
        "context": context_text,
        "decision": decision,
        "options": parsed_options,
        "consequences": consequences or [],
        "decision_makers": decision_makers,
        "status": status,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }

    _run_skill_command(
        ctx=ctx,
        skill_name="decision_log",
        inputs=inputs,
        command_name="decision_log",
        slug=title.lower().replace(" ", "_")[:20],
    )


# ============================================================================
# Personal Ops Skill Commands (M7.1)
# ============================================================================


@app.command(name="weekly-plan")
def weekly_plan(
    ctx: Context,
    goals: Optional[List[str]] = typer.Option(
        None, "--goal", "-g", help="Weekly goal (can be repeated)"
    ),
    monday: Optional[List[str]] = typer.Option(
        None, "--monday", help="Monday task (can be repeated)"
    ),
    tuesday: Optional[List[str]] = typer.Option(
        None, "--tuesday", help="Tuesday task (can be repeated)"
    ),
    wednesday: Optional[List[str]] = typer.Option(
        None, "--wednesday", help="Wednesday task (can be repeated)"
    ),
    thursday: Optional[List[str]] = typer.Option(
        None, "--thursday", help="Thursday task (can be repeated)"
    ),
    friday: Optional[List[str]] = typer.Option(
        None, "--friday", help="Friday task (can be repeated)"
    ),
    notes: Optional[List[str]] = typer.Option(
        None, "--note", "-n", help="Note/reminder (can be repeated)"
    ),
    week_of: Optional[str] = typer.Option(
        None, "--week-of", "-w", help="Week start date (YYYY-MM-DD)"
    ),
):
    """Generate a weekly plan.

    Examples:
        ag weekly-plan --goal "Exercise 3x" --goal "Complete project"
        ag weekly-plan --monday "Team standup" --wednesday "Review meeting"
    """
    typer.echo("📅 Creating weekly plan...")

    if week_of is None:
        week_of = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    daily_tasks = {}
    if monday:
        daily_tasks["Monday"] = monday
    if tuesday:
        daily_tasks["Tuesday"] = tuesday
    if wednesday:
        daily_tasks["Wednesday"] = wednesday
    if thursday:
        daily_tasks["Thursday"] = thursday
    if friday:
        daily_tasks["Friday"] = friday

    inputs = {
        "week_of": week_of,
        "goals": goals or [],
        "daily_tasks": daily_tasks,
        "notes": notes or [],
    }

    _run_skill_command(
        ctx=ctx,
        skill_name="weekly_plan",
        inputs=inputs,
        command_name="weekly_plan",
        slug=f"week_{week_of}",
    )


@app.command(name="errand-list")
def errand_list(
    ctx: Context,
    errands: Optional[List[str]] = typer.Option(
        None, "--errand", "-e", help="Errand (can be repeated)"
    ),
    locations: Optional[List[str]] = typer.Option(
        None, "--location", "-l", help="Location for errands (format: 'location: task')"
    ),
    date: Optional[str] = typer.Option(None, "--date", "-d", help="Date for errands (YYYY-MM-DD)"),
):
    """Generate an organized errand list.

    Examples:
        ag errand-list --errand "Buy groceries" --errand "Pick up dry cleaning"
        ag errand-list --location "Grocery: Milk, Bread" --location "Post Office: Mail package"
    """
    typer.echo("📋 Creating errand list...")

    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Parse errands into structured format
    parsed_errands = []

    # Simple errands (no location)
    for errand in errands or []:
        parsed_errands.append(
            {
                "task": errand,
                "location": "General",
                "priority": "normal",
                "notes": None,
            }
        )

    # Location-based errands
    for loc in locations or []:
        if ": " in loc:
            location, task = loc.split(": ", 1)
            parsed_errands.append(
                {
                    "task": task,
                    "location": location,
                    "priority": "normal",
                    "notes": None,
                }
            )
        else:
            parsed_errands.append(
                {
                    "task": loc,
                    "location": "General",
                    "priority": "normal",
                    "notes": None,
                }
            )

    inputs = {
        "date": date,
        "errands": parsed_errands,
    }

    _run_skill_command(
        ctx=ctx,
        skill_name="errand_list",
        inputs=inputs,
        command_name="errand_list",
        slug=f"errands_{date}",
    )


@app.command(name="travel-outline")
def travel_outline(
    ctx: Context,
    destination: str = typer.Option(..., "--destination", "-d", help="Travel destination"),
    start_date: str = typer.Option(..., "--start", "-s", help="Start date (YYYY-MM-DD)"),
    end_date: str = typer.Option(..., "--end", "-e", help="End date (YYYY-MM-DD)"),
    accommodation: Optional[str] = typer.Option(
        None, "--accommodation", "-a", help="Accommodation details"
    ),
    activities: Optional[List[str]] = typer.Option(
        None, "--activity", help="Activity for itinerary (can be repeated)"
    ),
    packing: Optional[List[str]] = typer.Option(
        None, "--packing", "-p", help="Packing list item (can be repeated)"
    ),
    notes: Optional[List[str]] = typer.Option(
        None, "--note", "-n", help="Important note (can be repeated)"
    ),
):
    """Generate a travel itinerary outline.

    Examples:
        ag travel-outline --destination Paris --start 2026-02-10 --end 2026-02-17
        ag travel-outline -d "New York" -s 2026-03-01 -e 2026-03-05 --activity "Visit Times Square"
    """
    typer.echo(f"✈️ Creating travel outline: {destination}")

    # Build simple itinerary
    itinerary = []
    if activities:
        # Put all activities on day 1 for simplicity
        itinerary.append(
            {
                "date": start_date,
                "activities": activities,
            }
        )

    inputs = {
        "destination": destination,
        "start_date": start_date,
        "end_date": end_date,
        "accommodation": accommodation or "",
        "itinerary": itinerary,
        "packing_list": packing or [],
        "notes": notes or [],
    }

    _run_skill_command(
        ctx=ctx,
        skill_name="travel_outline",
        inputs=inputs,
        command_name="travel_outline",
        slug=destination.lower().replace(" ", "_")[:20],
    )

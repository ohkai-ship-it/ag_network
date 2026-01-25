"""CLI entry point for BD Copilot."""

import json
from pathlib import Path
from typing import List, Optional

import typer
from typer import Typer

from bdcopilot.config import config
from bdcopilot.orchestrator import RunManager
from bdcopilot.skills.research_brief import ResearchBriefSkill
from bdcopilot.tools.ingest import SourceIngestor

# Initialize Typer app
app = Typer(
    name="bd",
    help="BD Copilot: Autonomous business development workflow assistant",
)


@app.callback()
def init_app():
    """Initialize the application."""
    config.ensure_directories()


@app.command()
def research(
    company: str = typer.Argument(..., help="Company name to research"),
    snapshot: str = typer.Option(
        ..., "--snapshot", "-s", help="Company snapshot/description"
    ),
    pains: Optional[List[str]] = typer.Option(
        None, "--pain", "-p", help="Key pains (can be repeated)"
    ),
    triggers: Optional[List[str]] = typer.Option(
        None, "--trigger", "-t", help="Triggers (can be repeated)"
    ),
    competitors: Optional[List[str]] = typer.Option(
        None, "--competitor", "-c", help="Competitors (can be repeated)"
    ),
    sources_file: Optional[Path] = typer.Option(
        None, "--sources", "-f", help="JSON file with sources"
    ),
):
    """Research a company and generate account research brief."""
    typer.echo(f"🔍 Researching {company}...")

    # Create run manager
    run = RunManager(command="research", slug=company.lower().replace(" ", "_"))
    typer.echo(f"📁 Run folder: {run.run_dir}")

    try:
        # Log start
        run.log_action(
            phase="1",
            action=f"Start research for {company}",
            status="success",
            next_action="Ingest sources",
        )

        # Initialize source ingestor
        ingestor = SourceIngestor(run.run_dir)

        # Load sources if provided
        if sources_file and sources_file.exists():
            with open(sources_file, "r") as f:
                sources_data = json.load(f)
            for source in sources_data.get("sources", []):
                if source.get("type") == "text":
                    ingestor.ingest_text(
                        content=source["content"],
                        title=source.get("title"),
                        company=company,
                    )
            typer.echo(f"✅ Loaded {len(ingestor.ingested_sources)} sources")

        # Prepare input data
        inputs = {
            "company": company,
            "snapshot": snapshot,
            "pains": pains or [],
            "triggers": triggers or [],
            "competitors": competitors or [],
            "sources_ingested": len(ingestor.ingested_sources),
        }
        run.save_inputs(inputs)

        # Generate research brief
        run.log_action(
            phase="2",
            action="Generate research brief",
            status="success",
            next_action="Create artifacts",
        )

        skill = ResearchBriefSkill()

        # Prepare personalization angles
        angles = [
            {
                "name": "Market Expansion",
                "fact": f"{company} is expanding into new markets",
                "is_assumption": True,
            },
            {
                "name": "Cost Optimization",
                "fact": f"{company} seeks to optimize operational costs",
                "is_assumption": True,
            },
            {
                "name": "Digital Transformation",
                "fact": f"{company} is undergoing digital transformation",
                "is_assumption": True,
            },
        ]

        markdown, json_data = skill.generate(
            company=company,
            snapshot=snapshot,
            pains=pains or [],
            triggers=triggers or [],
            competitors=competitors or [],
            personalization_angles=angles,
        )

        # Save artifacts
        run.save_artifact("research_brief", markdown, json_data)

        # Update status
        run.update_status(
            current_phase="2",
            phases_completed=["0", "1"],
            phases_in_progress=["2"],
        )

        typer.echo("✅ Research brief generated successfully!")
        typer.echo(f"📄 Artifacts saved to: {run.run_dir / 'artifacts'}")

        run.log_action(
            phase="2",
            action="Complete research command",
            status="success",
            changes_made=[
                str(run.run_dir / "artifacts" / "research_brief.md"),
                str(run.run_dir / "artifacts" / "research_brief.json"),
            ],
        )

    except Exception as e:
        run.log_action(
            phase="2",
            action="Research generation failed",
            status="failure",
            issues_discovered=[str(e)],
        )
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def targets(
    company: str = typer.Argument(..., help="Company name"),
    persona: Optional[str] = typer.Option(
        None, "--persona", "-p", help="Target persona"
    ),
):
    """Generate prospect target map for a company."""
    typer.echo(f"🎯 Creating target map for {company}...")
    run = RunManager(command="targets", slug=company.lower().replace(" ", "_"))

    run.log_action(
        phase="1",
        action=f"Start targets command for {company}",
        status="success",
    )

    # Placeholder implementation
    targets_data = {
        "company": company,
        "personas": [
            {"title": "VP Sales", "role": "economic_buyer", "hypothesis": "Controls budget"},
            {"title": "Sales Manager", "role": "champion", "hypothesis": "Advocates internally"},
            {"title": "IT Director", "role": "blocker", "hypothesis": "Has technical concerns"},
        ],
    }

    markdown = f"# Target Map: {company}\n\n## Personas\n"
    for p in targets_data["personas"]:
        markdown += f"- **{p['title']}** ({p['role']}): {p['hypothesis']}\n"

    run.save_artifact("target_map", markdown, targets_data)
    typer.echo("✅ Target map created")


@app.command()
def outreach(
    company: str = typer.Argument(..., help="Company name"),
    persona: str = typer.Option(..., "--persona", "-p", help="Target persona"),
    channel: str = typer.Option(
        "email", "--channel", "-c", help="Channel: email or linkedin"
    ),
):
    """Generate outreach message drafts."""
    typer.echo(f"📧 Creating outreach for {company} ({persona}) via {channel}...")
    run = RunManager(command="outreach", slug=company.lower().replace(" ", "_"))

    run.log_action(
        phase="1",
        action=f"Start outreach command for {company}",
        status="success",
    )

    # Placeholder implementation
    if channel == "email":
        subject = f"Partnership opportunity with {company}"
        body = f"Hi {persona},\n\nI'd like to explore a partnership..."
    else:
        subject = f"Connection request - {company} partnership"
        body = f"Hi {persona}, saw your profile and would love to connect..."

    outreach_data = {
        "company": company,
        "persona": persona,
        "channel": channel,
        "subject_or_hook": subject,
        "body": body,
    }

    markdown = f"# Outreach: {company}\n\n## {channel.title()}\n\n**Subject/Hook**: {subject}\n\n**Body**:\n{body}"

    run.save_artifact("outreach", markdown, outreach_data)
    typer.echo("✅ Outreach drafts created")


@app.command()
def prep(
    company: str = typer.Argument(..., help="Company name"),
    meeting_type: str = typer.Option(
        "discovery", "--type", "-t", help="Meeting type: discovery, demo, negotiation"
    ),
):
    """Generate meeting preparation pack."""
    typer.echo(f"📋 Preparing for {meeting_type} meeting with {company}...")
    run = RunManager(command="prep", slug=company.lower().replace(" ", "_"))

    run.log_action(
        phase="1",
        action=f"Start prep command for {company}",
        status="success",
    )

    # Placeholder implementation
    prep_data = {
        "company": company,
        "meeting_type": meeting_type,
        "agenda": ["Introductions (5 min)", "Problem discovery (15 min)", "Solution overview (10 min)"],
        "questions": ["What are your current challenges?", "How are you currently solving this?"],
        "stakeholder_map": {"VP Sales": "Economic buyer"},
    }

    markdown = f"# Meeting Prep: {company}\n\n## Agenda\n"
    for item in prep_data["agenda"]:
        markdown += f"- {item}\n"

    run.save_artifact("meeting_prep", markdown, prep_data)
    typer.echo("✅ Meeting prep pack created")


@app.command()
def followup(
    company: str = typer.Argument(..., help="Company name"),
    notes: str = typer.Option(
        ..., "--notes", "-n", help="Meeting notes or file path"
    ),
):
    """Generate post-meeting follow-up."""
    typer.echo(f"📝 Creating follow-up for {company}...")
    run = RunManager(command="followup", slug=company.lower().replace(" ", "_"))

    run.log_action(
        phase="1",
        action=f"Start followup command for {company}",
        status="success",
    )

    # Placeholder implementation
    followup_data = {
        "company": company,
        "summary": "Good initial conversation, strong interest in solution",
        "next_steps": ["Send proposal", "Schedule demo", "Follow up in 1 week"],
        "tasks": [{"task": "Send proposal", "owner": "sales", "due": "2 days"}],
    }

    markdown = f"# Follow-up: {company}\n\n## Summary\n{followup_data['summary']}\n\n## Next Steps\n"
    for step in followup_data["next_steps"]:
        markdown += f"- {step}\n"

    run.save_artifact("followup", markdown, followup_data)
    typer.echo("✅ Follow-up created")


@app.command()
def status():
    """Show status of recent runs."""
    typer.echo("📊 Recent runs:")
    runs = sorted(config.runs_dir.glob("*"), key=lambda x: x.name, reverse=True)
    for run in runs[:5]:
        status_file = run / "logs" / "agent_status.json"
        if status_file.exists():
            with open(status_file, "r") as f:
                status_data = json.load(f)
            typer.echo(f"  {run.name}: {status_data.get('current_phase', '?')}")


if __name__ == "__main__":
    app()

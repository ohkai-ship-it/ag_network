"""Research-related CLI commands.

Commands for company research and account intelligence:
- research: Generate account research brief
- targets: Generate prospect target map
- outreach: Generate outreach message drafts
- prep: Generate meeting preparation pack
- followup: Generate post-meeting follow-up
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

import typer
from typer import Context

from agnetwork.cli.app import app, get_workspace_context
from agnetwork.orchestrator import RunManager
from agnetwork.skills.research_brief import ResearchBriefSkill
from agnetwork.tools.ingest import SourceIngestor

if TYPE_CHECKING:
    pass


def _discover_and_fetch_deep_links(
    url: str,
    raw_path: Path,
    run_dir: Path,
    deep_links_max: int,
    deep_links_mode: str,
    capture,
    db,
    run_id: str,
) -> list:
    """M8: Discover and fetch deep links from a homepage.

    Returns list of successfully captured deep link results.
    """
    from agnetwork.tools.web.deeplinks import (
        DeepLinksConfig,
        discover_deep_links,
        is_homepage_url,
    )

    if not is_homepage_url(url):
        return []

    if not raw_path.exists():
        return []

    typer.echo("   🔗 Discovering deep links...")
    raw_html = raw_path.read_bytes()

    # Configure deep links
    dl_config = DeepLinksConfig.load_default()
    dl_config.max_total = deep_links_max

    # Setup LLM if agent mode
    llm = None
    use_agent = deep_links_mode == "agent"
    if use_agent:
        try:
            from agnetwork.tools.llm import LLMFactory

            llm_factory = LLMFactory.from_env()
            if llm_factory.is_enabled:
                llm = llm_factory.get_default_adapter()
            else:
                typer.echo("   ⚠️ LLM not enabled, using deterministic mode")
                use_agent = False
        except Exception as e:
            typer.echo(f"   ⚠️ LLM setup failed: {e}, using deterministic mode")
            use_agent = False

    # Discover deep links
    selections, audit = discover_deep_links(
        url,
        raw_html,
        config=dl_config,
        use_agent=use_agent,
        llm=llm,
    )

    # Save audit artifact
    audit.save(run_dir / "sources" / "deeplinks.json")

    # Fetch selected deep links
    captured = []
    for sel in selections:
        typer.echo(f"      [fetched] {sel.url[:50]}... ({sel.category})")
        dl_result = capture.capture_url(sel.url)
        if dl_result.is_success:
            cache_label = " [cached]" if dl_result.is_cached else ""
            typer.echo(f"      ✅{cache_label} {dl_result.title or 'No title'}")
            db.upsert_source_from_capture(
                source_id=dl_result.source_id,
                url=dl_result.url,
                final_url=dl_result.final_url,
                title=dl_result.title,
                clean_text=dl_result.clean_text,
                content_hash=dl_result.content_hash,
                fetched_at=dl_result.fetched_at.isoformat(),
                run_id=run_id,
            )
            captured.append(dl_result)
        else:
            typer.echo(f"      ❌ Failed: {dl_result.error}", err=True)

    typer.echo(f"   🔗 Deep links: {len(selections)} selected ({audit.selection_method})")
    return captured


@app.command()
def research(
    ctx: Context,
    company: str = typer.Argument(..., help="Company name to research"),
    snapshot: str = typer.Option(..., "--snapshot", "-s", help="Company snapshot/description"),
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
    urls: Optional[List[str]] = typer.Option(
        None, "--url", "-u", help="URLs to fetch and use as sources (can be repeated)"
    ),
    use_memory: bool = typer.Option(
        False, "--use-memory/--no-memory", help="Enable memory retrieval (M5)"
    ),
    deep_links: bool = typer.Option(
        False, "--deep-links/--no-deep-links", help="Enable deep link discovery (M8)"
    ),
    deep_links_mode: str = typer.Option(
        "deterministic",
        "--deep-links-mode",
        help="Deep link selection mode: deterministic or agent",
    ),
    deep_links_max: int = typer.Option(4, "--deep-links-max", help="Maximum deep links to fetch"),
):
    """Research a company and generate account research brief."""
    ws_ctx = get_workspace_context(ctx)

    typer.echo(f"🔍 [computed] Starting research run for {company}...")
    typer.echo(f"📂 Workspace: {ws_ctx.name}")

    # Create run manager with workspace context
    run = RunManager(command="research", slug=company.lower().replace(" ", "_"), workspace=ws_ctx)
    typer.echo(f"📁 Run folder: {run.run_dir}")

    try:
        # Log start
        run.log_action(
            phase="1",
            action=f"Start research for {company}",
            status="success",
            next_action="Ingest sources",
        )

        # Initialize source ingestor with workspace context
        ingestor = SourceIngestor(run.run_dir, ws_ctx)
        captured_sources = []

        # Fetch URLs if provided (M5)
        if urls:
            typer.echo(f"🌐 [fetched] Fetching {len(urls)} URLs...")
            from agnetwork.storage.sqlite import SQLiteManager
            from agnetwork.tools.web import SourceCapture

            capture = SourceCapture(run.run_dir / "sources")
            db = SQLiteManager.for_workspace(ws_ctx)

            for url in urls:
                typer.echo(f"   [fetched] {url[:60]}...")
                result = capture.capture_url(url)
                if result.is_success:
                    cache_label = " [cached]" if result.is_cached else ""
                    typer.echo(f"   ✅{cache_label} {result.title or 'No title'}")
                    # Upsert to database
                    db.upsert_source_from_capture(
                        source_id=result.source_id,
                        url=result.url,
                        final_url=result.final_url,
                        title=result.title,
                        clean_text=result.clean_text,
                        content_hash=result.content_hash,
                        fetched_at=result.fetched_at.isoformat(),
                        run_id=run.run_id,
                    )
                    captured_sources.append(result)

                    # M8: Deep link discovery if enabled and this looks like a homepage
                    if deep_links and result.raw_path:
                        dl_captured = _discover_and_fetch_deep_links(
                            url=url,
                            raw_path=run.run_dir / result.raw_path,
                            run_dir=run.run_dir,
                            deep_links_max=deep_links_max,
                            deep_links_mode=deep_links_mode,
                            capture=capture,
                            db=db,
                            run_id=run.run_id,
                        )
                        captured_sources.extend(dl_captured)
                else:
                    typer.echo(f"   ❌ Failed: {result.error}", err=True)

            typer.echo(f"✅ Captured {len(captured_sources)} URLs")

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
            "urls_fetched": [s.url for s in captured_sources],
            "source_ids": [s.source_id for s in captured_sources],
            "use_memory": use_memory,
            "deep_links_enabled": deep_links,
            "deep_links_mode": deep_links_mode if deep_links else None,
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
    ctx: Context,
    company: str = typer.Argument(..., help="Company name"),
    persona: Optional[str] = typer.Option(None, "--persona", "-p", help="Target persona"),
):
    """Generate prospect target map for a company."""
    ws_ctx = get_workspace_context(ctx)
    typer.echo(f"🎯 Creating target map for {company}...")
    typer.echo(f"📂 Workspace: {ws_ctx.name}")
    run = RunManager(command="targets", slug=company.lower().replace(" ", "_"), workspace=ws_ctx)

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
    ctx: Context,
    company: str = typer.Argument(..., help="Company name"),
    persona: str = typer.Option(..., "--persona", "-p", help="Target persona"),
    channel: str = typer.Option("email", "--channel", "-c", help="Channel: email or linkedin"),
):
    """Generate outreach message drafts."""
    ws_ctx = get_workspace_context(ctx)
    typer.echo(f"📧 [placeholder] Creating outreach for {company} ({persona}) via {channel}...")
    typer.echo(f"📂 Workspace: {ws_ctx.name}")
    run = RunManager(command="outreach", slug=company.lower().replace(" ", "_"), workspace=ws_ctx)

    run.log_action(
        phase="1",
        action=f"Start outreach command for {company}",
        status="success",
    )

    # Placeholder implementation (not using LLM)
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
    typer.echo("✅ [placeholder] Outreach drafts created")


@app.command()
def prep(
    ctx: Context,
    company: str = typer.Argument(..., help="Company name"),
    meeting_type: str = typer.Option(
        "discovery", "--type", "-t", help="Meeting type: discovery, demo, negotiation"
    ),
):
    """Generate meeting preparation pack."""
    ws_ctx = get_workspace_context(ctx)
    typer.echo(f"📋 [placeholder] Preparing for {meeting_type} meeting with {company}...")
    typer.echo(f"📂 Workspace: {ws_ctx.name}")
    run = RunManager(command="prep", slug=company.lower().replace(" ", "_"), workspace=ws_ctx)

    run.log_action(
        phase="1",
        action=f"Start prep command for {company}",
        status="success",
    )

    # Placeholder implementation (not using LLM)
    prep_data = {
        "company": company,
        "meeting_type": meeting_type,
        "agenda": [
            "Introductions (5 min)",
            "Problem discovery (15 min)",
            "Solution overview (10 min)",
        ],
        "questions": ["What are your current challenges?", "How are you currently solving this?"],
        "stakeholder_map": {"VP Sales": "Economic buyer"},
    }

    markdown = f"# Meeting Prep: {company}\n\n## Agenda\n"
    for item in prep_data["agenda"]:
        markdown += f"- {item}\n"

    run.save_artifact("meeting_prep", markdown, prep_data)
    typer.echo("✅ [placeholder] Meeting prep pack created")


@app.command()
def followup(
    ctx: Context,
    company: str = typer.Argument(..., help="Company name"),
    notes: str = typer.Option(..., "--notes", "-n", help="Meeting notes or file path"),
):
    """Generate post-meeting follow-up."""
    ws_ctx = get_workspace_context(ctx)
    typer.echo(f"📝 [placeholder] Creating follow-up for {company}...")
    typer.echo(f"📂 Workspace: {ws_ctx.name}")
    run = RunManager(command="followup", slug=company.lower().replace(" ", "_"), workspace=ws_ctx)

    run.log_action(
        phase="1",
        action=f"Start followup command for {company}",
        status="success",
    )

    # Placeholder implementation (not using LLM)
    followup_data = {
        "company": company,
        "summary": "Good initial conversation, strong interest in solution",
        "next_steps": ["Send proposal", "Schedule demo", "Follow up in 1 week"],
        "tasks": [{"task": "Send proposal", "owner": "sales", "due": "2 days"}],
    }

    markdown = (
        f"# Follow-up: {company}\n\n## Summary\n{followup_data['summary']}\n\n## Next Steps\n"
    )
    for step in followup_data["next_steps"]:
        markdown += f"- {step}\n"

    run.save_artifact("followup", markdown, followup_data)
    typer.echo("✅ [placeholder] Follow-up created")

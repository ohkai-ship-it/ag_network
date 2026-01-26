"""CLI entry point for AG Network."""

import json
from pathlib import Path
from typing import List, Optional

import typer
from typer import Typer

import agnetwork.skills  # noqa: F401, I001 - Import skills to register them
from agnetwork.config import config
from agnetwork.orchestrator import RunManager
from agnetwork.skills.research_brief import ResearchBriefSkill
from agnetwork.tools.ingest import SourceIngestor

# Initialize Typer app
app = Typer(
    name="ag_network",
    help="Agent network: Workflow orchestration for agentic AI with a multipurpose skillset.",
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
    urls: Optional[List[str]] = typer.Option(
        None, "--url", "-u", help="URLs to fetch and use as sources (can be repeated)"
    ),
    use_memory: bool = typer.Option(
        False, "--use-memory/--no-memory", help="Enable memory retrieval (M5)"
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
        captured_sources = []

        # Fetch URLs if provided (M5)
        if urls:
            typer.echo(f"🌐 Fetching {len(urls)} URLs...")
            from agnetwork.storage.sqlite import SQLiteManager
            from agnetwork.tools.web import SourceCapture

            capture = SourceCapture(run.run_dir / "sources")
            db = SQLiteManager()

            for url in urls:
                typer.echo(f"   Fetching: {url[:60]}...")
                result = capture.capture_url(url)
                if result.is_success:
                    typer.echo(f"   ✅ {result.title or 'No title'}")
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


@app.command(name="validate-run")
def validate_run(
    run_path: Path = typer.Argument(..., help="Path to run folder to validate"),
    require_meta: bool = typer.Option(
        False, "--require-meta", "-m", help="Require meta blocks in artifacts"
    ),
    check_evidence: bool = typer.Option(
        False, "--check-evidence", "-e", help="Check claim evidence consistency (M4)"
    ),
):
    """Validate a run folder for integrity.

    M4: Use --check-evidence to verify claim→source links in the database.
    """
    from agnetwork.validate import validate_run_folder

    typer.echo(f"🔍 Validating run folder: {run_path}")

    result = validate_run_folder(
        run_path, require_meta=require_meta, check_evidence=check_evidence
    )

    typer.echo(str(result))

    if not result.is_valid:
        raise typer.Exit(1)


@app.command(name="run-pipeline")
def run_pipeline(
    company: str = typer.Argument(..., help="Company name to run pipeline for"),
    snapshot: str = typer.Option(
        "", "--snapshot", "-s", help="Company snapshot/description"
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
    urls: Optional[List[str]] = typer.Option(
        None, "--url", "-u", help="URLs to fetch and use as sources (can be repeated)"
    ),
    persona: str = typer.Option(
        "VP Sales", "--persona", help="Target persona"
    ),
    channel: str = typer.Option(
        "email", "--channel", help="Outreach channel: email or linkedin"
    ),
    meeting_type: str = typer.Option(
        "discovery", "--meeting-type", help="Meeting type: discovery, demo, negotiation"
    ),
    notes: str = typer.Option(
        "Pipeline run completed", "--notes", "-n", help="Meeting notes for follow-up"
    ),
    verify: bool = typer.Option(
        True, "--verify/--no-verify", help="Run verification on results"
    ),
    mode: str = typer.Option(
        "manual", "--mode", "-m", help="Execution mode: manual (default) or llm"
    ),
    use_memory: bool = typer.Option(
        False, "--use-memory/--no-memory", help="Enable memory retrieval for context (M4/M5)"
    ),
):
    """Run the full BD pipeline for a company.

    Generates all 5 BD artifacts in a single run:
    1. Research Brief
    2. Target Map
    3. Outreach Drafts
    4. Meeting Prep
    5. Follow-up Summary

    Modes:
    - manual: Deterministic template-based generation (default, no API keys needed)
    - llm: LLM-assisted generation (requires AG_LLM_ENABLED=1 and API keys)

    Memory (M4/M5):
    - --use-memory: Enable FTS5-based retrieval over stored sources/artifacts
    - --url: Fetch URLs into sources before running pipeline
    """
    from agnetwork.eval.verifier import Verifier
    from agnetwork.kernel import ExecutionMode, KernelExecutor, TaskSpec, TaskType

    # Validate and parse mode
    try:
        exec_mode = ExecutionMode(mode.lower())
    except ValueError:
        typer.echo(f"❌ Invalid mode: {mode}. Use 'manual' or 'llm'", err=True)
        raise typer.Exit(1)

    # Check LLM mode requirements
    llm_factory = None
    if exec_mode == ExecutionMode.LLM:
        from agnetwork.tools.llm import LLMFactory

        llm_factory = LLMFactory.from_env()

        if not llm_factory.is_enabled:
            typer.echo(
                "⚠️  LLM mode requested but AG_LLM_ENABLED=0. "
                "Set AG_LLM_ENABLED=1 in your environment or .env file.",
                err=True,
            )
            raise typer.Exit(1)

        typer.echo(f"🤖 Running in LLM mode (provider: {llm_factory.config.default_provider})")

    typer.echo(f"🚀 Running full BD pipeline for {company}...")

    # M5: Fetch URLs if provided
    captured_source_ids = []
    if urls:
        typer.echo(f"🌐 Fetching {len(urls)} URLs...")
        from agnetwork.orchestrator import RunManager
        from agnetwork.storage.sqlite import SQLiteManager
        from agnetwork.tools.web import SourceCapture

        # Create a temporary run to capture sources
        temp_run = RunManager(command="pipeline", slug=company.lower().replace(" ", "_"))
        capture = SourceCapture(temp_run.run_dir / "sources")
        db = SQLiteManager()

        for url in urls:
            typer.echo(f"   Fetching: {url[:60]}...")
            result = capture.capture_url(url)
            if result.is_success:
                typer.echo(f"   ✅ {result.title or 'No title'}")
                # Upsert to database for FTS indexing
                db.upsert_source_from_capture(
                    source_id=result.source_id,
                    url=result.url,
                    final_url=result.final_url,
                    title=result.title,
                    clean_text=result.clean_text,
                    content_hash=result.content_hash,
                    fetched_at=result.fetched_at.isoformat(),
                    run_id=temp_run.run_id,
                )
                captured_source_ids.append(result.source_id)
            else:
                typer.echo(f"   ❌ Failed: {result.error}", err=True)

        typer.echo(f"✅ Captured {len(captured_source_ids)} URLs")

        # Enable memory automatically when URLs are provided
        if captured_source_ids and not use_memory:
            use_memory = True
            typer.echo("🧠 Memory retrieval auto-enabled (URLs provided)")

    # M4: Memory retrieval status
    if use_memory:
        typer.echo("🧠 Memory retrieval enabled (FTS5)")

    # Build task spec
    task_spec = TaskSpec(
        task_type=TaskType.PIPELINE,
        inputs={
            "company": company,
            "snapshot": snapshot or f"{company} - company snapshot",
            "pains": pains or [],
            "triggers": triggers or [],
            "competitors": competitors or [],
            "persona": persona,
            "channel": channel,
            "meeting_type": meeting_type,
            "notes": notes,
            "source_ids": captured_source_ids,  # M5: Pass captured source IDs
        },
    )

    # Create executor with optional verifier and memory flag
    verifier = Verifier() if verify else None
    executor = KernelExecutor(
        verifier=verifier,
        mode=exec_mode,
        llm_factory=llm_factory,
        use_memory=use_memory,
    )

    # Execute pipeline
    result = executor.execute_task(task_spec)

    if result.success:
        mode_label = "LLM" if exec_mode == ExecutionMode.LLM else "manual"
        memory_label = " +memory" if result.memory_enabled else ""
        urls_label = f" +{len(captured_source_ids)}urls" if captured_source_ids else ""
        typer.echo(
            f"✅ Pipeline completed successfully! (mode: {mode_label}{memory_label}{urls_label})"
        )
        typer.echo(f"📁 Run folder: {config.runs_dir / result.run_id}")
        typer.echo(f"📄 Artifacts created: {len(result.artifacts_written)}")
        for artifact in result.artifacts_written:
            typer.echo(f"   - {artifact}")
        if result.claims_persisted > 0:
            typer.echo(f"📋 Claims persisted: {result.claims_persisted}")
    else:
        typer.echo("❌ Pipeline failed!")
        for error in result.errors:
            typer.echo(f"   Error: {error}", err=True)

        if result.verification_issues:
            typer.echo("Verification issues:")
            for issue in result.verification_issues:
                typer.echo(f"   - [{issue.get('severity')}] {issue.get('message')}")

        raise typer.Exit(1)


# Create memory subcommand group
memory_app = Typer(help="Memory management commands (M5)")
app.add_typer(memory_app, name="memory")


@memory_app.command(name="rebuild-index")
def memory_rebuild_index():
    """Rebuild FTS5 search indexes from base tables.

    Use this if FTS indexes get out of sync with sources/artifacts tables.
    """
    from agnetwork.storage.sqlite import SQLiteManager

    typer.echo("🔧 Rebuilding FTS5 indexes...")

    db = SQLiteManager()
    db.rebuild_fts_index()

    typer.echo("✅ FTS5 indexes rebuilt successfully!")


@memory_app.command(name="search")
def memory_search(
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

    db = SQLiteManager()

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


if __name__ == "__main__":
    app()

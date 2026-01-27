"""CLI entry point for AG Network."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

import typer
from typer import Typer

import agnetwork.skills  # noqa: F401, I001 - Import skills to register them
from agnetwork.config import config
from agnetwork.orchestrator import RunManager
from agnetwork.skills.research_brief import ResearchBriefSkill
from agnetwork.tools.ingest import SourceIngestor

if TYPE_CHECKING:
    from agnetwork.kernel import ExecutionMode, PipelineResult
    from agnetwork.tools.llm import LLMFactory

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


# =============================================================================
# Pipeline Helpers (M6.3 refactored)
# =============================================================================


def _resolve_execution_mode(mode: str) -> "ExecutionMode":
    """Parse and validate execution mode string.

    Args:
        mode: Mode string ('manual' or 'llm')

    Returns:
        ExecutionMode enum value

    Raises:
        typer.Exit: If mode is invalid
    """
    from agnetwork.kernel import ExecutionMode

    try:
        return ExecutionMode(mode.lower())
    except ValueError:
        typer.echo(f"❌ Invalid mode: {mode}. Use 'manual' or 'llm'", err=True)
        raise typer.Exit(1)


def _setup_llm_factory(exec_mode: "ExecutionMode") -> Optional["LLMFactory"]:
    """Setup LLM factory if LLM mode is requested.

    Args:
        exec_mode: The execution mode

    Returns:
        LLMFactory instance or None for manual mode

    Raises:
        typer.Exit: If LLM mode requested but not enabled
    """
    from agnetwork.kernel import ExecutionMode

    if exec_mode != ExecutionMode.LLM:
        return None

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
    return llm_factory


def _fetch_urls_for_pipeline(
    urls: List[str],
    company: str,
) -> List[str]:
    """Fetch URLs and store them for pipeline use.

    Args:
        urls: List of URLs to fetch
        company: Company name for run slug

    Returns:
        List of captured source IDs
    """
    from agnetwork.orchestrator import RunManager
    from agnetwork.storage.sqlite import SQLiteManager
    from agnetwork.tools.web import SourceCapture

    typer.echo(f"🌐 Fetching {len(urls)} URLs...")

    temp_run = RunManager(command="pipeline", slug=company.lower().replace(" ", "_"))
    capture = SourceCapture(temp_run.run_dir / "sources")
    db = SQLiteManager()

    captured_source_ids = []
    for url in urls:
        typer.echo(f"   Fetching: {url[:60]}...")
        result = capture.capture_url(url)
        if result.is_success:
            typer.echo(f"   ✅ {result.title or 'No title'}")
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
    return captured_source_ids


def _print_pipeline_result(
    result: "PipelineResult",
    exec_mode: "ExecutionMode",
    captured_source_ids: List[str],
) -> None:
    """Print pipeline execution result to terminal.

    Args:
        result: The pipeline result
        exec_mode: Execution mode used
        captured_source_ids: List of captured source IDs
    """
    from agnetwork.kernel import ExecutionMode

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
    from agnetwork.kernel import KernelExecutor, TaskSpec, TaskType

    # Resolve execution mode and LLM factory
    exec_mode = _resolve_execution_mode(mode)
    llm_factory = _setup_llm_factory(exec_mode)

    typer.echo(f"🚀 Running full BD pipeline for {company}...")

    # Fetch URLs if provided
    captured_source_ids: List[str] = []
    if urls:
        captured_source_ids = _fetch_urls_for_pipeline(urls, company)
        if captured_source_ids and not use_memory:
            use_memory = True
            typer.echo("🧠 Memory retrieval auto-enabled (URLs provided)")

    if use_memory:
        typer.echo("🧠 Memory retrieval enabled (FTS5)")

    # Build task spec and execute
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
            "source_ids": captured_source_ids,
        },
    )

    verifier = Verifier() if verify else None
    executor = KernelExecutor(
        verifier=verifier,
        mode=exec_mode,
        llm_factory=llm_factory,
        use_memory=use_memory,
    )

    result = executor.execute_task(task_spec)
    _print_pipeline_result(result, exec_mode, captured_source_ids)

    if not result.success:
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


# =============================================================================
# CRM Subcommand Group (M6)
# =============================================================================

crm_app = Typer(help="CRM integration commands (M6)")
app.add_typer(crm_app, name="crm")


@crm_app.command(name="export-run")
def crm_export_run(
    run_id: str = typer.Argument(..., help="Run ID to export"),
    format: str = typer.Option(
        "json", "--format", "-f", help="Output format: json or csv"
    ),
    out: Optional[Path] = typer.Option(
        None, "--out", "-o", help="Output directory path"
    ),
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

    typer.echo(f"📦 Exporting run: {run_id}")

    # Map run to CRM objects
    try:
        package = map_run_to_crm(run_id)
    except ValueError as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)

    # Determine output path
    if out is None:
        out = config.project_root / "data" / "crm_exports" / run_id

    typer.echo(f"📁 Output directory: {out}")

    # Export using adapter from factory (M6.1)
    adapter = CRMAdapterFactory.from_env()
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
    format: str = typer.Option(
        "json", "--format", "-f", help="Output format: json or csv"
    ),
    out: Optional[Path] = typer.Option(
        None, "--out", "-o", help="Output directory path"
    ),
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
    # Find latest run
    runs = sorted(config.runs_dir.glob("*"), key=lambda x: x.name, reverse=True)

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

    if out is None:
        out = config.project_root / "data" / "crm_exports" / run_id

    typer.echo(f"📁 Output directory: {out}")

    adapter = CRMAdapterFactory.from_env()
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

    mode = "DRY RUN" if dry_run else "LIVE"
    typer.echo(f"📥 Importing from: {file} ({mode})")

    adapter = CRMAdapterFactory.from_env()
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
    entity: str = typer.Argument(
        "accounts", help="Entity type: accounts, contacts, or activities"
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results"),
    account_id: Optional[str] = typer.Option(
        None, "--account", "-a", help="Filter by account ID"
    ),
):
    """List CRM entities from storage.

    Examples:
        ag crm list accounts
        ag crm list contacts --account acc_testcompany
        ag crm list activities --limit 10
    """
    from agnetwork.crm.adapters import CRMAdapterFactory

    adapter = CRMAdapterFactory.from_env()

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

    if entity not in handlers:
        typer.echo(f"❌ Unknown entity type: {entity}", err=True)
        typer.echo("   Valid types: accounts, contacts, activities")
        raise typer.Exit(1)

    handlers[entity]()


@crm_app.command(name="search")
def crm_search(
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

    adapter = CRMAdapterFactory.from_env()

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
def crm_stats():
    """Show CRM storage statistics.

    Example:
        ag crm stats
    """
    from agnetwork.crm.storage import CRMStorage

    storage = CRMStorage()
    stats = storage.get_stats()

    typer.echo("\n📊 CRM Storage Statistics:")
    typer.echo(f"   Accounts:   {stats['accounts']}")
    typer.echo(f"   Contacts:   {stats['contacts']}")
    typer.echo(f"   Activities: {stats['activities']}")


# =============================================================================
# Sequence Subcommand Group (M6)
# =============================================================================

sequence_app = Typer(help="Outreach sequence commands (M6)")
app.add_typer(sequence_app, name="sequence")


@sequence_app.command(name="plan")
def sequence_plan(
    run_id: str = typer.Argument(..., help="Run ID to build sequence from"),
    channel: str = typer.Option(
        "email", "--channel", "-c", help="Channel: email or linkedin"
    ),
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
    import json
    from datetime import datetime, timezone

    from agnetwork.crm.models import CRMExportManifest, CRMExportPackage
    from agnetwork.crm.sequence import SequenceBuilder

    typer.echo(f"📋 Building sequence plan for run: {run_id}")

    # Load run data
    run_dir = config.runs_dir / run_id
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


if __name__ == "__main__":
    app()

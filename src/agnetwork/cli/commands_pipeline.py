"""Status and pipeline CLI commands.

Commands for run status, validation, and pipeline execution:
- status: Show status of recent runs
- validate-run: Validate a run folder for integrity
- run-pipeline: Run the full BD pipeline for a company
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

import typer
from typer import Context

from agnetwork.cli.app import app, get_workspace_context
from agnetwork.config import config

if TYPE_CHECKING:
    from agnetwork.kernel import ExecutionMode, PipelineResult
    from agnetwork.orchestrator import RunManager
    from agnetwork.tools.llm import LLMFactory
    from agnetwork.workspaces.context import WorkspaceContext


@app.command()
def status(ctx: Context):
    """Show status of recent runs in the active workspace."""
    ws_ctx = get_workspace_context(ctx)
    typer.echo(f"📂 Workspace: {ws_ctx.name}")
    typer.echo("📊 Recent runs:")
    runs = sorted(ws_ctx.runs_dir.glob("*"), key=lambda x: x.name, reverse=True)
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

    result = validate_run_folder(run_path, require_meta=require_meta, check_evidence=check_evidence)

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


def _fetch_urls_for_pipeline(
    urls: List[str],
    company: str,
    ws_ctx: "WorkspaceContext",
    *,
    deep_links: bool = False,
    deep_links_mode: str = "deterministic",
    deep_links_max: int = 4,
) -> Tuple[List[str], "RunManager"]:
    """Fetch URLs and store them for pipeline use.

    Args:
        urls: List of URLs to fetch
        company: Company name for run slug
        ws_ctx: Workspace context for scoped storage
        deep_links: Whether to discover and fetch deep links
        deep_links_mode: "deterministic" or "agent"
        deep_links_max: Maximum deep links to fetch per homepage

    Returns:
        Tuple of (list of captured source IDs, RunManager for reuse by executor)
    """
    from agnetwork.orchestrator import RunManager
    from agnetwork.storage.sqlite import SQLiteManager
    from agnetwork.tools.web import SourceCapture

    typer.echo(f"🌐 [fetched] Fetching {len(urls)} URLs...")

    temp_run = RunManager(
        command="pipeline", slug=company.lower().replace(" ", "_"), workspace=ws_ctx
    )
    capture = SourceCapture(temp_run.run_dir / "sources")
    db = SQLiteManager(db_path=ws_ctx.db_path, workspace_id=ws_ctx.workspace_id)

    captured_source_ids = []
    for url in urls:
        typer.echo(f"   [fetched] {url[:60]}...")
        result = capture.capture_url(url)
        if result.is_success:
            cache_label = " [cached]" if result.is_cached else ""
            typer.echo(f"   ✅{cache_label} {result.title or 'No title'}")
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

            # M8: Deep link discovery if enabled and this looks like a homepage
            if deep_links and result.raw_path:
                dl_captured = _discover_and_fetch_deep_links(
                    url=url,
                    raw_path=temp_run.run_dir / result.raw_path,
                    run_dir=temp_run.run_dir,
                    deep_links_max=deep_links_max,
                    deep_links_mode=deep_links_mode,
                    capture=capture,
                    db=db,
                    run_id=temp_run.run_id,
                )
                captured_source_ids.extend([r.source_id for r in dl_captured])
        else:
            typer.echo(f"   ❌ Failed: {result.error}", err=True)

    typer.echo(f"✅ Captured {len(captured_source_ids)} URLs")
    return captured_source_ids, temp_run


def _build_mode_label(result: "PipelineResult", exec_mode: "ExecutionMode") -> str:
    """Build truthful mode label for pipeline result.

    PR4: Returns appropriate truth labels based on execution mode and cache status.
    """
    from agnetwork.kernel import ExecutionMode

    # Check if any step results have cached=True
    any_cached = any(sr.metrics and sr.metrics.cached for sr in result.step_results.values())

    if exec_mode == ExecutionMode.LLM:
        return "[LLM] [cached]" if any_cached else "[LLM]"
    return "[computed]"


def _print_pipeline_result(
    result: "PipelineResult",
    exec_mode: "ExecutionMode",
    captured_source_ids: List[str],
) -> None:
    """Print pipeline execution result to terminal.

    PR4: Uses truth labels to indicate actual execution mode.

    Args:
        result: The pipeline result
        exec_mode: Execution mode used
        captured_source_ids: List of captured source IDs
    """
    if result.success:
        mode_label = _build_mode_label(result, exec_mode)
        memory_label = " +memory" if result.memory_enabled else ""
        urls_label = f" +{len(captured_source_ids)}urls" if captured_source_ids else ""
        typer.echo(f"✅ Pipeline completed successfully! {mode_label}{memory_label}{urls_label}")
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
    ctx: Context,
    company: str = typer.Argument(..., help="Company name to run pipeline for"),
    snapshot: str = typer.Option("", "--snapshot", "-s", help="Company snapshot/description"),
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
    persona: str = typer.Option("VP Sales", "--persona", help="Target persona"),
    channel: str = typer.Option("email", "--channel", help="Outreach channel: email or linkedin"),
    meeting_type: str = typer.Option(
        "discovery", "--meeting-type", help="Meeting type: discovery, demo, negotiation"
    ),
    notes: str = typer.Option(
        "Pipeline run completed", "--notes", "-n", help="Meeting notes for follow-up"
    ),
    verify: bool = typer.Option(True, "--verify/--no-verify", help="Run verification on results"),
    mode: str = typer.Option(
        "manual", "--mode", "-m", help="Execution mode: manual (default) or llm"
    ),
    use_memory: bool = typer.Option(
        False, "--use-memory/--no-memory", help="Enable memory retrieval for context (M4/M5)"
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

    Deep Links (M8):
    - --deep-links: Discover and fetch additional pages from homepage (2-4 pages)
    - --deep-links-mode: Selection mode (deterministic or agent)
    - --deep-links-max: Maximum deep links to fetch (default 4)
    """
    from agnetwork.eval.verifier import Verifier
    from agnetwork.kernel import KernelExecutor, TaskSpec, TaskType

    ws_ctx = get_workspace_context(ctx)

    # Resolve execution mode and LLM factory
    exec_mode = _resolve_execution_mode(mode)
    llm_factory = _setup_llm_factory(exec_mode)

    typer.echo(f"🚀 Running full BD pipeline for {company}...")
    typer.echo(f"📂 Workspace: {ws_ctx.name}")

    # Fetch URLs if provided (with optional deep link discovery - M8)
    captured_source_ids: List[str] = []
    pipeline_run = None  # Will be set if URLs are fetched
    if urls:
        captured_source_ids, pipeline_run = _fetch_urls_for_pipeline(
            urls,
            company,
            ws_ctx,
            deep_links=deep_links,
            deep_links_mode=deep_links_mode,
            deep_links_max=deep_links_max,
        )
        if captured_source_ids and not use_memory:
            use_memory = True
            typer.echo("🧠 Memory retrieval auto-enabled (URLs provided)")

    if deep_links:
        typer.echo(f"🔗 Deep link discovery: {deep_links_mode} mode (max {deep_links_max})")

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
            "deep_links_enabled": deep_links,
            "deep_links_mode": deep_links_mode if deep_links else None,
        },
        workspace_context=ws_ctx,  # M7.1: Pass workspace context for scoped runs
    )

    verifier = Verifier() if verify else None
    executor = KernelExecutor(
        verifier=verifier,
        mode=exec_mode,
        llm_factory=llm_factory,
        use_memory=use_memory,
    )

    # Pass the run_manager from URL fetching to reuse the same run folder
    result = executor.execute_task(task_spec, run_manager=pipeline_run)
    _print_pipeline_result(result, exec_mode, captured_source_ids)

    if not result.success:
        raise typer.Exit(1)

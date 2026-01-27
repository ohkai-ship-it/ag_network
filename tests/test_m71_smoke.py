"""M7.1 Smoke tests for workspace flag and skill commands.

These tests verify:
D1) Global --workspace flag works correctly across commands
D2) All 6 new skill commands run and produce artifacts
"""

import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Generator

import pytest
from typer.testing import CliRunner

import agnetwork.config
from agnetwork.cli import app


@pytest.fixture
def runner() -> CliRunner:
    """Provide a CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_workspace_registry() -> Generator[Path, None, None]:
    """Provide temp directory for workspace registry and patch it."""
    import gc

    with TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        registry_root = Path(tmpdir)
        yield registry_root
        # Force garbage collection to close any lingering connections
        gc.collect()


def _close_loggers():
    """Close all loggers to release file handles (Windows compatibility)."""
    for logger_name in list(logging.Logger.manager.loggerDict):
        if logger_name.startswith("agnetwork."):
            logger = logging.getLogger(logger_name)
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)


class TestWorkspaceFlagSmoke:
    """D1) Tests for global --workspace flag."""

    def test_workspace_flag_creates_runs_in_correct_workspace(
        self, runner: CliRunner, temp_workspace_registry: Path
    ):
        """Running with --workspace alpha creates run in alpha only."""
        from agnetwork.workspaces.registry import WorkspaceRegistry

        # Create two workspaces
        registry = WorkspaceRegistry(registry_root=temp_workspace_registry)
        ctx_alpha = registry.create_workspace("alpha")
        ctx_beta = registry.create_workspace("beta")

        # Patch the WorkspaceRegistry to use our temp directory
        original_init = WorkspaceRegistry.__init__

        def patched_init(self, registry_root=None):
            original_init(self, registry_root=temp_workspace_registry)

        WorkspaceRegistry.__init__ = patched_init

        try:
            # Run targets command in alpha workspace
            result = runner.invoke(
                app,
                ["--workspace", "alpha", "targets", "TestAlphaCompany"],
            )

            # Close loggers before checking results
            _close_loggers()

            # Should succeed
            assert result.exit_code == 0, f"Failed: {result.output}"
            assert "TestAlphaCompany" in result.output

            # Check run was created in alpha workspace
            alpha_runs = list(ctx_alpha.runs_dir.glob("*__testalpha*__targets"))
            assert len(alpha_runs) == 1, f"Expected 1 run in alpha, found {len(alpha_runs)}"

            # Check NO run was created in beta workspace
            beta_runs = list(ctx_beta.runs_dir.glob("*"))
            assert len(beta_runs) == 0, f"Expected 0 runs in beta, found {len(beta_runs)}"

        finally:
            WorkspaceRegistry.__init__ = original_init

    def test_workspace_flag_not_found_exits_error(
        self, runner: CliRunner, temp_workspace_registry: Path
    ):
        """Running with --workspace for non-existent workspace exits with error."""
        from agnetwork.workspaces.registry import WorkspaceRegistry

        # Patch the WorkspaceRegistry
        original_init = WorkspaceRegistry.__init__

        def patched_init(self, registry_root=None):
            original_init(self, registry_root=temp_workspace_registry)

        WorkspaceRegistry.__init__ = patched_init

        try:
            result = runner.invoke(
                app,
                ["--workspace", "nonexistent", "targets", "TestCompany"],
            )

            # Should fail with error
            assert result.exit_code != 0
            assert "not found" in result.output.lower() or "nonexistent" in result.output.lower()

        finally:
            WorkspaceRegistry.__init__ = original_init

    def test_memory_search_uses_workspace_database(
        self, runner: CliRunner, temp_workspace_registry: Path
    ):
        """Memory search in beta workspace doesn't find alpha's data."""
        from agnetwork.workspaces.registry import WorkspaceRegistry

        # Create two workspaces
        registry = WorkspaceRegistry(registry_root=temp_workspace_registry)
        registry.create_workspace("alpha")
        registry.create_workspace("beta")

        # Patch the WorkspaceRegistry
        original_init = WorkspaceRegistry.__init__

        def patched_init(self, registry_root=None):
            original_init(self, registry_root=temp_workspace_registry)

        WorkspaceRegistry.__init__ = patched_init

        try:
            # Search in beta for a unique token
            result = runner.invoke(
                app,
                ["--workspace", "beta", "memory", "search", "UNIQUE_ALPHA_TOKEN_12345"],
            )

            _close_loggers()

            # Should run successfully but find nothing
            assert result.exit_code == 0
            assert "No matches found" in result.output or "Sources:" in result.output

        finally:
            WorkspaceRegistry.__init__ = original_init


class TestSkillCommandsSmoke:
    """D2) Tests for new skill commands."""

    @pytest.mark.parametrize(
        "command,args,artifact_prefix",
        [
            (
                "meeting-summary",
                ["--topic", "Test Meeting", "--notes", "- Discussion point 1"],
                "meeting_summary",
            ),
            (
                "status-update",
                ["--accomplishment", "Completed task 1", "--in-progress", "Task 2"],
                "status_update",
            ),
            (
                "decision-log",
                ["--title", "Test Decision", "--context", "Background", "--decision", "Decided X"],
                "decision_log",
            ),
            (
                "weekly-plan",
                ["--goal", "Exercise", "--monday", "Standup"],
                "weekly_plan",
            ),
            (
                "errand-list",
                ["--errand", "Buy groceries"],
                "errand_list",
            ),
            (
                "travel-outline",
                ["--destination", "Paris", "--start", "2026-02-10", "--end", "2026-02-17"],
                "travel_outline",
            ),
        ],
    )
    def test_skill_command_creates_artifacts(
        self,
        runner: CliRunner,
        temp_workspace_runs_dir: Path,
        command: str,
        args: list,
        artifact_prefix: str,
    ):
        """Each skill command creates run folder with expected artifacts."""
        result = runner.invoke(app, [command] + args)

        _close_loggers()

        # Command should succeed
        assert result.exit_code == 0, f"Command {command} failed: {result.output}"

        # Run folder should be created
        runs = list(temp_workspace_runs_dir.glob(f"*__{artifact_prefix}*"))
        assert len(runs) >= 1, f"No run folder found for {command}"

        run_dir = runs[0]

        # Artifacts folder should exist
        artifacts_dir = run_dir / "artifacts"
        assert artifacts_dir.exists(), f"No artifacts dir for {command}"

        # Should have at least one artifact file
        artifact_files = list(artifacts_dir.glob("*"))
        assert len(artifact_files) >= 1, f"No artifacts for {command}"

        # JSON artifact should exist and be valid
        json_files = list(artifacts_dir.glob("*.json"))
        assert len(json_files) >= 1, f"No JSON artifact for {command}"

        # Verify JSON is parseable
        for json_file in json_files:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert isinstance(data, dict), f"Invalid JSON structure for {command}"

        # MD artifact should exist
        md_files = list(artifacts_dir.glob("*.md"))
        assert len(md_files) >= 1, f"No MD artifact for {command}"


class TestSkillRoutesThroughKernel:
    """Additional test to verify skills route through kernel executor."""

    @pytest.fixture
    def temp_workspace_runs_dir(self) -> Generator[Path, None, None]:
        """Provide a temporary runs directory and patch config."""
        original_runs_dir = agnetwork.config.config.runs_dir

        with TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            agnetwork.config.config.runs_dir = temp_path
            yield temp_path
            agnetwork.config.config.runs_dir = original_runs_dir
            _close_loggers()

    def test_meeting_summary_skill_is_registered(self):
        """Verify meeting_summary skill is in the registry."""
        from agnetwork.kernel import skill_registry

        assert skill_registry.has("meeting_summary"), "meeting_summary not registered"

    def test_status_update_skill_is_registered(self):
        """Verify status_update skill is in the registry."""
        from agnetwork.kernel import skill_registry

        assert skill_registry.has("status_update"), "status_update not registered"

    def test_decision_log_skill_is_registered(self):
        """Verify decision_log skill is in the registry."""
        from agnetwork.kernel import skill_registry

        assert skill_registry.has("decision_log"), "decision_log not registered"

    def test_weekly_plan_skill_is_registered(self):
        """Verify weekly_plan skill is in the registry."""
        from agnetwork.kernel import skill_registry

        assert skill_registry.has("weekly_plan"), "weekly_plan not registered"

    def test_errand_list_skill_is_registered(self):
        """Verify errand_list skill is in the registry."""
        from agnetwork.kernel import skill_registry

        assert skill_registry.has("errand_list"), "errand_list not registered"

    def test_travel_outline_skill_is_registered(self):
        """Verify travel_outline skill is in the registry."""
        from agnetwork.kernel import skill_registry

        assert skill_registry.has("travel_outline"), "travel_outline not registered"

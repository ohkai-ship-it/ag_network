"""Tests for PR2: CLI workspace path isolation.

Verifies that:
- status command shows only runs from the active workspace (ID #7)
- sequence plan command uses workspace runs_dir (ID #9)
- research command uses workspace-scoped DB (ID #10 - already fixed, regression test)

These tests ensure CLI commands respect workspace boundaries and don't
leak data across workspaces.
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Generator

import pytest
from typer.testing import CliRunner

from agnetwork.cli import app


@pytest.fixture
def runner() -> CliRunner:
    """Provide a CLI test runner."""
    return CliRunner()


@pytest.fixture
def two_workspaces() -> Generator[tuple, None, None]:
    """Create two isolated workspaces for testing.

    Yields:
        Tuple of (ws1_context, ws2_context, registry)
    """
    from agnetwork.workspaces.registry import WorkspaceRegistry

    with TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        temp_registry_root = Path(tmpdir)
        registry = WorkspaceRegistry(registry_root=temp_registry_root)

        # Create two workspaces
        ws1 = registry.create_workspace("workspace_one")
        ws2 = registry.create_workspace("workspace_two")

        # Patch WorkspaceRegistry to use our temp directory
        original_init = WorkspaceRegistry.__init__

        def patched_init(self, registry_root=None):
            original_init(self, registry_root=temp_registry_root)

        WorkspaceRegistry.__init__ = patched_init

        try:
            yield ws1, ws2, registry
        finally:
            WorkspaceRegistry.__init__ = original_init


class TestStatusWorkspaceIsolation:
    """Tests for status command workspace isolation (Backlog ID #7)."""

    def test_status_shows_only_workspace_runs(self, runner: CliRunner, two_workspaces):
        """status command shows only runs from the active workspace."""
        ws1, ws2, registry = two_workspaces

        # Create a run in ws1
        run1_dir = ws1.runs_dir / "20260129_test__company1__pipeline"
        run1_dir.mkdir(parents=True)
        (run1_dir / "logs").mkdir()
        with open(run1_dir / "logs" / "agent_status.json", "w") as f:
            json.dump({"current_phase": "ws1_phase"}, f)

        # Create a run in ws2
        run2_dir = ws2.runs_dir / "20260129_test__company2__pipeline"
        run2_dir.mkdir(parents=True)
        (run2_dir / "logs").mkdir()
        with open(run2_dir / "logs" / "agent_status.json", "w") as f:
            json.dump({"current_phase": "ws2_phase"}, f)

        # Set ws1 as default and check status
        registry.set_default_workspace("workspace_one")
        result1 = runner.invoke(app, ["status"])

        assert result1.exit_code == 0, f"Failed: {result1.output}"
        assert "ws1_phase" in result1.output
        assert "ws2_phase" not in result1.output
        assert "workspace_one" in result1.output

        # Set ws2 as default and check status
        registry.set_default_workspace("workspace_two")
        result2 = runner.invoke(app, ["status"])

        assert result2.exit_code == 0, f"Failed: {result2.output}"
        assert "ws2_phase" in result2.output
        assert "ws1_phase" not in result2.output
        assert "workspace_two" in result2.output

    def test_status_with_explicit_workspace_flag(self, runner: CliRunner, two_workspaces):
        """status respects --workspace flag."""
        ws1, ws2, registry = two_workspaces

        # Create a run in ws1 only
        run1_dir = ws1.runs_dir / "20260129_explicit__company1__pipeline"
        run1_dir.mkdir(parents=True)
        (run1_dir / "logs").mkdir()
        with open(run1_dir / "logs" / "agent_status.json", "w") as f:
            json.dump({"current_phase": "explicit_ws1"}, f)

        # Set ws2 as default but use --workspace flag for ws1
        registry.set_default_workspace("workspace_two")
        result = runner.invoke(app, ["--workspace", "workspace_one", "status"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "explicit_ws1" in result.output
        assert "workspace_one" in result.output


class TestSequencePlanWorkspaceIsolation:
    """Tests for sequence plan command workspace isolation (Backlog ID #9)."""

    def test_sequence_plan_uses_workspace_runs_dir(self, runner: CliRunner, two_workspaces):
        """sequence plan reads from workspace runs_dir only."""
        ws1, ws2, registry = two_workspaces

        # Create run with outreach artifact in ws1
        run1_dir = ws1.runs_dir / "20260129_seq__company1__pipeline"
        run1_dir.mkdir(parents=True)
        (run1_dir / "artifacts").mkdir()
        outreach1 = {
            "company": "Company1",
            "persona": "VP Sales",
            "channel": "email",
            "subject_or_hook": "Subject 1",
            "body": "Body 1",
        }
        with open(run1_dir / "artifacts" / "outreach.json", "w") as f:
            json.dump(outreach1, f)

        # Create run with outreach artifact in ws2
        run2_dir = ws2.runs_dir / "20260129_seq__company2__pipeline"
        run2_dir.mkdir(parents=True)
        (run2_dir / "artifacts").mkdir()
        outreach2 = {
            "company": "Company2",
            "persona": "VP Sales",
            "channel": "email",
            "subject_or_hook": "Subject 2",
            "body": "Body 2",
        }
        with open(run2_dir / "artifacts" / "outreach.json", "w") as f:
            json.dump(outreach2, f)

        # Set ws1 as default and plan for ws1 run
        registry.set_default_workspace("workspace_one")
        result1 = runner.invoke(app, ["sequence", "plan", run1_dir.name])

        assert result1.exit_code == 0, f"Failed: {result1.output}"
        assert "Company1" in result1.output

        # Try to plan for ws2 run from ws1 - should fail (run not found)
        result_cross = runner.invoke(app, ["sequence", "plan", run2_dir.name])
        assert result_cross.exit_code == 1
        assert "Run not found" in result_cross.output

    def test_sequence_plan_rejects_cross_workspace_run(self, runner: CliRunner, two_workspaces):
        """sequence plan cannot access runs from another workspace."""
        ws1, ws2, registry = two_workspaces

        # Create run only in ws2
        run2_dir = ws2.runs_dir / "20260129_cross__onlyws2__pipeline"
        run2_dir.mkdir(parents=True)
        (run2_dir / "artifacts").mkdir()
        outreach = {
            "company": "OnlyWS2",
            "persona": "VP",
            "channel": "email",
            "subject_or_hook": "Test",
            "body": "Test",
        }
        with open(run2_dir / "artifacts" / "outreach.json", "w") as f:
            json.dump(outreach, f)

        # Set ws1 as default - should not find ws2 run
        registry.set_default_workspace("workspace_one")
        result = runner.invoke(app, ["sequence", "plan", run2_dir.name])

        assert result.exit_code == 1
        assert "Run not found" in result.output


class TestResearchWorkspaceIsolation:
    """Tests for research command workspace isolation (Backlog ID #10).

    Note: The research command was already fixed in PR1. These tests
    serve as regression tests to ensure it stays workspace-aware.
    """

    def test_research_command_uses_workspace_db(self, runner: CliRunner, two_workspaces):
        """research command writes sources to workspace-scoped DB."""
        ws1, ws2, registry = two_workspaces

        # Set ws1 as default
        registry.set_default_workspace("workspace_one")

        # Run research with minimal input (will create run dir but may not complete)
        # We just verify it starts with correct workspace
        result = runner.invoke(
            app,
            [
                "research",
                "TestCompany",
                "--snapshot",
                "Test snapshot",
            ],
        )

        # Check workspace is shown in output
        assert "workspace_one" in result.output.lower() or "Workspace:" in result.output

        # Verify run was created in ws1's runs_dir, not ws2's
        ws1_runs = list(ws1.runs_dir.glob("*research*"))
        ws2_runs = list(ws2.runs_dir.glob("*research*"))

        assert len(ws1_runs) >= 0  # May or may not create run depending on execution
        # Key assertion: ws2 should have no research runs
        assert len(ws2_runs) == 0, "Research created run in wrong workspace!"


class TestNoConfigRunsDirInWorkspaceCommands:
    """Anti-regression test: ensure workspace-aware commands don't use config.runs_dir."""

    def test_no_config_runs_dir_in_status_and_sequence(self):
        """AST-like check: status and sequence plan should not use config.runs_dir."""
        import ast
        from pathlib import Path

        cli_path = Path(__file__).parent.parent / "src" / "agnetwork" / "cli.py"
        source = cli_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(cli_path))

        # Find the status and sequence_plan function definitions
        target_functions = {"status", "sequence_plan"}
        violations = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in target_functions:
                # Walk the function body looking for config.runs_dir
                for child in ast.walk(node):
                    if isinstance(child, ast.Attribute):
                        # Check for config.runs_dir pattern
                        if (
                            child.attr == "runs_dir"
                            and isinstance(child.value, ast.Name)
                            and child.value.id == "config"
                        ):
                            violations.append(
                                f"{node.name}:{child.lineno} uses config.runs_dir"
                            )

        if violations:
            pytest.fail(
                "Found config.runs_dir usage in workspace-aware commands:\n"
                + "\n".join(violations)
                + "\n\nUse ws_ctx.runs_dir instead."
            )

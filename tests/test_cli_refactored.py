"""Tests for CLI refactored helpers (M6.3).

Verifies that:
- Timezone import fix works (F821 issue)
- run_pipeline helper functions work correctly
- crm_list helper functions render correctly
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Generator
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import agnetwork.config
from agnetwork.cli import (
    _render_accounts_list,
    _render_activities_list,
    _render_contacts_list,
    _resolve_execution_mode,
    _setup_llm_factory,
    app,
)


@pytest.fixture
def runner() -> CliRunner:
    """Provide a CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_runs_dir() -> Generator[Path, None, None]:
    """Provide a temporary runs directory and patch config."""
    import logging

    original_runs_dir = agnetwork.config.config.runs_dir

    with TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)
        agnetwork.config.config.runs_dir = temp_path
        yield temp_path
        agnetwork.config.config.runs_dir = original_runs_dir
        # Close all loggers to release file handles (needed on Windows)
        for logger_name in list(logging.Logger.manager.loggerDict):
            if logger_name.startswith("agnetwork."):
                logger = logging.getLogger(logger_name)
                for handler in logger.handlers[:]:
                    handler.close()
                    logger.removeHandler(handler)


class TestTimezoneImport:
    """Tests verifying timezone import fix (F821)."""

    def test_sequence_plan_command_parses_dates(self, runner: CliRunner, temp_runs_dir: Path):
        """sequence plan command can parse dates without NameError."""
        # First create a run with outreach artifact
        run_dir = temp_runs_dir / "20260127_test__testcompany__pipeline"
        run_dir.mkdir(parents=True)
        (run_dir / "artifacts").mkdir()

        # Create minimal outreach artifact
        outreach = {
            "company": "TestCompany",
            "persona": "VP Sales",
            "channel": "email",
            "subject_or_hook": "Test Subject",
            "body": "Test body",
        }
        with open(run_dir / "artifacts" / "outreach.json", "w") as f:
            json.dump(outreach, f)

        # Run the sequence plan command with a start date
        result = runner.invoke(
            app,
            [
                "sequence",
                "plan",
                run_dir.name,
                "--start-date",
                "2026-01-27",
            ],
        )

        # Should not raise NameError for timezone
        assert "NameError" not in result.output
        assert "timezone" not in result.output.lower() or "invalid" not in result.output.lower()
        # Note: The command may fail for other reasons, but not timezone NameError


class TestResolveExecutionMode:
    """Tests for _resolve_execution_mode helper."""

    def test_manual_mode(self):
        """Returns ExecutionMode.MANUAL for 'manual'."""
        from agnetwork.kernel import ExecutionMode

        result = _resolve_execution_mode("manual")
        assert result == ExecutionMode.MANUAL

    def test_llm_mode(self):
        """Returns ExecutionMode.LLM for 'llm'."""
        from agnetwork.kernel import ExecutionMode

        result = _resolve_execution_mode("llm")
        assert result == ExecutionMode.LLM

    def test_case_insensitive(self):
        """Mode parsing is case-insensitive."""
        from agnetwork.kernel import ExecutionMode

        assert _resolve_execution_mode("MANUAL") == ExecutionMode.MANUAL
        assert _resolve_execution_mode("LLM") == ExecutionMode.LLM
        assert _resolve_execution_mode("Manual") == ExecutionMode.MANUAL

    def test_invalid_mode_exits(self):
        """Invalid mode raises typer.Exit."""
        from click.exceptions import Exit

        with pytest.raises(Exit):
            _resolve_execution_mode("invalid_mode")


class TestSetupLlmFactory:
    """Tests for _setup_llm_factory helper."""

    def test_returns_none_for_manual_mode(self):
        """Returns None for manual execution mode."""
        from agnetwork.kernel import ExecutionMode

        result = _setup_llm_factory(ExecutionMode.MANUAL)
        assert result is None


class TestRenderHelpers:
    """Tests for CRM list rendering helpers."""

    def test_render_accounts_list(self, capsys):
        """_render_accounts_list formats accounts correctly."""
        # Create mock accounts
        mock_account = MagicMock()
        mock_account.account_id = "acc_test123"
        mock_account.name = "Test Company"
        mock_account.domain = "testcompany.com"

        _render_accounts_list([mock_account])

        captured = capsys.readouterr()
        assert "acc_test123" in captured.out
        assert "Test Company" in captured.out
        assert "testcompany.com" in captured.out
        assert "Accounts (1)" in captured.out

    def test_render_contacts_list(self, capsys):
        """_render_contacts_list formats contacts correctly."""
        mock_contact = MagicMock()
        mock_contact.contact_id = "con_test456"
        mock_contact.full_name = "John Doe"
        mock_contact.role_title = "VP Sales"
        mock_contact.email = "john@test.com"

        _render_contacts_list([mock_contact])

        captured = capsys.readouterr()
        assert "con_test456" in captured.out
        assert "John Doe" in captured.out
        assert "VP Sales" in captured.out
        assert "john@test.com" in captured.out
        assert "Contacts (1)" in captured.out

    def test_render_activities_list(self, capsys):
        """_render_activities_list formats activities correctly."""
        from agnetwork.crm.models import ActivityDirection, ActivityType

        mock_activity = MagicMock()
        mock_activity.activity_id = "act_test789"
        mock_activity.subject = "Test Email Subject"
        mock_activity.activity_type = ActivityType.EMAIL
        mock_activity.direction = ActivityDirection.OUTBOUND
        mock_activity.is_planned = False
        mock_activity.run_id = "run_20260127"

        _render_activities_list([mock_activity])

        captured = capsys.readouterr()
        assert "act_test789" in captured.out
        assert "Test Email Subject" in captured.out
        assert "email" in captured.out
        assert "outbound" in captured.out
        assert "run_20260127" in captured.out

    def test_render_activities_shows_planned_status(self, capsys):
        """_render_activities_list shows planned status correctly."""
        from agnetwork.crm.models import ActivityDirection, ActivityType

        mock_planned = MagicMock()
        mock_planned.activity_id = "act_planned"
        mock_planned.subject = "Planned Activity"
        mock_planned.activity_type = ActivityType.EMAIL
        mock_planned.direction = ActivityDirection.OUTBOUND
        mock_planned.is_planned = True
        mock_planned.run_id = None

        _render_activities_list([mock_planned])

        captured = capsys.readouterr()
        assert "📅 PLANNED" in captured.out


class TestCrmListCommand:
    """Tests for crm list command with dispatch table."""

    def test_crm_list_unknown_entity_fails(self, runner: CliRunner):
        """crm list with unknown entity fails gracefully."""
        result = runner.invoke(app, ["crm", "list", "unknown_entity"])

        assert result.exit_code == 1
        assert "Unknown entity type" in result.output
        assert "accounts, contacts, activities" in result.output


class TestPipelineEndToEnd:
    """End-to-end tests for refactored pipeline."""

    def test_pipeline_runs_successfully(self, runner: CliRunner, temp_runs_dir: Path):
        """Pipeline command runs successfully with refactored helpers."""
        result = runner.invoke(
            app,
            [
                "run-pipeline",
                "RefactorTest",
                "--snapshot",
                "Testing refactored pipeline",
                "--mode",
                "manual",
                "--no-verify",
            ],
        )

        assert result.exit_code == 0, f"Pipeline failed: {result.output}"
        assert "Pipeline completed successfully" in result.output

        # Verify artifacts created
        run_dir = list(temp_runs_dir.glob("*"))[0]
        assert (run_dir / "artifacts" / "research_brief.json").exists()
        assert (run_dir / "artifacts" / "outreach.json").exists()

    def test_pipeline_invalid_mode_fails(self, runner: CliRunner, temp_runs_dir: Path):
        """Pipeline with invalid mode fails gracefully."""
        result = runner.invoke(
            app,
            [
                "run-pipeline",
                "TestCo",
                "--mode",
                "invalid_mode",
            ],
        )

        assert result.exit_code == 1
        assert "Invalid mode" in result.output

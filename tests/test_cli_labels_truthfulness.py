"""Tests for PR4: Truthful CLI Labels.

Verifies that CLI outputs correctly label:
- [LLM] - LLM call was used
- [computed] - Deterministic code (no LLM)
- [placeholder] - Stub/template output
- [fetched] - Network retrieval happened
- [cached] - Result came from cache

All tests are offline and deterministic (no real API keys).
"""

import gc
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Generator
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from agnetwork.cli import app
from agnetwork.cli_labels import (
    StepLabel,
    format_label,
    format_labels,
    format_step_prefix,
    get_mode_labels,
)
from agnetwork.kernel.contracts import SkillMetrics


def _close_loggers():
    """Close all loggers to release file handles (Windows compatibility)."""
    for logger_name in list(logging.Logger.manager.loggerDict):
        if logger_name.startswith("agnetwork."):
            logger = logging.getLogger(logger_name)
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)


@pytest.fixture
def runner() -> CliRunner:
    """Provide a CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_workspace() -> Generator:
    """Set up a temporary workspace with registry for CLI tests.

    This fixture patches WorkspaceRegistry so all CLI commands use the
    temporary workspace.
    """
    from agnetwork.workspaces.registry import WorkspaceRegistry

    with TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        temp_registry_root = Path(tmpdir)

        # Create a test workspace and set as default
        registry = WorkspaceRegistry(registry_root=temp_registry_root)
        test_ws = registry.create_workspace("test_ws")
        registry.set_default_workspace("test_ws")

        # Patch WorkspaceRegistry to use our temp directory
        original_init = WorkspaceRegistry.__init__

        def patched_init(self, registry_root=None):
            original_init(self, registry_root=temp_registry_root)

        WorkspaceRegistry.__init__ = patched_init

        try:
            yield test_ws, registry
        finally:
            WorkspaceRegistry.__init__ = original_init
            _close_loggers()
            gc.collect()


class TestLabelHelpers:
    """Tests for cli_labels.py helper functions."""

    def test_format_label_basic(self):
        """format_label wraps label in brackets."""
        assert format_label(StepLabel.LLM) == "[LLM]"
        assert format_label(StepLabel.COMPUTED) == "[computed]"
        assert format_label(StepLabel.PLACEHOLDER) == "[placeholder]"
        assert format_label(StepLabel.FETCHED) == "[fetched]"
        assert format_label(StepLabel.CACHED) == "[cached]"

    def test_format_labels_multiple(self):
        """format_labels joins multiple labels with spaces."""
        labels = [StepLabel.LLM, StepLabel.CACHED]
        assert format_labels(labels) == "[LLM] [cached]"

    def test_format_labels_empty(self):
        """format_labels returns empty string for empty list."""
        assert format_labels([]) == ""

    def test_format_step_prefix_with_workspace(self):
        """format_step_prefix includes workspace name."""
        mock_ws = MagicMock()
        mock_ws.name = "my_workspace"

        result = format_step_prefix(mock_ws, StepLabel.LLM)
        assert "[workspace: my_workspace]" in result
        assert "[LLM]" in result

    def test_format_step_prefix_without_workspace(self):
        """format_step_prefix works without workspace."""
        result = format_step_prefix(None, StepLabel.PLACEHOLDER)
        assert "[placeholder]" in result
        assert "workspace" not in result

    def test_format_step_prefix_with_extra_labels(self):
        """format_step_prefix includes extra labels."""
        mock_ws = MagicMock()
        mock_ws.name = "ws"

        result = format_step_prefix(mock_ws, StepLabel.LLM, [StepLabel.CACHED])
        assert "[LLM]" in result
        assert "[cached]" in result

    def test_get_mode_labels_llm(self):
        """get_mode_labels returns LLM label for LLM mode."""
        labels = get_mode_labels(is_llm=True)
        assert StepLabel.LLM in labels
        assert StepLabel.COMPUTED not in labels

    def test_get_mode_labels_llm_cached(self):
        """get_mode_labels includes cached when specified."""
        labels = get_mode_labels(is_llm=True, is_cached=True)
        assert StepLabel.LLM in labels
        assert StepLabel.CACHED in labels

    def test_get_mode_labels_computed(self):
        """get_mode_labels returns computed for non-LLM, non-placeholder."""
        labels = get_mode_labels()
        assert StepLabel.COMPUTED in labels

    def test_get_mode_labels_placeholder(self):
        """get_mode_labels returns placeholder when flagged."""
        labels = get_mode_labels(is_placeholder=True)
        assert StepLabel.PLACEHOLDER in labels
        assert StepLabel.LLM not in labels

    def test_get_mode_labels_fetched(self):
        """get_mode_labels returns fetched for fetch operations."""
        labels = get_mode_labels(is_fetched=True)
        assert StepLabel.FETCHED in labels


class TestPlaceholderLabels:
    """Tests for placeholder command labels."""

    def test_outreach_output_contains_placeholder(self, runner, temp_workspace):
        """outreach command output includes [placeholder] label."""
        ws, registry = temp_workspace

        # Registry is patched via fixture, so CLI will use temp workspace
        result = runner.invoke(
            app,
            ["outreach", "TestCo", "--persona", "VP Sales"],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "[placeholder]" in result.output

    def test_prep_output_contains_placeholder(self, runner, temp_workspace):
        """prep command output includes [placeholder] label."""
        ws, registry = temp_workspace

        result = runner.invoke(
            app,
            ["prep", "TestCo", "--type", "discovery"],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "[placeholder]" in result.output

    def test_followup_output_contains_placeholder(self, runner, temp_workspace):
        """followup command output includes [placeholder] label."""
        ws, registry = temp_workspace

        result = runner.invoke(
            app,
            ["followup", "TestCo", "--notes", "Great meeting"],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "[placeholder]" in result.output


class TestMemorySearchLabels:
    """Tests for memory search command labels."""

    def test_memory_search_labels_fts(self, runner, temp_workspace):
        """memory search output includes (FTS) and [computed] labels."""
        ws, registry = temp_workspace

        result = runner.invoke(
            app,
            ["memory", "search", "test query"],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "[computed]" in result.output
        assert "(FTS)" in result.output


class TestResearchLabels:
    """Tests for research command labels."""

    def test_research_output_contains_computed(self, runner, temp_workspace):
        """research command output includes [computed] label."""
        ws, registry = temp_workspace

        result = runner.invoke(
            app,
            ["research", "TestCo", "--snapshot", "A test company"],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "[computed]" in result.output


class TestPipelineModeLabelDistinguishesCached:
    """Tests for pipeline mode label with cached flag."""

    def test_skill_metrics_cached_field_exists(self):
        """SkillMetrics has a cached field defaulting to False."""
        metrics = SkillMetrics()
        assert hasattr(metrics, "cached")
        assert metrics.cached is False

    def test_skill_metrics_cached_can_be_true(self):
        """SkillMetrics cached field can be set to True."""
        metrics = SkillMetrics(cached=True)
        assert metrics.cached is True

    def test_build_mode_label_llm_no_cache(self):
        """_build_mode_label returns [LLM] when no cache."""
        from agnetwork.cli.commands_pipeline import _build_mode_label
        from agnetwork.kernel import ExecutionMode
        from agnetwork.kernel.executor import ExecutionResult

        result = ExecutionResult()
        result.mode = ExecutionMode.LLM

        label = _build_mode_label(result, ExecutionMode.LLM)
        assert label == "[LLM]"
        assert "[cached]" not in label

    def test_build_mode_label_llm_with_cache(self):
        """_build_mode_label returns [LLM] [cached] when cached."""
        from agnetwork.cli.commands_pipeline import _build_mode_label
        from agnetwork.kernel import ExecutionMode
        from agnetwork.kernel.executor import ExecutionResult

        # Create a mock result with cached step
        result = ExecutionResult()
        result.mode = ExecutionMode.LLM

        # Add a step result with cached=True
        mock_skill_result = MagicMock()
        mock_skill_result.metrics = SkillMetrics(cached=True)
        result.step_results["step1"] = mock_skill_result

        label = _build_mode_label(result, ExecutionMode.LLM)
        assert "[LLM]" in label
        assert "[cached]" in label

    def test_build_mode_label_manual(self):
        """_build_mode_label returns [computed] for MANUAL mode."""
        from agnetwork.cli.commands_pipeline import _build_mode_label
        from agnetwork.kernel import ExecutionMode
        from agnetwork.kernel.executor import ExecutionResult

        result = ExecutionResult()
        result.mode = ExecutionMode.MANUAL

        label = _build_mode_label(result, ExecutionMode.MANUAL)
        assert label == "[computed]"


class TestNoExternalProviderFailures:
    """Tests to ensure no provider/API-key failures."""

    def test_placeholder_commands_offline(self, runner, temp_workspace):
        """Placeholder commands work without API keys."""
        ws, registry = temp_workspace

        # All these commands should work offline
        commands = [
            ["outreach", "TestCo", "--persona", "VP"],
            ["prep", "TestCo"],
            ["followup", "TestCo", "--notes", "notes"],
        ]
        for cmd in commands:
            result = runner.invoke(app, cmd)
            assert result.exit_code == 0, f"Command {cmd} failed: {result.output}"
            # Should NOT mention API key errors
            assert "api" not in result.output.lower() or "key" not in result.output.lower()

    def test_memory_search_offline(self, runner, temp_workspace):
        """Memory search works without API keys."""
        ws, registry = temp_workspace

        result = runner.invoke(app, ["memory", "search", "test"])
        assert result.exit_code == 0, f"Failed: {result.output}"
        # FTS search is local, no API needed
        assert "api" not in result.output.lower() or "key" not in result.output.lower()

"""Tests for core orchestrator functionality."""

import json

from agnetwork.orchestrator import RunManager


def test_run_manager_initialization(temp_run_dir):
    """Test that RunManager initializes correctly."""
    # Monkey patch config to use temp directory
    import agnetwork.config

    orig_runs_dir = agnetwork.config.config.runs_dir
    agnetwork.config.config.runs_dir = temp_run_dir

    try:
        run = RunManager(command="test", slug="test_run")

        assert run.run_dir.exists()
        assert (run.run_dir / "sources").exists()
        assert (run.run_dir / "artifacts").exists()
        assert (run.run_dir / "logs").exists()
        assert run.status_path.exists()
        # Worklog is only created after first log action
    finally:
        agnetwork.config.config.runs_dir = orig_runs_dir


def test_run_manager_logging(temp_run_dir):
    """Test that RunManager logs actions correctly."""
    import agnetwork.config

    orig_runs_dir = agnetwork.config.config.runs_dir
    agnetwork.config.config.runs_dir = temp_run_dir

    try:
        run = RunManager(command="test", slug="test_logging")

        run.log_action(
            phase="1",
            action="Test action",
            status="success",
            changes_made=["file1.py"],
        )

        # Check worklog was written
        assert run.worklog_path.exists()
        with open(run.worklog_path, "r") as f:
            lines = f.readlines()
            assert len(lines) > 0
            entry = json.loads(lines[0])
            assert entry["action"] == "Test action"
            assert entry["status"] == "success"
    finally:
        agnetwork.config.config.runs_dir = orig_runs_dir


def test_run_manager_artifacts(temp_run_dir):
    """Test that RunManager saves artifacts correctly."""
    import agnetwork.config

    orig_runs_dir = agnetwork.config.config.runs_dir
    agnetwork.config.config.runs_dir = temp_run_dir

    try:
        run = RunManager(command="test", slug="test_artifacts")

        markdown = "# Test\nThis is a test"
        json_data = {"test": "data", "nested": {"key": "value"}}

        run.save_artifact("test_artifact", markdown, json_data)

        # Check markdown was saved
        md_file = run.run_dir / "artifacts" / "test_artifact.md"
        assert md_file.exists()
        assert md_file.read_text() == markdown

        # Check JSON was saved with meta field
        json_file = run.run_dir / "artifacts" / "test_artifact.json"
        assert json_file.exists()
        with open(json_file, "r") as f:
            saved_data = json.load(f)
            # Original data preserved
            assert saved_data["test"] == "data"
            assert saved_data["nested"] == {"key": "value"}
            # Meta field added
            assert "meta" in saved_data
            assert saved_data["meta"]["artifact_version"] == "1.0"
            assert saved_data["meta"]["run_id"] == run.run_id
    finally:
        agnetwork.config.config.runs_dir = orig_runs_dir

"""Golden run tests for CLI commands.

These tests verify that CLI commands produce expected artifacts with correct structure.
They use temp directories and deterministic inputs to ensure reproducibility.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agnetwork.cli import app


@pytest.fixture
def runner() -> CliRunner:
    """Provide a CLI test runner."""
    return CliRunner()


def get_latest_run(runs_dir: Path) -> Path:
    """Get the most recent run folder."""
    runs = sorted(runs_dir.glob("*"), key=lambda x: x.name, reverse=True)
    assert len(runs) > 0, "No run folders found"
    return runs[0]


def validate_artifact_structure(json_path: Path, required_keys: set) -> dict:
    """Validate that an artifact JSON has required keys and meta block."""
    assert json_path.exists(), f"Artifact JSON not found: {json_path}"

    with open(json_path) as f:
        data = json.load(f)

    # Check required top-level keys
    missing = required_keys - set(data.keys())
    assert not missing, f"Missing required keys: {missing}"

    # Check meta block
    assert "meta" in data, "Missing 'meta' block in artifact"
    meta = data["meta"]

    meta_required = {"artifact_version", "skill_name", "skill_version", "generated_at", "run_id"}
    missing_meta = meta_required - set(meta.keys())
    assert not missing_meta, f"Missing meta keys: {missing_meta}"

    return data


class TestGoldenResearch:
    """Golden tests for the research command."""

    def test_research_creates_run_folder(self, runner: CliRunner, temp_workspace_runs_dir: Path):
        """Test that research command creates proper run folder structure."""
        result = runner.invoke(
            app,
            [
                "research",
                "TestCorp",
                "--snapshot",
                "A test company for golden runs",
                "--pain",
                "Pain point 1",
                "--trigger",
                "Trigger 1",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"

        run_dir = get_latest_run(temp_workspace_runs_dir)

        # Verify folder structure
        assert (run_dir / "sources").is_dir()
        assert (run_dir / "artifacts").is_dir()
        assert (run_dir / "logs").is_dir()

    def test_research_creates_artifacts(self, runner: CliRunner, temp_workspace_runs_dir: Path):
        """Test that research command creates expected artifacts."""
        result = runner.invoke(
            app,
            [
                "research",
                "TestCorp",
                "--snapshot",
                "A test company",
                "--pain",
                "Pain 1",
            ],
        )

        assert result.exit_code == 0

        run_dir = get_latest_run(temp_workspace_runs_dir)
        artifacts_dir = run_dir / "artifacts"

        # Check both MD and JSON exist
        assert (artifacts_dir / "research_brief.md").exists()
        assert (artifacts_dir / "research_brief.json").exists()

        # Validate JSON structure
        data = validate_artifact_structure(
            artifacts_dir / "research_brief.json",
            required_keys={"company", "snapshot", "pains", "triggers", "competitors"},
        )

        assert data["company"] == "TestCorp"
        assert data["meta"]["skill_name"] == "research_brief"

    def test_research_creates_logs(self, runner: CliRunner, temp_workspace_runs_dir: Path):
        """Test that research command creates proper log files."""
        result = runner.invoke(
            app,
            ["research", "TestCorp", "--snapshot", "Test"],
        )

        assert result.exit_code == 0

        run_dir = get_latest_run(temp_workspace_runs_dir)
        logs_dir = run_dir / "logs"

        # Check status file
        assert (logs_dir / "agent_status.json").exists()
        with open(logs_dir / "agent_status.json") as f:
            status = json.load(f)
        assert "session_id" in status
        assert "current_phase" in status

        # Check worklog
        assert (logs_dir / "agent_worklog.jsonl").exists()
        with open(logs_dir / "agent_worklog.jsonl") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        assert len(lines) > 0
        assert all("timestamp" in entry for entry in lines)


class TestGoldenTargets:
    """Golden tests for the targets command."""

    def test_targets_creates_artifacts(self, runner: CliRunner, temp_workspace_runs_dir: Path):
        """Test that targets command creates expected artifacts."""
        result = runner.invoke(app, ["targets", "TestCorp"])

        assert result.exit_code == 0

        run_dir = get_latest_run(temp_workspace_runs_dir)
        artifacts_dir = run_dir / "artifacts"

        assert (artifacts_dir / "target_map.md").exists()
        assert (artifacts_dir / "target_map.json").exists()

        data = validate_artifact_structure(
            artifacts_dir / "target_map.json",
            required_keys={"company", "personas"},
        )

        assert data["company"] == "TestCorp"
        assert data["meta"]["skill_name"] == "target_map"


class TestGoldenOutreach:
    """Golden tests for the outreach command."""

    def test_outreach_creates_artifacts(self, runner: CliRunner, temp_workspace_runs_dir: Path):
        """Test that outreach command creates expected artifacts."""
        result = runner.invoke(
            app,
            ["outreach", "TestCorp", "--persona", "VP Sales", "--channel", "email"],
        )

        assert result.exit_code == 0

        run_dir = get_latest_run(temp_workspace_runs_dir)
        artifacts_dir = run_dir / "artifacts"

        assert (artifacts_dir / "outreach.md").exists()
        assert (artifacts_dir / "outreach.json").exists()

        data = validate_artifact_structure(
            artifacts_dir / "outreach.json",
            required_keys={"company", "persona", "channel"},
        )

        assert data["company"] == "TestCorp"
        assert data["persona"] == "VP Sales"


class TestGoldenPrep:
    """Golden tests for the prep command."""

    def test_prep_creates_artifacts(self, runner: CliRunner, temp_workspace_runs_dir: Path):
        """Test that prep command creates expected artifacts."""
        result = runner.invoke(
            app,
            ["prep", "TestCorp", "--type", "discovery"],
        )

        assert result.exit_code == 0

        run_dir = get_latest_run(temp_workspace_runs_dir)
        artifacts_dir = run_dir / "artifacts"

        assert (artifacts_dir / "meeting_prep.md").exists()
        assert (artifacts_dir / "meeting_prep.json").exists()

        data = validate_artifact_structure(
            artifacts_dir / "meeting_prep.json",
            required_keys={"company", "meeting_type", "agenda"},
        )

        assert data["company"] == "TestCorp"
        assert data["meeting_type"] == "discovery"


class TestGoldenFollowup:
    """Golden tests for the followup command."""

    def test_followup_creates_artifacts(self, runner: CliRunner, temp_workspace_runs_dir: Path):
        """Test that followup command creates expected artifacts."""
        result = runner.invoke(
            app,
            ["followup", "TestCorp", "--notes", "Good meeting, next steps agreed"],
        )

        assert result.exit_code == 0

        run_dir = get_latest_run(temp_workspace_runs_dir)
        artifacts_dir = run_dir / "artifacts"

        assert (artifacts_dir / "followup.md").exists()
        assert (artifacts_dir / "followup.json").exists()

        data = validate_artifact_structure(
            artifacts_dir / "followup.json",
            required_keys={"company", "summary", "next_steps"},
        )

        assert data["company"] == "TestCorp"

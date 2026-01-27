"""Tests for the kernel executor and pipeline command."""

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


class TestPipelineCommand:
    """Tests for the run-pipeline command."""

    def test_pipeline_creates_all_artifacts(self, runner: CliRunner, temp_workspace_runs_dir: Path):
        """Test that pipeline creates all 5 BD artifacts."""
        result = runner.invoke(
            app,
            [
                "run-pipeline",
                "TestCorp",
                "--snapshot",
                "A test company",
                "--pain",
                "Pain 1",
                "--persona",
                "VP Sales",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"

        run_dir = get_latest_run(temp_workspace_runs_dir)
        artifacts_dir = run_dir / "artifacts"

        # Check all 5 artifact pairs exist
        expected_artifacts = [
            "research_brief",
            "target_map",
            "outreach",
            "meeting_prep",
            "followup",
        ]

        for artifact_name in expected_artifacts:
            md_path = artifacts_dir / f"{artifact_name}.md"
            json_path = artifacts_dir / f"{artifact_name}.json"

            assert md_path.exists(), f"Missing {artifact_name}.md"
            assert json_path.exists(), f"Missing {artifact_name}.json"

            # Validate JSON
            with open(json_path) as f:
                data = json.load(f)

            assert "company" in data, f"{artifact_name}.json missing 'company'"
            assert data["company"] == "TestCorp"

            # Check meta block
            assert "meta" in data, f"{artifact_name}.json missing 'meta'"
            assert "skill_name" in data["meta"]
            assert "generated_at" in data["meta"]

    def test_pipeline_creates_proper_logs(self, runner: CliRunner, temp_workspace_runs_dir: Path):
        """Test that pipeline creates proper log files."""
        result = runner.invoke(app, ["run-pipeline", "TestCorp"])

        assert result.exit_code == 0

        run_dir = get_latest_run(temp_workspace_runs_dir)
        logs_dir = run_dir / "logs"

        # Check status file
        status_path = logs_dir / "agent_status.json"
        assert status_path.exists()

        with open(status_path) as f:
            status = json.load(f)

        assert "session_id" in status
        assert status["current_phase"] == "complete"

        # Check worklog
        worklog_path = logs_dir / "agent_worklog.jsonl"
        assert worklog_path.exists()

        with open(worklog_path) as f:
            entries = [json.loads(line) for line in f if line.strip()]

        assert len(entries) > 0
        # Should have entries for plan start, each step, and completion
        assert any("plan" in e.get("phase", "") for e in entries)

    def test_pipeline_run_folder_naming(self, runner: CliRunner, temp_workspace_runs_dir: Path):
        """Test that pipeline run folder is named correctly."""
        result = runner.invoke(app, ["run-pipeline", "Test Corp Inc"])

        assert result.exit_code == 0

        run_dir = get_latest_run(temp_workspace_runs_dir)

        # Should contain company slug and 'pipeline'
        assert "test_corp_inc" in run_dir.name
        assert "pipeline" in run_dir.name

    def test_pipeline_with_no_verify(self, runner: CliRunner, temp_workspace_runs_dir: Path):
        """Test pipeline with verification disabled."""
        result = runner.invoke(
            app,
            ["run-pipeline", "TestCorp", "--no-verify"],
        )

        assert result.exit_code == 0


class TestExecutorWithVerification:
    """Tests for executor with verifier integration."""

    def test_verifier_failure_marks_run_failed(self, temp_config_runs_dir: Path):
        """Test that verification failure marks run as failed."""
        from agnetwork.eval.verifier import Verifier
        from agnetwork.kernel import (
            KernelExecutor,
            SkillResult,
            TaskSpec,
            TaskType,
            skill_registry,
        )
        from agnetwork.kernel.contracts import ArtifactKind, ArtifactRef, Claim, ClaimKind

        # Create a skill that produces invalid output
        class BadSkill:
            name = "bad_skill"
            version = "1.0"

            def run(self, inputs, context):
                return SkillResult(
                    output={},
                    artifacts=[
                        ArtifactRef(
                            name="research_brief",
                            kind=ArtifactKind.JSON,
                            # Missing required 'snapshot' field
                            content=json.dumps({"company": "Test"}),
                        ),
                        ArtifactRef(
                            name="research_brief",
                            kind=ArtifactKind.MARKDOWN,
                            content="# Test",
                        ),
                    ],
                    claims=[
                        Claim(
                            text="This is wrongly marked as fact",
                            kind=ClaimKind.FACT,  # No evidence!
                            evidence=[],
                        )
                    ],
                    skill_name="bad_skill",
                )

        # Register the bad skill temporarily
        original_skill = skill_registry._skill_classes.get("research_brief")
        skill_registry.register("research_brief", BadSkill)

        try:
            task_spec = TaskSpec(
                task_type=TaskType.RESEARCH,
                inputs={"company": "TestCorp"},
            )

            verifier = Verifier()
            executor = KernelExecutor(verifier=verifier)

            result = executor.execute_task(task_spec)

            # Should have failed due to verification
            assert not result.success
            assert len(result.verification_issues) > 0
            assert any(
                i.get("check") in ["claims_labeled", "basic_completeness"]
                for i in result.verification_issues
            )

            # Check that run folder status shows failure
            run_dir = get_latest_run(temp_config_runs_dir)
            status_path = run_dir / "logs" / "agent_status.json"

            with open(status_path) as f:
                status = json.load(f)

            assert status["current_phase"] == "failed"

        finally:
            # Restore original skill
            if original_skill:
                skill_registry.register("research_brief", original_skill)
            else:
                del skill_registry._skill_classes["research_brief"]
            # Clear cached instance
            if "research_brief" in skill_registry._skills:
                del skill_registry._skills["research_brief"]

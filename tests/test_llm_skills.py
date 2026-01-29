"""Tests for LLM-mode skill execution."""

import json

import pytest
from typer.testing import CliRunner

from agnetwork.cli import app
from agnetwork.kernel.contracts import SkillContext
from agnetwork.kernel.llm_executor import LLMSkillError, LLMSkillExecutor
from agnetwork.tools.llm.adapters.fake import (
    FAKE_FOLLOWUP,
    FAKE_MEETING_PREP,
    FAKE_OUTREACH,
    FAKE_RESEARCH_BRIEF,
    FAKE_TARGET_MAP,
    FakeAdapter,
)
from agnetwork.tools.llm.factory import LLMConfig, LLMFactory, RoleConfig


@pytest.fixture
def fake_factory() -> LLMFactory:
    """Create a factory with fake adapters for all roles."""
    config = LLMConfig(
        enabled=True,
        roles={
            "default": RoleConfig(provider="fake", model="fake"),
            "draft": RoleConfig(provider="fake", model="fake"),
            "critic": RoleConfig(provider="fake", model="fake"),
        },
    )
    factory = LLMFactory(config)

    # Create fake adapters with preset responses
    # NOTE: Patterns must be unique enough to avoid conflicts
    # "follow-up" is more specific than "follow" to avoid matching "meeting"
    draft_fake = FakeAdapter()
    draft_fake.add_response("research brief", FAKE_RESEARCH_BRIEF)
    draft_fake.add_response("target map", FAKE_TARGET_MAP)
    draft_fake.add_response("outreach", FAKE_OUTREACH)
    draft_fake.add_response("meeting prep", FAKE_MEETING_PREP)
    draft_fake.add_response("follow-up", FAKE_FOLLOWUP)
    factory.set_adapter("draft", draft_fake)

    # Critic returns "passed" by default
    critic_fake = FakeAdapter(default_response='{"passed": true, "issues": []}')
    factory.set_adapter("critic", critic_fake)

    return factory


@pytest.fixture
def llm_executor(fake_factory) -> LLMSkillExecutor:
    """Create an LLM executor with fake adapters."""
    return LLMSkillExecutor(
        llm_factory=fake_factory,
        enable_critic=False,  # Disable critic for basic tests
        max_repairs=2,
    )


@pytest.fixture
def context() -> SkillContext:
    """Create a test skill context."""
    return SkillContext(
        run_id="test-run-123",
        workspace="work",
    )


class TestLLMSkillExecutor:
    """Tests for LLMSkillExecutor."""

    def test_research_brief_generation(self, llm_executor, context):
        """Test research brief generation in LLM mode."""
        inputs = {
            "company": "TestCorp",
            "snapshot": "A technology company",
            "pains": ["Pain 1"],
            "triggers": ["Trigger 1"],
            "competitors": ["Competitor 1"],
        }

        result = llm_executor.execute_research_brief(inputs, context)

        assert result.skill_name == "research_brief"
        assert len(result.artifacts) == 2  # MD and JSON

        # Check JSON artifact
        json_artifact = result.get_json_artifact()
        assert json_artifact is not None
        data = json.loads(json_artifact.content)
        assert data["company"] == "TestCorp"

        # Check claims extracted
        assert len(result.claims) > 0

    def test_target_map_generation(self, llm_executor, context):
        """Test target map generation in LLM mode."""
        inputs = {
            "company": "TestCorp",
        }

        result = llm_executor.execute_target_map(inputs, context)

        assert result.skill_name == "target_map"
        json_artifact = result.get_json_artifact()
        data = json.loads(json_artifact.content)
        assert "personas" in data
        assert len(data["personas"]) > 0

    def test_outreach_generation(self, llm_executor, context):
        """Test outreach generation in LLM mode."""
        inputs = {
            "company": "TestCorp",
            "persona": "VP Sales",
            "channel": "email",
        }

        result = llm_executor.execute_outreach(inputs, context)

        assert result.skill_name == "outreach"
        json_artifact = result.get_json_artifact()
        data = json.loads(json_artifact.content)
        assert data["persona"] == "VP Sales"
        assert "variants" in data

    def test_meeting_prep_generation(self, llm_executor, context):
        """Test meeting prep generation in LLM mode."""
        inputs = {
            "company": "TestCorp",
            "meeting_type": "discovery",
        }

        result = llm_executor.execute_meeting_prep(inputs, context)

        assert result.skill_name == "meeting_prep"
        json_artifact = result.get_json_artifact()
        data = json.loads(json_artifact.content)
        assert data["meeting_type"] == "discovery"
        assert "agenda" in data

    def test_followup_generation(self, llm_executor, context):
        """Test follow-up generation in LLM mode."""
        inputs = {
            "company": "TestCorp",
            "notes": "Good meeting",
        }

        result = llm_executor.execute_followup(inputs, context)

        assert result.skill_name == "followup"
        json_artifact = result.get_json_artifact()
        data = json.loads(json_artifact.content)
        assert data["company"] == "TestCorp"
        assert "next_steps" in data

    def test_markdown_output_consistency(self, llm_executor, context):
        """Test that markdown output follows expected format."""
        inputs = {
            "company": "TestCorp",
            "snapshot": "A test company",
        }

        result = llm_executor.execute_research_brief(inputs, context)

        md_artifact = result.get_markdown_artifact()
        assert md_artifact is not None
        assert "# Account Research Brief: TestCorp" in md_artifact.content
        assert "## Snapshot" in md_artifact.content


class TestLLMSkillWithCritic:
    """Tests for LLM skills with critic pass enabled."""

    def test_critic_pass_improves_output(self, fake_factory, context):
        """Test that critic pass can improve output."""
        # Set up critic to return patched JSON
        critic = fake_factory.get("critic")
        patched = json.loads(FAKE_RESEARCH_BRIEF)
        patched["personalization_angles"].append(
            {
                "name": "Critic Added",
                "fact": "This was added by the critic",
                "is_assumption": True,
            }
        )
        critic.queue_response(
            json.dumps(
                {
                    "passed": True,
                    "issues": [],
                    "patched_json": patched,
                }
            )
        )

        executor = LLMSkillExecutor(
            llm_factory=fake_factory,
            enable_critic=True,
            max_repairs=2,
        )

        result = executor.execute_research_brief(
            {"company": "TestCorp", "snapshot": "Test"},
            context,
        )

        json_artifact = result.get_json_artifact()
        data = json.loads(json_artifact.content)

        # Check critic's patch was applied
        angle_names = [a["name"] for a in data["personalization_angles"]]
        assert "Critic Added" in angle_names


class TestLLMSkillErrorHandling:
    """Tests for LLM skill error handling."""

    def test_invalid_json_triggers_repair(self, fake_factory, context):
        """Test that invalid JSON triggers repair loop."""
        # Override draft to return invalid JSON first
        draft = fake_factory.get("draft")
        draft.reset()
        draft.queue_response("not valid json at all")

        # Repair loop uses critic adapter to fix JSON
        critic = fake_factory.get("critic")
        critic.reset()
        critic.queue_response(FAKE_RESEARCH_BRIEF)  # Critic returns fixed JSON

        executor = LLMSkillExecutor(
            llm_factory=fake_factory,
            enable_critic=False,
            max_repairs=2,
        )

        # This should succeed after repair via critic
        result = executor.execute_research_brief(
            {"company": "TestCorp"},
            context,
        )

        assert result is not None
        assert result.skill_name == "research_brief"

    def test_persistent_failure_raises_error(self, fake_factory, context):
        """Test that persistent failure raises LLMSkillError."""
        # Override to always return invalid
        draft = fake_factory.get("draft")
        draft.reset()
        draft.set_response_fn(lambda r: "always invalid")

        # Critic also returns invalid
        critic = fake_factory.get("critic")
        critic.reset()
        critic.set_response_fn(lambda r: "still invalid")

        executor = LLMSkillExecutor(
            llm_factory=fake_factory,
            enable_critic=False,
            max_repairs=1,
        )

        with pytest.raises(LLMSkillError) as exc_info:
            executor.execute_research_brief(
                {"company": "TestCorp"},
                context,
            )

        assert "research_brief" in exc_info.value.skill_name


class TestCLILLMMode:
    """Tests for CLI with LLM mode."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Provide a CLI test runner."""
        return CliRunner()

    def test_manual_mode_default(self, runner, temp_workspace_runs_dir):
        """Test that manual mode is the default."""
        result = runner.invoke(
            app,
            ["run-pipeline", "TestCorp", "--snapshot", "Test"],
        )

        # Should succeed in manual mode
        assert result.exit_code == 0
        assert "manual" in result.output.lower() or "completed" in result.output.lower()

    def test_invalid_mode_rejected(self, runner, temp_workspace_runs_dir):
        """Test that invalid mode is rejected."""
        result = runner.invoke(
            app,
            ["run-pipeline", "TestCorp", "--mode", "invalid_mode"],
        )

        assert result.exit_code == 1
        assert "invalid mode" in result.output.lower()

    def test_llm_mode_requires_enabled(self, runner, temp_workspace_runs_dir):
        """Test that LLM mode requires AG_LLM_ENABLED=1."""
        # Without setting AG_LLM_ENABLED
        result = runner.invoke(
            app,
            ["run-pipeline", "TestCorp", "--mode", "llm"],
            env={"AG_LLM_ENABLED": "0"},
        )

        assert result.exit_code == 1
        assert "AG_LLM_ENABLED" in result.output


class TestManualModeUnchanged:
    """Tests to verify manual mode is unchanged."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_pipeline_still_works_without_llm(self, runner, temp_workspace_runs_dir):
        """Test pipeline works with no LLM config at all."""
        result = runner.invoke(
            app,
            [
                "run-pipeline",
                "TestCorp",
                "--snapshot",
                "Test company",
                "--pain",
                "Pain 1",
            ],
        )

        assert result.exit_code == 0
        assert "completed" in result.output.lower()

        # Check artifacts were created
        runs = list(temp_workspace_runs_dir.glob("*"))
        assert len(runs) == 1
        artifacts_dir = runs[0] / "artifacts"
        assert (artifacts_dir / "research_brief.json").exists()
        assert (artifacts_dir / "target_map.json").exists()

    def test_research_command_unchanged(self, runner, temp_workspace_runs_dir):
        """Test standalone research command still works."""
        result = runner.invoke(
            app,
            [
                "research",
                "TestCorp",
                "--snapshot",
                "A test company",
            ],
        )

        assert result.exit_code == 0
        assert "research brief generated" in result.output.lower()

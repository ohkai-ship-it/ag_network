"""Tests for kernel models and planner."""

from agnetwork.kernel import (
    Constraints,
    Plan,
    Planner,
    Step,
    StepStatus,
    TaskSpec,
    TaskType,
    Workspace,
)


class TestTaskSpec:
    """Tests for TaskSpec model."""

    def test_task_spec_creation(self):
        """Test creating a TaskSpec."""
        spec = TaskSpec(
            task_type=TaskType.RESEARCH,
            inputs={"company": "TestCorp", "snapshot": "Test company"},
        )

        assert spec.task_type == TaskType.RESEARCH
        assert spec.workspace == Workspace.WORK
        assert spec.inputs["company"] == "TestCorp"
        assert spec.get_company() == "TestCorp"
        assert spec.get_slug() == "testcorp"

    def test_task_spec_with_constraints(self):
        """Test TaskSpec with constraints."""
        spec = TaskSpec(
            task_type=TaskType.OUTREACH,
            inputs={"company": "TestCorp"},
            constraints=Constraints(tone="formal", language="en"),
        )

        assert spec.constraints.tone == "formal"
        assert spec.constraints.language == "en"

    def test_task_spec_pipeline_type(self):
        """Test pipeline task type."""
        spec = TaskSpec(
            task_type=TaskType.PIPELINE,
            inputs={"company": "TestCorp"},
        )

        assert spec.task_type == TaskType.PIPELINE

    def test_task_spec_slug_handles_spaces(self):
        """Test that slug handles company names with spaces."""
        spec = TaskSpec(
            task_type=TaskType.RESEARCH,
            inputs={"company": "Test Corp Inc"},
        )

        assert spec.get_slug() == "test_corp_inc"


class TestStep:
    """Tests for Step model."""

    def test_step_creation(self):
        """Test creating a Step."""
        step = Step(
            step_id="step_1",
            skill_name="research_brief",
            expected_artifacts=["research_brief.md", "research_brief.json"],
        )

        assert step.step_id == "step_1"
        assert step.skill_name == "research_brief"
        assert step.status == StepStatus.PENDING
        assert len(step.expected_artifacts) == 2

    def test_step_status_transitions(self):
        """Test step status transitions."""
        step = Step(step_id="step_1", skill_name="test_skill")

        assert step.status == StepStatus.PENDING

        step.mark_running()
        assert step.status == StepStatus.RUNNING
        assert step.started_at is not None

        step.mark_completed()
        assert step.status == StepStatus.COMPLETED
        assert step.completed_at is not None

    def test_step_failure(self):
        """Test marking step as failed."""
        step = Step(step_id="step_1", skill_name="test_skill")
        step.mark_running()
        step.mark_failed("Test error")

        assert step.status == StepStatus.FAILED
        assert step.error == "Test error"
        assert step.completed_at is not None


class TestPlan:
    """Tests for Plan model."""

    def test_plan_creation(self):
        """Test creating a Plan."""
        spec = TaskSpec(
            task_type=TaskType.RESEARCH,
            inputs={"company": "TestCorp"},
        )

        plan = Plan(
            plan_id="test_plan",
            task_spec=spec,
            steps=[
                Step(step_id="step_1", skill_name="research_brief"),
            ],
        )

        assert plan.plan_id == "test_plan"
        assert len(plan.steps) == 1

    def test_plan_get_next_step(self):
        """Test getting next pending step."""
        spec = TaskSpec(task_type=TaskType.PIPELINE, inputs={"company": "Test"})
        plan = Plan(
            plan_id="test",
            task_spec=spec,
            steps=[
                Step(step_id="step_1", skill_name="skill_a"),
                Step(step_id="step_2", skill_name="skill_b", depends_on=["step_1"]),
            ],
        )

        # First step should be available
        next_step = plan.get_next_step()
        assert next_step.step_id == "step_1"

        # After completing step_1, step_2 should be available
        plan.steps[0].mark_completed()
        next_step = plan.get_next_step()
        assert next_step.step_id == "step_2"

    def test_plan_is_complete(self):
        """Test plan completion check."""
        spec = TaskSpec(task_type=TaskType.RESEARCH, inputs={"company": "Test"})
        plan = Plan(
            plan_id="test",
            task_spec=spec,
            steps=[Step(step_id="step_1", skill_name="test")],
        )

        assert not plan.is_complete()

        plan.steps[0].mark_completed()
        assert plan.is_complete()

    def test_plan_has_failed(self):
        """Test plan failure check."""
        spec = TaskSpec(task_type=TaskType.RESEARCH, inputs={"company": "Test"})
        plan = Plan(
            plan_id="test",
            task_spec=spec,
            steps=[Step(step_id="step_1", skill_name="test")],
        )

        assert not plan.has_failed()

        plan.steps[0].mark_failed("Error")
        assert plan.has_failed()


class TestPlanner:
    """Tests for Planner."""

    def test_create_plan_for_research(self):
        """Test creating plan for research task."""
        planner = Planner()
        spec = TaskSpec(
            task_type=TaskType.RESEARCH,
            inputs={"company": "TestCorp"},
        )

        plan = planner.create_plan(spec)

        assert len(plan.steps) == 1
        assert plan.steps[0].skill_name == "research_brief"
        assert "research_brief.md" in plan.steps[0].expected_artifacts

    def test_create_plan_for_pipeline(self):
        """Test creating plan for full pipeline."""
        planner = Planner()
        spec = TaskSpec(
            task_type=TaskType.PIPELINE,
            inputs={"company": "TestCorp"},
        )

        plan = planner.create_plan(spec)

        # Pipeline should have 5 steps
        assert len(plan.steps) == 5

        skill_names = [s.skill_name for s in plan.steps]
        assert "research_brief" in skill_names
        assert "target_map" in skill_names
        assert "outreach" in skill_names
        assert "meeting_prep" in skill_names
        assert "followup" in skill_names

        # Check dependencies are set up correctly
        for i, step in enumerate(plan.steps):
            if i > 0:
                assert plan.steps[i - 1].step_id in step.depends_on

    def test_create_plan_with_requested_artifacts(self):
        """Test filtering plan by requested artifacts."""
        planner = Planner()
        spec = TaskSpec(
            task_type=TaskType.PIPELINE,
            inputs={"company": "TestCorp"},
            requested_artifacts=["research_brief", "outreach"],
        )

        plan = planner.create_plan(spec)

        skill_names = [s.skill_name for s in plan.steps]
        assert "research_brief" in skill_names
        assert "outreach" in skill_names

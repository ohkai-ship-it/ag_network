"""Planner module for creating execution plans from task specifications.

The planner takes a TaskSpec and creates a Plan with appropriate steps
based on the task type. This is a deterministic planner for M2.
"""

from datetime import datetime, timezone
from typing import Dict, List
from uuid import uuid4

from agnetwork.kernel.models import Plan, Step, TaskSpec, TaskType


class Planner:
    """Creates execution plans from task specifications.

    This is a deterministic planner that maps task types to
    predefined skill sequences. LLM-based planning comes in M3+.
    """

    # Maps task types to their skill sequences
    TASK_SKILL_MAP: Dict[TaskType, List[str]] = {
        TaskType.RESEARCH: ["research_brief"],
        TaskType.TARGETS: ["target_map"],
        TaskType.OUTREACH: ["outreach"],
        TaskType.PREP: ["meeting_prep"],
        TaskType.FOLLOWUP: ["followup"],
        TaskType.PIPELINE: [
            "research_brief",
            "target_map",
            "outreach",
            "meeting_prep",
            "followup",
        ],
    }

    # Maps skills to their expected artifacts
    SKILL_ARTIFACTS: Dict[str, List[str]] = {
        "research_brief": ["research_brief.md", "research_brief.json"],
        "target_map": ["target_map.md", "target_map.json"],
        "outreach": ["outreach.md", "outreach.json"],
        "meeting_prep": ["meeting_prep.md", "meeting_prep.json"],
        "followup": ["followup.md", "followup.json"],
    }

    def create_plan(self, task_spec: TaskSpec) -> Plan:
        """Create an execution plan from a task specification.

        Args:
            task_spec: The task specification to plan for

        Returns:
            A Plan with steps to execute
        """
        plan_id = f"plan_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"

        steps = self._create_steps_for_task(task_spec)

        return Plan(
            plan_id=plan_id,
            task_spec=task_spec,
            steps=steps,
        )

    def _create_steps_for_task(self, task_spec: TaskSpec) -> List[Step]:
        """Create steps for a task type.

        Args:
            task_spec: The task specification

        Returns:
            List of steps to execute
        """
        skill_names = self.TASK_SKILL_MAP.get(task_spec.task_type, [])

        # Filter by requested artifacts if specified
        if task_spec.requested_artifacts:
            skill_names = self._filter_skills_by_artifacts(
                skill_names, task_spec.requested_artifacts
            )

        steps = []
        previous_step_id = None

        for i, skill_name in enumerate(skill_names):
            step_id = f"step_{i + 1}_{skill_name}"

            # Build dependencies - each step depends on the previous
            depends_on = [previous_step_id] if previous_step_id else []

            # Build input references based on task inputs
            input_ref = self._build_input_ref(skill_name, task_spec)

            step = Step(
                step_id=step_id,
                skill_name=skill_name,
                input_ref=input_ref,
                depends_on=depends_on,
                expected_artifacts=self.SKILL_ARTIFACTS.get(skill_name, []),
            )
            steps.append(step)
            previous_step_id = step_id

        return steps

    def _filter_skills_by_artifacts(
        self, skill_names: List[str], requested_artifacts: List[str]
    ) -> List[str]:
        """Filter skill names to only those producing requested artifacts.

        Args:
            skill_names: List of skill names
            requested_artifacts: List of requested artifact names

        Returns:
            Filtered list of skill names
        """
        filtered = []
        for skill_name in skill_names:
            skill_artifacts = self.SKILL_ARTIFACTS.get(skill_name, [])
            # Check if any artifact matches (by base name without extension)
            for artifact in skill_artifacts:
                base_name = artifact.rsplit(".", 1)[0]
                if base_name in requested_artifacts or artifact in requested_artifacts:
                    filtered.append(skill_name)
                    break
        return filtered or skill_names  # Return all if no match

    def _build_input_ref(self, skill_name: str, task_spec: TaskSpec) -> Dict:
        """Build input references for a skill.

        Maps task inputs to skill-specific inputs.

        Args:
            skill_name: Name of the skill
            task_spec: The task specification

        Returns:
            Dict of input references
        """
        inputs = task_spec.inputs.copy()

        # Add common inputs
        inputs["workspace"] = task_spec.workspace.value
        inputs["constraints"] = task_spec.constraints.model_dump()

        return inputs

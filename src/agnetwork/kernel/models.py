"""Kernel models for task specification and planning.

This module defines the core models used by the kernel to:
- Accept task specifications (TaskSpec)
- Create execution plans (Plan)
- Track individual steps (Step)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass


class TaskType(str, Enum):
    """Types of tasks the agent kernel can execute."""

    RESEARCH = "research"
    TARGETS = "targets"
    OUTREACH = "outreach"
    PREP = "prep"
    FOLLOWUP = "followup"
    PIPELINE = "pipeline"  # Full BD pipeline


class ExecutionMode(str, Enum):
    """Execution mode for the kernel.

    - MANUAL: Deterministic mode using template-based generation (default)
    - LLM: LLM-assisted generation with structured output validation
    """

    MANUAL = "manual"
    LLM = "llm"


class Workspace(str, Enum):
    """Workspace context for task execution."""

    WORK = "work"
    PERSONAL = "personal"


class Constraints(BaseModel):
    """Constraints on task execution and output."""

    tone: Optional[str] = None  # e.g., "formal", "casual", "professional"
    language: str = "en"
    max_length: Optional[int] = None  # Maximum length for output artifacts
    custom: Dict[str, Any] = Field(default_factory=dict)


class TaskSpec(BaseModel):
    """Specification for a task to be executed by the kernel.

    TaskSpec represents the input to the kernel. It defines what
    needs to be done, with what inputs, and under what constraints.
    """

    task_type: TaskType
    workspace: Workspace = Workspace.WORK
    inputs: Dict[str, Any] = Field(default_factory=dict)
    constraints: Constraints = Field(default_factory=Constraints)
    requested_artifacts: List[str] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    context: Dict[str, Any] = Field(default_factory=dict)  # Additional context

    # M7.1: Optional workspace context for scoped runs
    # Using Any to avoid circular import; actual type is WorkspaceContext
    workspace_context: Optional[Any] = Field(default=None, exclude=True)

    model_config = {"arbitrary_types_allowed": True}

    def get_company(self) -> Optional[str]:
        """Extract company name from inputs."""
        return self.inputs.get("company")

    def get_slug(self) -> str:
        """Get a URL-safe slug for this task."""
        company = self.get_company() or "unknown"
        return company.lower().replace(" ", "_")


class StepStatus(str, Enum):
    """Status of a plan step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Step(BaseModel):
    """A single step in an execution plan.

    Steps are executed sequentially or in parallel based on dependencies.
    Each step invokes a skill with specific inputs.
    """

    step_id: str
    skill_name: str
    input_ref: Dict[str, Any] = Field(default_factory=dict)  # Input mapping
    depends_on: List[str] = Field(default_factory=list)  # Step IDs this depends on
    expected_artifacts: List[str] = Field(
        default_factory=list
    )  # e.g., ["research_brief.md", "research_brief.json"]

    # Runtime state
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    def mark_running(self) -> None:
        """Mark this step as running."""
        self.status = StepStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)

    def mark_completed(self) -> None:
        """Mark this step as completed."""
        self.status = StepStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)

    def mark_failed(self, error: str) -> None:
        """Mark this step as failed."""
        self.status = StepStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.error = error


class Plan(BaseModel):
    """An execution plan for a task.

    A Plan consists of ordered steps that need to be executed.
    The kernel uses this to orchestrate skill execution.
    """

    plan_id: str
    task_spec: TaskSpec
    steps: List[Step] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def get_next_step(self) -> Optional[Step]:
        """Get the next pending step that has all dependencies satisfied."""
        completed_ids = {s.step_id for s in self.steps if s.status == StepStatus.COMPLETED}

        for step in self.steps:
            if step.status == StepStatus.PENDING:
                # Check if all dependencies are completed
                if all(dep in completed_ids for dep in step.depends_on):
                    return step
        return None

    def is_complete(self) -> bool:
        """Check if all steps are completed."""
        return all(s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED) for s in self.steps)

    def has_failed(self) -> bool:
        """Check if any step has failed."""
        return any(s.status == StepStatus.FAILED for s in self.steps)

    def mark_started(self) -> None:
        """Mark the plan as started."""
        self.started_at = datetime.now(timezone.utc)

    def mark_completed(self) -> None:
        """Mark the plan as completed."""
        self.completed_at = datetime.now(timezone.utc)

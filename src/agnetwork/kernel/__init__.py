"""Kernel module for task specification, planning, and execution."""

from agnetwork.kernel.contracts import (
    ArtifactKind,
    ArtifactRef,
    Claim,
    ClaimKind,
    NextAction,
    Skill,
    SkillContext,
    SkillMetrics,
    SkillResult,
    SourceRef,
)
from agnetwork.kernel.executor import (
    ExecutionResult,
    KernelExecutor,
    register_skill,
    skill_registry,
)
from agnetwork.kernel.models import (
    Constraints,
    ExecutionMode,
    Plan,
    Step,
    StepStatus,
    TaskSpec,
    TaskType,
    Workspace,
)
from agnetwork.kernel.planner import Planner

__all__ = [
    # Models
    "TaskSpec",
    "TaskType",
    "Workspace",
    "Constraints",
    "Plan",
    "Step",
    "StepStatus",
    # Contracts
    "Skill",
    "SkillContext",
    "SkillResult",
    "SkillMetrics",
    "SourceRef",
    "Claim",
    "ClaimKind",
    "ArtifactRef",
    "ArtifactKind",
    "NextAction",
    # Planner
    "Planner",
    # Executor
    "KernelExecutor",
    "ExecutionResult",
    "ExecutionMode",
    "skill_registry",
    "register_skill",
]

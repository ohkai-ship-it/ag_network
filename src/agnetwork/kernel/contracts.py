"""Skill contracts and standard interfaces.

This module defines the standard contract that all skills must follow:
- SkillContext: Runtime context passed to skills
- SkillResult: Standard result type returned by skills
- Skill: Protocol defining the skill interface
- Supporting types: SourceRef, Claim, ArtifactRef

M4 additions:
- EvidenceBundle integration in SkillContext
- Claim.source_ids property for evidence tracking
"""

from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from pydantic import BaseModel, Field

# Note: EvidenceBundle is accessed via Any to avoid circular import with storage.memory


class ClaimKind(str, Enum):
    """Type of claim being made."""

    FACT = "fact"  # Verified from source
    ASSUMPTION = "assumption"  # Assumed without evidence
    INFERENCE = "inference"  # Inferred from other facts


class SourceRef(BaseModel):
    """Reference to a stored source.

    Used to link claims and facts back to their source material.
    """

    source_id: str
    source_type: str = "unknown"  # "url", "text", "file", etc.
    title: Optional[str] = None
    uri: Optional[str] = None
    excerpt: Optional[str] = None  # Relevant excerpt from source


class Claim(BaseModel):
    """A claim or statement made by a skill.

    Claims track the provenance of facts and assumptions
    to maintain traceability.
    """

    text: str
    kind: ClaimKind
    evidence: List[SourceRef] = Field(default_factory=list)
    confidence: Optional[float] = None  # 0.0 to 1.0

    def is_sourced(self) -> bool:
        """Check if this claim has evidence."""
        return len(self.evidence) > 0

    def validate_kind(self) -> bool:
        """Validate that claim kind matches evidence status."""
        if self.kind == ClaimKind.FACT:
            return self.is_sourced()
        return True  # Assumptions and inferences don't require evidence

    @property
    def source_ids(self) -> List[str]:
        """Get list of source IDs from evidence.

        Returns:
            List of source IDs referenced by this claim's evidence.
        """
        return [e.source_id for e in self.evidence]


class ArtifactKind(str, Enum):
    """Type of artifact produced."""

    MARKDOWN = "markdown"
    JSON = "json"


class ArtifactRef(BaseModel):
    """Reference to an artifact that should be written.

    Skills produce artifact refs; the orchestrator writes them.
    """

    name: str  # e.g., "research_brief"
    kind: ArtifactKind
    content: str  # The actual content to write
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def filename(self) -> str:
        """Get the filename for this artifact."""
        ext = ".md" if self.kind == ArtifactKind.MARKDOWN else ".json"
        return f"{self.name}{ext}"


class SkillContext(BaseModel):
    """Context passed to skills during execution.

    Contains runtime information needed by skills.
    M4: Added evidence_bundle for memory retrieval support.
    """

    run_id: str
    workspace: str = "work"
    config: Dict[str, Any] = Field(default_factory=dict)
    sources: List[SourceRef] = Field(default_factory=list)

    # Inputs from previous steps (for multi-step pipelines)
    step_inputs: Dict[str, Any] = Field(default_factory=dict)

    # M4: Evidence bundle from memory retrieval (when enabled)
    # Using Any to avoid circular import; actual type is EvidenceBundle
    evidence_bundle: Optional[Any] = None

    # M4: Flag indicating if memory retrieval was used
    memory_enabled: bool = False

    model_config = {"arbitrary_types_allowed": True}


class NextAction(BaseModel):
    """Suggested next action from a skill result."""

    action_type: str  # e.g., "skill", "user_input", "verification"
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class SkillMetrics(BaseModel):
    """Metrics from skill execution.

    Attributes:
        execution_time_ms: Time taken to execute skill in milliseconds
        input_tokens: Number of input tokens (LLM calls only)
        output_tokens: Number of output tokens (LLM calls only)
        cached: Whether result was served from cache (no new LLM/fetch call)
        custom: Additional custom metrics
    """

    execution_time_ms: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cached: bool = False  # PR4: Track if result came from cache
    custom: Dict[str, Any] = Field(default_factory=dict)


# Generic type for skill output
T = TypeVar("T", bound=BaseModel)


class SkillResult(BaseModel, Generic[T]):
    """Standard result type returned by all skills.

    Skills must return a SkillResult containing:
    - output: The typed output model
    - artifacts: List of artifacts to write
    - claims: List of claims made (for traceability)
    - warnings: Any warnings generated
    - next_actions: Suggested follow-up actions
    - metrics: Execution metrics
    """

    output: Any  # The typed output (T) - using Any for Pydantic compatibility
    artifacts: List[ArtifactRef] = Field(default_factory=list)
    claims: List[Claim] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    next_actions: List[NextAction] = Field(default_factory=list)
    metrics: SkillMetrics = Field(default_factory=SkillMetrics)

    # Metadata
    skill_name: str = ""
    skill_version: str = "1.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def get_artifact(self, name: str) -> Optional[ArtifactRef]:
        """Get artifact by name."""
        for artifact in self.artifacts:
            if artifact.name == name:
                return artifact
        return None

    def has_errors(self) -> bool:
        """Check if result has any errors (warnings are not errors)."""
        return False  # Override in subclass if needed

    def get_json_artifact(self) -> Optional[ArtifactRef]:
        """Get the first JSON artifact."""
        for artifact in self.artifacts:
            if artifact.kind == ArtifactKind.JSON:
                return artifact
        return None

    def get_markdown_artifact(self) -> Optional[ArtifactRef]:
        """Get the first Markdown artifact."""
        for artifact in self.artifacts:
            if artifact.kind == ArtifactKind.MARKDOWN:
                return artifact
        return None


@runtime_checkable
class Skill(Protocol):
    """Protocol defining the standard skill interface.

    All skills must implement this protocol. Skills are:
    - Side-effect free: No direct file/db/network writes
    - Deterministic: Same inputs produce same outputs (no LLM in M2)
    - Traceable: Claims link back to sources
    """

    @property
    def name(self) -> str:
        """Unique name identifying this skill."""
        ...

    @property
    def version(self) -> str:
        """Version of this skill."""
        ...

    def run(self, inputs: Dict[str, Any], context: SkillContext) -> SkillResult:
        """Execute the skill with given inputs and context.

        Args:
            inputs: Skill-specific input parameters
            context: Runtime context with run_id, workspace, etc.

        Returns:
            SkillResult containing output, artifacts, claims, etc.
        """
        ...


# Type alias for skill factory functions
SkillFactory = type[Skill]

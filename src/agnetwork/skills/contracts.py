"""Skill contracts re-exported from kernel.

This module provides convenience imports for skill contracts.
The canonical implementation lives in `agnetwork.kernel.contracts`.

For new code, prefer importing directly from `agnetwork.kernel.contracts`,
but this re-export is maintained for backward compatibility and convenience.
"""

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

__all__ = [
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
]

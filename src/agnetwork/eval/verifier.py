"""Verifier layer for skill result validation.

This module provides verification for skill results to ensure:
- Required artifact refs exist
- JSON output validates against Pydantic schemas
- Meta/version fields exist
- Claims are properly labeled
- Basic completeness checks

M4 additions:
- Evidence consistency checks for claims
- Memory-enabled verification mode
"""

import json
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field, ValidationError

from agnetwork.kernel.contracts import (
    ArtifactKind,
    ArtifactRef,
    ClaimKind,
    SkillResult,
)
from agnetwork.models.core import (
    FollowUpSummary,
    MeetingPrepPack,
    OutreachDraft,
    ResearchBrief,
    TargetMap,
)


class IssueSeverity(str, Enum):
    """Severity of a verification issue."""

    ERROR = "error"  # Fails the run
    WARNING = "warning"  # Logged but doesn't fail


class Issue(BaseModel):
    """A verification issue found in a skill result."""

    check: str  # Name of the check that failed
    message: str
    severity: IssueSeverity
    artifact_name: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "check": self.check,
            "message": self.message,
            "severity": self.severity.value,
            "artifact_name": self.artifact_name,
            "details": self.details,
        }


class Verifier:
    """Verifies skill results for correctness and completeness.

    The verifier performs these checks:
    1. artifact_refs_exist: All expected artifacts are present
    2. json_validates: JSON artifacts parse as valid JSON
    3. schema_validates: JSON artifacts validate against Pydantic output models
    4. claims_labeled: Claims without evidence are labeled assumption/inference
    5. basic_completeness: Artifacts have minimum required fields
    6. (M4) evidence_consistency: Facts have evidence when memory is enabled
    """

    # Required fields per artifact type (light checks)
    REQUIRED_FIELDS: Dict[str, List[str]] = {
        "research_brief": ["company", "snapshot"],
        "target_map": ["company", "personas"],
        "outreach": ["company", "persona", "channel"],
        "meeting_prep": ["company", "meeting_type", "agenda"],
        "followup": ["company", "summary", "next_steps"],
    }

    # Pydantic output models per artifact type (strong schema validation)
    OUTPUT_MODELS: Dict[str, Type[BaseModel]] = {
        "research_brief": ResearchBrief,
        "target_map": TargetMap,
        "outreach": OutreachDraft,
        "meeting_prep": MeetingPrepPack,
        "followup": FollowUpSummary,
    }

    def verify_skill_result(
        self, result: SkillResult, memory_enabled: bool = False
    ) -> List[Issue]:
        """Run all verification checks on a skill result.

        Args:
            result: The SkillResult to verify
            memory_enabled: Whether memory retrieval was enabled (M4)

        Returns:
            List of Issue objects found
        """
        issues: List[Issue] = []

        # Check 1: Artifact refs exist
        issues.extend(self._check_artifact_refs_exist(result))

        # Check 2: JSON validates (parse check)
        issues.extend(self._check_json_validates(result))

        # Check 3: Schema validates (Pydantic model check)
        issues.extend(self._check_schema_validates(result))

        # Check 4: Claims are properly labeled
        issues.extend(self._check_claims_labeled(result))

        # Check 5: Basic completeness
        issues.extend(self._check_basic_completeness(result))

        # Check 6 (M4): Evidence consistency when memory is enabled
        if memory_enabled:
            issues.extend(self._check_evidence_consistency(result))

        return issues

    def _check_artifact_refs_exist(self, result: SkillResult) -> List[Issue]:
        """Check that artifacts have both MD and JSON versions."""
        issues = []

        # Group artifacts by name
        artifacts_by_name: Dict[str, List[ArtifactRef]] = {}
        for artifact in result.artifacts:
            if artifact.name not in artifacts_by_name:
                artifacts_by_name[artifact.name] = []
            artifacts_by_name[artifact.name].append(artifact)

        # Check each artifact has both MD and JSON
        for name, artifacts in artifacts_by_name.items():
            kinds = {a.kind for a in artifacts}

            if ArtifactKind.MARKDOWN not in kinds:
                issues.append(
                    Issue(
                        check="artifact_refs_exist",
                        message=f"Artifact '{name}' missing markdown version",
                        severity=IssueSeverity.WARNING,
                        artifact_name=name,
                    )
                )

            if ArtifactKind.JSON not in kinds:
                issues.append(
                    Issue(
                        check="artifact_refs_exist",
                        message=f"Artifact '{name}' missing JSON version",
                        severity=IssueSeverity.ERROR,
                        artifact_name=name,
                    )
                )

        return issues

    def _check_json_validates(self, result: SkillResult) -> List[Issue]:
        """Check that JSON artifacts contain valid JSON (parse check)."""
        issues = []

        for artifact in result.artifacts:
            if artifact.kind == ArtifactKind.JSON:
                try:
                    json.loads(artifact.content)
                except json.JSONDecodeError as e:
                    issues.append(
                        Issue(
                            check="json_validates",
                            message=f"Invalid JSON in artifact '{artifact.name}': {e}",
                            severity=IssueSeverity.ERROR,
                            artifact_name=artifact.name,
                            details={"error": str(e)},
                        )
                    )

        return issues

    def _check_schema_validates(self, result: SkillResult) -> List[Issue]:
        """Check that JSON artifacts validate against Pydantic output models.

        This is stronger than json_validates - it ensures the data structure
        matches the expected schema with correct types and required fields.
        """
        issues = []

        for artifact in result.artifacts:
            if artifact.kind != ArtifactKind.JSON:
                continue

            # Get the Pydantic model for this artifact type
            model_class = self.OUTPUT_MODELS.get(artifact.name)
            if not model_class:
                # No schema defined for this artifact type - skip
                continue

            try:
                data = json.loads(artifact.content)
            except json.JSONDecodeError:
                # Already caught in _check_json_validates
                continue

            try:
                model_class.model_validate(data)
            except ValidationError as e:
                # Extract readable error messages
                error_messages = []
                for error in e.errors():
                    loc = " -> ".join(str(x) for x in error["loc"])
                    error_messages.append(f"{loc}: {error['msg']}")

                issues.append(
                    Issue(
                        check="schema_validates",
                        message=f"Artifact '{artifact.name}' failed schema validation",
                        severity=IssueSeverity.WARNING,  # Warning, not error (allows flexibility)
                        artifact_name=artifact.name,
                        details={
                            "model": model_class.__name__,
                            "errors": error_messages,
                            "error_count": len(e.errors()),
                        },
                    )
                )

        return issues

    def _check_claims_labeled(self, result: SkillResult) -> List[Issue]:
        """Check that claims without evidence are labeled assumption/inference."""
        issues = []

        for i, claim in enumerate(result.claims):
            if not claim.is_sourced() and claim.kind == ClaimKind.FACT:
                issues.append(
                    Issue(
                        check="claims_labeled",
                        message=f"Claim '{claim.text[:50]}...' marked as FACT but has no evidence",
                        severity=IssueSeverity.ERROR,
                        details={"claim_index": i, "claim_text": claim.text},
                    )
                )

        return issues

    def _check_basic_completeness(self, result: SkillResult) -> List[Issue]:
        """Check that artifacts have minimum required fields."""
        issues = []

        for artifact in result.artifacts:
            if artifact.kind != ArtifactKind.JSON:
                continue

            try:
                data = json.loads(artifact.content)
            except json.JSONDecodeError:
                continue  # Already caught in json_validates

            # Check required fields for this artifact type
            required = self.REQUIRED_FIELDS.get(artifact.name, [])
            missing = [f for f in required if f not in data or not data[f]]

            if missing:
                issues.append(
                    Issue(
                        check="basic_completeness",
                        message=f"Artifact '{artifact.name}' missing required fields: {missing}",
                        severity=IssueSeverity.ERROR,
                        artifact_name=artifact.name,
                        details={"missing_fields": missing},
                    )
                )

        return issues

    def _check_evidence_consistency(self, result: SkillResult) -> List[Issue]:
        """Check that fact claims have evidence (M4).

        When memory retrieval is enabled, claims marked as 'fact' should have
        evidence. This check only runs when memory_enabled=True to avoid
        false failures on manual runs.

        Args:
            result: The SkillResult to check

        Returns:
            List of Issue objects for evidence inconsistencies
        """
        issues = []

        for i, claim in enumerate(result.claims):
            # Only check facts - assumptions and inferences don't require evidence
            if claim.kind == ClaimKind.FACT and not claim.is_sourced():
                issues.append(
                    Issue(
                        check="evidence_consistency",
                        message=(
                            f"Claim '{claim.text[:50]}...' is marked as FACT "
                            "but has no evidence (memory retrieval was enabled)"
                        ),
                        severity=IssueSeverity.WARNING,  # Warning, not error
                        details={
                            "claim_index": i,
                            "claim_text": claim.text,
                            "claim_kind": claim.kind.value,
                        },
                    )
                )

        return issues


# Singleton verifier instance
_verifier = Verifier()


def verify_skill_result(
    result: SkillResult, memory_enabled: bool = False
) -> List[Dict[str, Any]]:
    """Convenience function to verify a skill result.

    Args:
        result: The SkillResult to verify
        memory_enabled: Whether memory retrieval was enabled (M4)

    Returns:
        List of issue dicts (for easy logging/JSON serialization)
    """
    issues = _verifier.verify_skill_result(result, memory_enabled=memory_enabled)
    return [issue.to_dict() for issue in issues]

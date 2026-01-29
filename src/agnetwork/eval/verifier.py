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

M8 additions:
- Evidence quote verification (quotes must exist in source text)
- Research brief evidence validation
"""

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

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

logger = logging.getLogger(__name__)


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
    7. (M8) evidence_quotes: Evidence quotes exist verbatim in source text
    """

    # Required fields per artifact type (light checks)
    REQUIRED_FIELDS: Dict[str, List[str]] = {
        "research_brief": ["company", "snapshot"],
        "target_map": ["company", "personas"],
        "outreach": ["company", "persona", "variants"],
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

    def __init__(self, source_loader: Optional[Callable[[str], Optional[str]]] = None):
        """Initialize verifier.

        Args:
            source_loader: M8 - Optional function to load source text by source_id.
                           Signature: (source_id: str) -> Optional[str]
                           If not provided, evidence quote verification is skipped.
        """
        self._source_loader = source_loader

    def verify_skill_result(
        self,
        result: SkillResult,
        memory_enabled: bool = False,
        verify_evidence_quotes: bool = False,
    ) -> List[Issue]:
        """Run all verification checks on a skill result.

        Args:
            result: The SkillResult to verify
            memory_enabled: Whether memory retrieval was enabled (M4)
            verify_evidence_quotes: M8 - Whether to verify evidence quotes exist in sources

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

        # Check 7 (M8): Evidence quote verification
        if verify_evidence_quotes:
            issues.extend(self._check_evidence_quotes(result))

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

    def _check_evidence_quotes(self, result: SkillResult) -> List[Issue]:  # noqa: C901
        """M8: Check that evidence quotes exist verbatim in source text.

        For research_brief artifacts, verifies that:
        1. Non-assumption facts have evidence
        2. Evidence quotes exist as exact substrings in their source

        Args:
            result: The SkillResult to check

        Returns:
            List of Issue objects for evidence quote problems
        """
        issues = []

        # Only check research_brief artifacts
        for artifact in result.artifacts:
            if artifact.kind != ArtifactKind.JSON or artifact.name != "research_brief":
                continue

            try:
                data = json.loads(artifact.content)
            except json.JSONDecodeError:
                continue

            angles = data.get("personalization_angles", [])

            for i, angle in enumerate(angles):
                is_assumption = angle.get("is_assumption", True)
                evidence = angle.get("evidence", [])
                name = angle.get("name", f"angle_{i}")

                # M8 Rule: non-assumption without evidence is an error
                if not is_assumption and not evidence:
                    issues.append(
                        Issue(
                            check="evidence_quotes",
                            message=f"Angle '{name}' is not an assumption but has no evidence",
                            severity=IssueSeverity.ERROR,
                            artifact_name=artifact.name,
                            details={
                                "angle_index": i,
                                "angle_name": name,
                                "is_assumption": is_assumption,
                            },
                        )
                    )
                    continue

                # M8 Rule: verify each evidence quote exists in source
                for j, ev in enumerate(evidence):
                    source_id = ev.get("source_id", "")
                    quote = ev.get("quote", "")

                    if not source_id or not quote:
                        issues.append(
                            Issue(
                                check="evidence_quotes",
                                message=f"Angle '{name}' evidence[{j}] missing source_id or quote",
                                severity=IssueSeverity.ERROR,
                                artifact_name=artifact.name,
                                details={
                                    "angle_index": i,
                                    "evidence_index": j,
                                    "source_id": source_id,
                                    "quote_length": len(quote),
                                },
                            )
                        )
                        continue

                    # Try to load source text and verify quote
                    if self._source_loader is not None:
                        source_text = self._source_loader(source_id)
                        if source_text is None:
                            issues.append(
                                Issue(
                                    check="evidence_quotes",
                                    message=f"Angle '{name}' evidence[{j}] source not found: {source_id}",
                                    severity=IssueSeverity.ERROR,
                                    artifact_name=artifact.name,
                                    details={
                                        "angle_index": i,
                                        "evidence_index": j,
                                        "source_id": source_id,
                                    },
                                )
                            )
                        elif quote not in source_text:
                            # Try case-insensitive and whitespace-normalized match
                            normalized_quote = " ".join(quote.lower().split())
                            normalized_source = " ".join(source_text.lower().split())

                            if normalized_quote not in normalized_source:
                                issues.append(
                                    Issue(
                                        check="evidence_quotes",
                                        message=f"Angle '{name}' evidence[{j}] quote not found in source",
                                        severity=IssueSeverity.ERROR,
                                        artifact_name=artifact.name,
                                        details={
                                            "angle_index": i,
                                            "evidence_index": j,
                                            "source_id": source_id,
                                            "quote": quote[:100] + "..."
                                            if len(quote) > 100
                                            else quote,
                                        },
                                    )
                                )
                            else:
                                # Found with normalization - log warning
                                logger.warning(
                                    f"Evidence quote found with whitespace/case normalization: {quote[:50]}..."
                                )
                    else:
                        # No source loader - log that we can't verify
                        logger.debug(
                            f"Cannot verify evidence quote (no source_loader): {source_id}"
                        )

        return issues


def create_verifier_with_sources(  # noqa: C901
    sources_dir: Optional[Path] = None,
    db_path: Optional[Path] = None,
    workspace_id: Optional[str] = None,
) -> Verifier:
    """Create a Verifier with a source loader for evidence verification.

    Args:
        sources_dir: Path to sources directory (for file-based lookup)
        db_path: Path to SQLite database (for DB-based lookup)
        workspace_id: Workspace ID for DB isolation (required if db_path is provided)

    Returns:
        Verifier instance with source_loader configured
    """
    source_cache: Dict[str, str] = {}

    def load_source(source_id: str) -> Optional[str]:  # noqa: C901
        """Load source text by source_id."""
        # Check cache first
        if source_id in source_cache:
            return source_cache[source_id]

        # Try file-based lookup
        if sources_dir is not None:
            # Look for *__clean.txt files
            for clean_file in sources_dir.glob("*__clean.txt"):
                # Check if source_id matches the file
                if source_id in clean_file.stem:
                    try:
                        text = clean_file.read_text(encoding="utf-8")
                        source_cache[source_id] = text
                        return text
                    except Exception as e:
                        logger.warning(f"Failed to read source file {clean_file}: {e}")

            # Also check meta files for source_id match
            for meta_file in sources_dir.glob("*__meta.json"):
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    if meta.get("source_id") == source_id:
                        # Found matching meta, load the clean file
                        clean_path = meta_file.with_name(
                            meta_file.stem.replace("__meta", "__clean") + ".txt"
                        )
                        if clean_path.exists():
                            text = clean_path.read_text(encoding="utf-8")
                            source_cache[source_id] = text
                            return text
                except Exception:
                    continue

        # Try DB-based lookup
        if db_path is not None and workspace_id is not None:
            try:
                from agnetwork.storage.sqlite import SQLiteManager

                db = SQLiteManager(db_path=db_path, workspace_id=workspace_id)
                source = db.get_source(source_id)
                if source:
                    text = source.get("clean_text", "")
                    source_cache[source_id] = text
                    return text
            except Exception as e:
                logger.warning(f"Failed to load source from DB: {e}")

        return None

    return Verifier(source_loader=load_source)


# Singleton verifier instance (without source loader for backward compatibility)
_verifier = Verifier()


def verify_skill_result(
    result: SkillResult,
    memory_enabled: bool = False,
    verify_evidence_quotes: bool = False,
    source_loader: Optional[Callable[[str], Optional[str]]] = None,
) -> List[Dict[str, Any]]:
    """Convenience function to verify a skill result.

    Args:
        result: The SkillResult to verify
        memory_enabled: Whether memory retrieval was enabled (M4)
        verify_evidence_quotes: M8 - Whether to verify evidence quotes exist in sources
        source_loader: M8 - Optional function to load source text by source_id

    Returns:
        List of issue dicts (for easy logging/JSON serialization)
    """
    verifier = Verifier(source_loader=source_loader) if source_loader else _verifier
    issues = verifier.verify_skill_result(
        result,
        memory_enabled=memory_enabled,
        verify_evidence_quotes=verify_evidence_quotes,
    )
    return [issue.to_dict() for issue in issues]

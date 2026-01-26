"""Versioning utilities for artifacts and skills."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Package version
PACKAGE_VERSION = "0.1.0"

# Default versions for artifacts and skills
DEFAULT_ARTIFACT_VERSION = "1.0"
DEFAULT_SKILL_VERSION = "1.0"

# Skill version registry - maps skill names to their versions
SKILL_VERSIONS: Dict[str, str] = {
    "research_brief": "1.0",
    "target_map": "1.0",
    "outreach": "1.0",
    "meeting_prep": "1.0",
    "followup": "1.0",
}


def get_skill_version(skill_name: str) -> str:
    """Get the version for a given skill name."""
    return SKILL_VERSIONS.get(skill_name, DEFAULT_SKILL_VERSION)


def create_artifact_meta(
    artifact_name: str,
    skill_name: str,
    run_id: str,
    artifact_version: Optional[str] = None,
    skill_version: Optional[str] = None,
) -> Dict[str, Any]:
    """Create metadata block for an artifact.

    Args:
        artifact_name: Name of the artifact (e.g., "research_brief")
        skill_name: Name of the skill that generated it
        run_id: The run identifier
        artifact_version: Override artifact version (default: "1.0")
        skill_version: Override skill version (default from registry)

    Returns:
        Dict containing artifact metadata
    """
    return {
        "artifact_version": artifact_version or DEFAULT_ARTIFACT_VERSION,
        "skill_name": skill_name,
        "skill_version": skill_version or get_skill_version(skill_name),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
    }


def inject_meta(
    json_data: Dict[str, Any],
    artifact_name: str,
    skill_name: str,
    run_id: str,
) -> Dict[str, Any]:
    """Inject metadata into artifact JSON data.

    Creates a copy of the data with 'meta' field added.
    Preserves all existing fields for backward compatibility.

    Args:
        json_data: Original artifact data
        artifact_name: Name of the artifact
        skill_name: Name of the skill
        run_id: The run identifier

    Returns:
        New dict with meta field added
    """
    result = dict(json_data)
    result["meta"] = create_artifact_meta(
        artifact_name=artifact_name,
        skill_name=skill_name,
        run_id=run_id,
    )
    return result

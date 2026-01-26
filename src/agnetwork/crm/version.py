"""CRM export manifest version compatibility (M6.1).

Defines version compatibility rules for CRM export packages:
- Same major version: OK
- Higher minor version: Warn but continue
- Different major version: Fail with clear error

Version format: MAJOR.MINOR (e.g., "1.0", "1.1", "2.0")
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

# Current export schema version
CRM_EXPORT_VERSION = "1.0"


class VersionCompatibility(str, Enum):
    """Result of version compatibility check."""

    COMPATIBLE = "compatible"  # Same major, same or lower minor
    WARN = "warn"  # Same major, higher minor (forward compatible with warning)
    INCOMPATIBLE = "incompatible"  # Different major (breaking change)


@dataclass
class VersionCheckResult:
    """Result of a version compatibility check."""

    status: VersionCompatibility
    current_version: str
    manifest_version: str
    message: str


def parse_version(version_str: str) -> Tuple[int, int]:
    """Parse a version string into (major, minor) tuple.

    Args:
        version_str: Version string like "1.0" or "2.1"

    Returns:
        Tuple of (major, minor) as integers

    Raises:
        ValueError: If version string is invalid
    """
    if not version_str:
        raise ValueError("Empty version string")

    parts = version_str.split(".")
    if len(parts) < 2:
        # Accept "1" as "1.0"
        parts.append("0")

    try:
        major = int(parts[0])
        minor = int(parts[1])
    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid version format: {version_str}") from e

    return major, minor


def check_version_compatibility(
    manifest_version: str,
    current_version: str = CRM_EXPORT_VERSION,
) -> VersionCheckResult:
    """Check if a manifest version is compatible with the current version.

    Compatibility rules:
    - Same major, same or lower minor: COMPATIBLE (OK)
    - Same major, higher minor: WARN (forward compatible)
    - Different major: INCOMPATIBLE (breaking change)

    Args:
        manifest_version: Version from manifest (e.g., "1.0")
        current_version: Current importer version (default: CRM_EXPORT_VERSION)

    Returns:
        VersionCheckResult with status and message
    """
    try:
        manifest_major, manifest_minor = parse_version(manifest_version)
        current_major, current_minor = parse_version(current_version)
    except ValueError as e:
        return VersionCheckResult(
            status=VersionCompatibility.INCOMPATIBLE,
            current_version=current_version,
            manifest_version=manifest_version,
            message=f"Invalid version format: {e}",
        )

    # Major version mismatch = incompatible
    if manifest_major != current_major:
        if manifest_major > current_major:
            message = (
                f"Manifest version {manifest_version} requires a newer importer. "
                f"Current importer supports version {current_major}.x"
            )
        else:
            message = (
                f"Manifest version {manifest_version} is from an older format. "
                f"Current importer requires version {current_major}.x"
            )
        return VersionCheckResult(
            status=VersionCompatibility.INCOMPATIBLE,
            current_version=current_version,
            manifest_version=manifest_version,
            message=message,
        )

    # Same major, check minor
    if manifest_minor > current_minor:
        # Newer minor version - warn but proceed
        return VersionCheckResult(
            status=VersionCompatibility.WARN,
            current_version=current_version,
            manifest_version=manifest_version,
            message=(
                f"Manifest version {manifest_version} is newer than importer "
                f"version {current_version}. Some features may not be fully supported."
            ),
        )

    # Compatible (same major, same or older minor)
    return VersionCheckResult(
        status=VersionCompatibility.COMPATIBLE,
        current_version=current_version,
        manifest_version=manifest_version,
        message=f"Version {manifest_version} is compatible with importer {current_version}",
    )


class ManifestVersionError(Exception):
    """Raised when manifest version is incompatible."""

    def __init__(self, check_result: VersionCheckResult):
        self.check_result = check_result
        super().__init__(check_result.message)

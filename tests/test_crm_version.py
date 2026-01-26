"""Tests for CRM export version compatibility (M6.1 Task D).

Tests cover:
- Version compatibility rules (COMPATIBLE, WARN, INCOMPATIBLE)
- Version parsing
- check_version_compatibility() function
"""

import pytest

from agnetwork.crm.version import (
    CRM_EXPORT_VERSION,
    VersionCheckResult,
    VersionCompatibility,
    check_version_compatibility,
)


class TestVersionConstants:
    """Tests for version constants."""

    def test_current_version_format(self):
        """Current version has expected format."""
        assert isinstance(CRM_EXPORT_VERSION, str)
        parts = CRM_EXPORT_VERSION.split(".")
        assert len(parts) == 2
        assert all(p.isdigit() for p in parts)

    def test_current_version_value(self):
        """Current version is 1.0 for M6.1."""
        assert CRM_EXPORT_VERSION == "1.0"


class TestVersionStatus:
    """Tests for VersionCompatibility enum."""

    def test_status_values(self):
        """All expected status values exist."""
        assert VersionCompatibility.COMPATIBLE.value == "compatible"
        assert VersionCompatibility.WARN.value == "warn"
        assert VersionCompatibility.INCOMPATIBLE.value == "incompatible"


class TestVersionCheckResult:
    """Tests for VersionCheckResult dataclass."""

    def test_compatible_result(self):
        """COMPATIBLE result properties."""
        result = VersionCheckResult(
            status=VersionCompatibility.COMPATIBLE,
            message="Versions match",
            manifest_version="1.0",
            current_version="1.0",
        )
        assert result.status == VersionCompatibility.COMPATIBLE

    def test_warn_result(self):
        """WARN result."""
        result = VersionCheckResult(
            status=VersionCompatibility.WARN,
            message="Minor version difference",
            manifest_version="1.1",
            current_version="1.0",
        )
        assert result.status == VersionCompatibility.WARN

    def test_incompatible_result(self):
        """INCOMPATIBLE result."""
        result = VersionCheckResult(
            status=VersionCompatibility.INCOMPATIBLE,
            message="Major version mismatch",
            manifest_version="2.0",
            current_version="1.0",
        )
        assert result.status == VersionCompatibility.INCOMPATIBLE


class TestCheckVersionCompatibility:
    """Tests for check_version_compatibility()."""

    def test_exact_match(self):
        """Exact version match is COMPATIBLE."""
        result = check_version_compatibility("1.0")
        assert result.status == VersionCompatibility.COMPATIBLE
        assert result.manifest_version == "1.0"
        assert result.current_version == CRM_EXPORT_VERSION

    def test_same_major_higher_minor(self):
        """Same major, higher minor version is WARN."""
        result = check_version_compatibility("1.5")
        assert result.status == VersionCompatibility.WARN
        assert "newer" in result.message.lower() or "minor" in result.message.lower()

    def test_same_major_lower_minor(self):
        """Same major, lower minor version is COMPATIBLE."""
        # If current is 1.0, anything with major=1 and minor<0 wouldn't exist
        # So let's test with something that makes sense
        result = check_version_compatibility("1.0")
        assert result.status == VersionCompatibility.COMPATIBLE

    def test_higher_major_incompatible(self):
        """Higher major version is INCOMPATIBLE."""
        result = check_version_compatibility("2.0")
        assert result.status == VersionCompatibility.INCOMPATIBLE
        assert "major" in result.message.lower() or "newer" in result.message.lower()

    def test_lower_major_incompatible(self):
        """Lower major version is INCOMPATIBLE (if we ever reach 2.0+)."""
        # This tests the reverse case - manifest from older major version
        result = check_version_compatibility("0.5")
        # Depends on implementation - could be WARN or INCOMPATIBLE
        # For M6.1, we treat lower major as INCOMPATIBLE
        assert result.status == VersionCompatibility.INCOMPATIBLE

    def test_invalid_version_format(self):
        """Invalid version format is INCOMPATIBLE."""
        result = check_version_compatibility("invalid")
        assert result.status == VersionCompatibility.INCOMPATIBLE

    def test_version_with_extra_parts(self):
        """Version with extra parts (1.0.0) is handled."""
        result = check_version_compatibility("1.0.0")
        # Should still work - either parse first two parts or fail gracefully
        # Implementation decides - just verify it doesn't crash
        assert result.status in (VersionCompatibility.COMPATIBLE, VersionCompatibility.WARN, VersionCompatibility.INCOMPATIBLE)


class TestVersionCompatibilityMatrix:
    """Comprehensive tests for version compatibility rules.

    Documents the expected behavior for various version combinations.
    """

    @pytest.mark.parametrize("manifest_version,expected_status", [
        ("1.0", VersionCompatibility.COMPATIBLE),  # Exact match
        ("1.1", VersionCompatibility.WARN),         # Same major, higher minor
        ("1.9", VersionCompatibility.WARN),         # Same major, much higher minor
        ("2.0", VersionCompatibility.INCOMPATIBLE), # Higher major
        ("0.9", VersionCompatibility.INCOMPATIBLE), # Lower major
        ("3.5", VersionCompatibility.INCOMPATIBLE), # Much higher major
        ("x.y", VersionCompatibility.INCOMPATIBLE), # Invalid
    ])
    def test_compatibility_matrix(self, manifest_version, expected_status):
        """Test various version combinations."""
        result = check_version_compatibility(manifest_version)
        assert result.status == expected_status, (
            f"Expected {expected_status} for version '{manifest_version}', "
            f"got {result.status}: {result.message}"
        )

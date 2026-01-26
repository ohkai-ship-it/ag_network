"""Tests for versioning utilities."""

from agnetwork.versioning import (
    DEFAULT_ARTIFACT_VERSION,
    DEFAULT_SKILL_VERSION,
    SKILL_VERSIONS,
    create_artifact_meta,
    get_skill_version,
    inject_meta,
)


class TestVersioning:
    """Tests for versioning utilities."""

    def test_get_skill_version_known(self):
        """Test getting version for known skill."""
        version = get_skill_version("research_brief")
        assert version == SKILL_VERSIONS["research_brief"]

    def test_get_skill_version_unknown(self):
        """Test getting version for unknown skill returns default."""
        version = get_skill_version("unknown_skill")
        assert version == DEFAULT_SKILL_VERSION

    def test_create_artifact_meta(self):
        """Test creating artifact metadata."""
        meta = create_artifact_meta(
            artifact_name="research_brief",
            skill_name="research_brief",
            run_id="20260125_100000__test__research",
        )

        assert meta["artifact_version"] == DEFAULT_ARTIFACT_VERSION
        assert meta["skill_name"] == "research_brief"
        assert meta["skill_version"] == SKILL_VERSIONS["research_brief"]
        assert meta["run_id"] == "20260125_100000__test__research"
        assert "generated_at" in meta

    def test_create_artifact_meta_with_overrides(self):
        """Test creating artifact metadata with version overrides."""
        meta = create_artifact_meta(
            artifact_name="test",
            skill_name="test",
            run_id="test_123",
            artifact_version="2.0",
            skill_version="1.5",
        )

        assert meta["artifact_version"] == "2.0"
        assert meta["skill_version"] == "1.5"

    def test_inject_meta(self):
        """Test injecting meta into JSON data."""
        original = {
            "company": "TestCorp",
            "snapshot": "Test company",
            "pains": ["pain1"],
        }

        result = inject_meta(
            json_data=original,
            artifact_name="research_brief",
            skill_name="research_brief",
            run_id="test_123",
        )

        # Original data preserved
        assert result["company"] == "TestCorp"
        assert result["snapshot"] == "Test company"
        assert result["pains"] == ["pain1"]

        # Meta added
        assert "meta" in result
        assert result["meta"]["artifact_version"] == DEFAULT_ARTIFACT_VERSION
        assert result["meta"]["skill_name"] == "research_brief"
        assert result["meta"]["run_id"] == "test_123"

    def test_inject_meta_does_not_modify_original(self):
        """Test that inject_meta doesn't modify the original dict."""
        original = {"company": "TestCorp"}

        inject_meta(
            json_data=original,
            artifact_name="test",
            skill_name="test",
            run_id="test_123",
        )

        assert "meta" not in original

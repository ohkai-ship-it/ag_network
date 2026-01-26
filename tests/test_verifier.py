"""Tests for the verifier layer."""

import json

from agnetwork.eval.verifier import Issue, IssueSeverity, Verifier, verify_skill_result
from agnetwork.kernel.contracts import (
    ArtifactKind,
    ArtifactRef,
    Claim,
    ClaimKind,
    SkillResult,
)


class TestVerifier:
    """Tests for Verifier class."""

    def test_verify_valid_result(self):
        """Test verifying a valid skill result."""
        result = SkillResult(
            output={"test": "data"},
            artifacts=[
                ArtifactRef(
                    name="test_artifact",
                    kind=ArtifactKind.MARKDOWN,
                    content="# Test",
                ),
                ArtifactRef(
                    name="test_artifact",
                    kind=ArtifactKind.JSON,
                    content=json.dumps({"company": "Test", "data": "value"}),
                ),
            ],
            claims=[
                Claim(
                    text="This is assumed",
                    kind=ClaimKind.ASSUMPTION,
                    evidence=[],
                ),
            ],
        )

        verifier = Verifier()
        issues = verifier.verify_skill_result(result)

        # No errors expected for valid result
        errors = [i for i in issues if i.severity == IssueSeverity.ERROR]
        assert len(errors) == 0

    def test_verify_missing_json_artifact(self):
        """Test verification catches missing JSON artifact."""
        result = SkillResult(
            output={"test": "data"},
            artifacts=[
                ArtifactRef(
                    name="test_artifact",
                    kind=ArtifactKind.MARKDOWN,
                    content="# Test",
                ),
                # Missing JSON artifact
            ],
            claims=[],
        )

        verifier = Verifier()
        issues = verifier.verify_skill_result(result)

        errors = [i for i in issues if i.severity == IssueSeverity.ERROR]
        assert len(errors) >= 1
        assert any(
            i.check == "artifact_refs_exist" and "JSON" in i.message for i in errors
        )

    def test_verify_invalid_json(self):
        """Test verification catches invalid JSON."""
        result = SkillResult(
            output={"test": "data"},
            artifacts=[
                ArtifactRef(
                    name="test_artifact",
                    kind=ArtifactKind.JSON,
                    content="{ invalid json }",
                ),
            ],
            claims=[],
        )

        verifier = Verifier()
        issues = verifier.verify_skill_result(result)

        errors = [i for i in issues if i.severity == IssueSeverity.ERROR]
        assert len(errors) >= 1
        assert any(i.check == "json_validates" for i in errors)

    def test_verify_unsourced_fact(self):
        """Test verification catches unsourced facts."""
        result = SkillResult(
            output={"test": "data"},
            artifacts=[
                ArtifactRef(
                    name="test_artifact",
                    kind=ArtifactKind.JSON,
                    content=json.dumps({"test": "data"}),
                ),
            ],
            claims=[
                Claim(
                    text="This is a fact without evidence",
                    kind=ClaimKind.FACT,  # Marked as fact but no evidence!
                    evidence=[],
                ),
            ],
        )

        verifier = Verifier()
        issues = verifier.verify_skill_result(result)

        errors = [i for i in issues if i.severity == IssueSeverity.ERROR]
        assert len(errors) >= 1
        assert any(i.check == "claims_labeled" for i in errors)

    def test_verify_missing_required_fields(self):
        """Test verification catches missing required fields."""
        result = SkillResult(
            output={},
            artifacts=[
                ArtifactRef(
                    name="research_brief",
                    kind=ArtifactKind.JSON,
                    content=json.dumps({"company": "Test"}),  # Missing 'snapshot'
                ),
            ],
            claims=[],
        )

        verifier = Verifier()
        issues = verifier.verify_skill_result(result)

        errors = [i for i in issues if i.severity == IssueSeverity.ERROR]
        assert len(errors) >= 1
        assert any(
            i.check == "basic_completeness" and "snapshot" in str(i.details)
            for i in errors
        )

    def test_verify_schema_validates_valid(self):
        """Test schema validation passes for valid Pydantic model."""
        from datetime import datetime, timezone

        result = SkillResult(
            output={},
            artifacts=[
                ArtifactRef(
                    name="research_brief",
                    kind=ArtifactKind.JSON,
                    content=json.dumps({
                        "company": "TestCorp",
                        "snapshot": "A test company",
                        "pains": ["pain1"],
                        "triggers": ["trigger1"],
                        "competitors": ["competitor1"],
                        "personalization_angles": [],
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }),
                ),
            ],
            claims=[],
        )

        verifier = Verifier()
        issues = verifier.verify_skill_result(result)

        schema_issues = [i for i in issues if i.check == "schema_validates"]
        assert len(schema_issues) == 0

    def test_verify_schema_validates_invalid(self):
        """Test schema validation catches invalid Pydantic model data."""
        result = SkillResult(
            output={},
            artifacts=[
                ArtifactRef(
                    name="research_brief",
                    kind=ArtifactKind.JSON,
                    content=json.dumps({
                        "company": "TestCorp",
                        "snapshot": "A test company",
                        # Missing required fields: pains, triggers, competitors, personalization_angles
                    }),
                ),
            ],
            claims=[],
        )

        verifier = Verifier()
        issues = verifier.verify_skill_result(result)

        schema_issues = [i for i in issues if i.check == "schema_validates"]
        assert len(schema_issues) == 1
        assert schema_issues[0].severity == IssueSeverity.WARNING
        assert "ResearchBrief" in schema_issues[0].details["model"]

    def test_verify_convenience_function(self):
        """Test the verify_skill_result convenience function."""
        result = SkillResult(
            output={},
            artifacts=[
                ArtifactRef(
                    name="test",
                    kind=ArtifactKind.JSON,
                    content="invalid json",
                ),
            ],
            claims=[],
        )

        issues = verify_skill_result(result)

        assert isinstance(issues, list)
        assert len(issues) > 0
        assert all(isinstance(i, dict) for i in issues)
        assert "check" in issues[0]
        assert "severity" in issues[0]


class TestIssue:
    """Tests for Issue model."""

    def test_issue_creation(self):
        """Test creating an Issue."""
        issue = Issue(
            check="test_check",
            message="Test message",
            severity=IssueSeverity.ERROR,
            artifact_name="test_artifact",
        )

        assert issue.check == "test_check"
        assert issue.severity == IssueSeverity.ERROR

    def test_issue_to_dict(self):
        """Test converting Issue to dict."""
        issue = Issue(
            check="test_check",
            message="Test message",
            severity=IssueSeverity.WARNING,
            details={"key": "value"},
        )

        d = issue.to_dict()

        assert d["check"] == "test_check"
        assert d["message"] == "Test message"
        assert d["severity"] == "warning"
        assert d["details"]["key"] == "value"

"""Tests for CRM mapping refactored helpers (M6.3).

Verifies that:
- Activity helper methods work correctly
- Activity types are correctly determined
- Source ID scoping works
- Artifact metadata is preserved
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from agnetwork.crm.mapping import PipelineMapper
from agnetwork.crm.models import ActivityDirection, ActivityType
from agnetwork.storage.sqlite import SQLiteManager


@pytest.fixture
def temp_db():
    """Provide temporary database."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.sqlite"
        db = SQLiteManager(db_path=db_path)
        yield db
        db.close()


@pytest.fixture
def mapper_with_db(temp_db):
    """Provide PipelineMapper with temporary database."""
    return PipelineMapper(db=temp_db)


class TestActivityFromOutreach:
    """Tests for _activity_from_outreach helper."""

    def test_email_channel_creates_email_activity(self, mapper_with_db):
        """Email channel creates EMAIL activity type."""
        outreach = {
            "company": "TestCo",
            "channel": "email",
            "subject_or_hook": "Test Subject",
            "body": "Test body",
            "persona": "VP Sales",
        }

        activity = mapper_with_db._activity_from_outreach(
            outreach=outreach,
            account_id="acc_test",
            contact_id="con_test",
            run_id="run_123",
            run_dir=Path("/tmp/run"),
            all_source_ids=["src_1", "src_2"],
        )

        assert activity.activity_type == ActivityType.EMAIL
        assert activity.direction == ActivityDirection.OUTBOUND
        assert activity.subject == "Test Subject"
        assert activity.body == "Test body"

    def test_linkedin_channel_creates_linkedin_activity(self, mapper_with_db):
        """LinkedIn channel creates LINKEDIN activity type."""
        outreach = {
            "company": "TestCo",
            "channel": "linkedin",
            "subject_or_hook": "LinkedIn Hook",
            "body": "LinkedIn message",
        }

        activity = mapper_with_db._activity_from_outreach(
            outreach=outreach,
            account_id="acc_test",
            contact_id="con_test",
            run_id="run_123",
            run_dir=Path("/tmp/run"),
            all_source_ids=[],
        )

        assert activity.activity_type == ActivityType.LINKEDIN

    def test_metadata_includes_channel(self, mapper_with_db):
        """Activity metadata includes channel information."""
        outreach = {
            "company": "TestCo",
            "channel": "email",
            "subject_or_hook": "Subject",
            "body": "Body",
            "sequence_steps": ["Step 1", "Step 2"],
            "objection_responses": {"price": "ROI analysis"},
        }

        activity = mapper_with_db._activity_from_outreach(
            outreach=outreach,
            account_id="acc_test",
            contact_id=None,
            run_id="run_123",
            run_dir=Path("/tmp/run"),
            all_source_ids=[],
        )

        assert activity.metadata["artifact_type"] == "outreach"
        assert activity.metadata["channel"] == "email"
        assert activity.metadata["sequence_steps"] == ["Step 1", "Step 2"]


class TestActivityFromMeetingPrep:
    """Tests for _activity_from_meeting_prep helper."""

    def test_creates_note_activity(self, mapper_with_db):
        """Meeting prep creates NOTE activity."""
        prep = {
            "meeting_type": "discovery",
            "agenda": ["Item 1", "Item 2"],
            "questions": ["Q1", "Q2"],
        }

        activity = mapper_with_db._activity_from_meeting_prep(
            prep=prep,
            account_id="acc_test",
            contact_id="con_test",
            run_id="run_123",
            run_dir=Path("/tmp/run"),
            all_source_ids=[],
        )

        assert activity.activity_type == ActivityType.NOTE
        assert "Discovery" in activity.subject
        assert "## Agenda" in activity.body
        assert "## Questions" in activity.body

    def test_body_includes_agenda_and_questions(self, mapper_with_db):
        """Body includes formatted agenda and questions."""
        prep = {
            "meeting_type": "demo",
            "agenda": ["Introduction", "Demo"],
            "questions": ["How does it work?"],
            "stakeholder_map": {"CEO": "decision_maker"},
        }

        activity = mapper_with_db._activity_from_meeting_prep(
            prep=prep,
            account_id="acc_test",
            contact_id="con_test",
            run_id="run_123",
            run_dir=Path("/tmp/run"),
            all_source_ids=[],
        )

        assert "- Introduction" in activity.body
        assert "- Demo" in activity.body
        assert "- How does it work?" in activity.body


class TestActivityFromFollowup:
    """Tests for _activity_from_followup helper."""

    def test_creates_email_activity(self, mapper_with_db):
        """Follow-up creates EMAIL activity."""
        followup = {
            "company": "TestCo",
            "summary": "Good meeting",
            "next_steps": ["Send proposal"],
            "tasks": [{"task": "Send proposal", "owner": "sales"}],
        }

        activity = mapper_with_db._activity_from_followup(
            followup=followup,
            account_id="acc_test",
            contact_id="con_test",
            run_id="run_123",
            run_dir=Path("/tmp/run"),
            all_source_ids=[],
        )

        assert activity.activity_type == ActivityType.EMAIL
        assert "Follow-up" in activity.subject
        assert "Good meeting" in activity.body
        assert "## Next Steps" in activity.body
        assert "## Tasks" in activity.body


class TestActivityFromResearchBrief:
    """Tests for _activity_from_research_brief helper."""

    def test_creates_note_at_account_level(self, mapper_with_db):
        """Research brief creates NOTE without contact_id."""
        brief = {
            "company": "TestCo",
            "snapshot": "A tech company",
            "pains": ["Pain 1"],
            "triggers": ["Trigger 1"],
            "personalization_angles": [{"name": "Angle", "fact": "Fact"}],
        }

        activity = mapper_with_db._activity_from_research_brief(
            brief=brief,
            account_id="acc_test",
            run_id="run_123",
            run_dir=Path("/tmp/run"),
            all_source_ids=[],
        )

        assert activity.activity_type == ActivityType.NOTE
        assert activity.contact_id is None  # Account-level activity
        assert "Research Brief" in activity.subject
        assert "## Company Snapshot" in activity.body
        assert "## Key Pains" in activity.body
        assert "## Triggers" in activity.body


class TestGetScopedSourceIds:
    """Tests for _get_scoped_source_ids helper."""

    def test_returns_artifact_source_ids_when_present(self, mapper_with_db):
        """Returns artifact-specific source_ids when present."""
        artifact_data = {"source_ids": ["src_a", "src_b"]}

        result = mapper_with_db._get_scoped_source_ids(
            artifact_data=artifact_data,
            artifact_ref="test",
            run_id="run_123",
            fallback_source_ids=["src_fallback"],
        )

        assert "src_a" in result
        assert "src_b" in result
        assert "src_fallback" not in result

    def test_returns_fallback_when_no_artifact_sources(self, mapper_with_db):
        """Returns fallback source_ids when artifact has none."""
        artifact_data = {}

        result = mapper_with_db._get_scoped_source_ids(
            artifact_data=artifact_data,
            artifact_ref="test",
            run_id="run_123",
            fallback_source_ids=["src_fallback_1", "src_fallback_2"],
        )

        assert result == ["src_fallback_1", "src_fallback_2"]


class TestCreateActivitiesRefactored:
    """Tests for the refactored _create_activities method."""

    @pytest.fixture
    def temp_run_dir(self):
        """Create temporary run directory with artifacts."""
        with TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            (run_dir / "artifacts").mkdir()

            # Create all artifact types
            artifacts = {
                "outreach": {"channel": "email", "subject_or_hook": "Subject", "body": "Body"},
                "meeting_prep": {"meeting_type": "discovery", "agenda": [], "questions": []},
                "followup": {"company": "Test", "summary": "Summary", "next_steps": []},
                "research_brief": {"company": "Test", "snapshot": "Snapshot", "pains": []},
            }
            for name, data in artifacts.items():
                with open(run_dir / "artifacts" / f"{name}.json", "w") as f:
                    json.dump(data, f)

            yield run_dir

    def test_creates_activities_for_all_artifact_types(self, mapper_with_db, temp_run_dir):
        """Creates activities for all artifact types."""
        from agnetwork.crm.models import Contact

        mock_contact = Contact(
            contact_id="con_test",
            account_id="acc_test",
            full_name="Test User",
            role_title="CEO",
        )

        artifacts = {
            "outreach": {"channel": "email", "subject_or_hook": "Subject", "body": "Body"},
            "meeting_prep": {"meeting_type": "discovery", "agenda": [], "questions": []},
            "followup": {"company": "Test", "summary": "Summary", "next_steps": []},
            "research_brief": {"company": "Test", "snapshot": "Snapshot", "pains": []},
        }

        activities = mapper_with_db._create_activities(
            account_id="acc_test",
            contacts=[mock_contact],
            artifacts=artifacts,
            run_id="run_123",
            run_dir=temp_run_dir,
            all_source_ids=["src_1"],
        )

        # Should have 4 activities (one for each artifact)
        assert len(activities) == 4

        # Check each activity type is present
        artifact_types = [a.metadata.get("artifact_type") for a in activities]
        assert "outreach" in artifact_types
        assert "meeting_prep" in artifact_types
        assert "followup" in artifact_types
        assert "research_brief" in artifact_types

    def test_handles_missing_artifacts_gracefully(self, mapper_with_db, temp_run_dir):
        """Handles partial artifact set gracefully."""
        from agnetwork.crm.models import Contact

        mock_contact = Contact(
            contact_id="con_test",
            account_id="acc_test",
            full_name="Test User",
            role_title="CEO",
        )

        # Only outreach artifact
        artifacts = {
            "outreach": {"channel": "email", "subject_or_hook": "Subject", "body": "Body"},
        }

        activities = mapper_with_db._create_activities(
            account_id="acc_test",
            contacts=[mock_contact],
            artifacts=artifacts,
            run_id="run_123",
            run_dir=temp_run_dir,
            all_source_ids=[],
        )

        # Should have only 1 activity
        assert len(activities) == 1
        assert activities[0].metadata["artifact_type"] == "outreach"

    def test_handles_empty_contacts_list(self, mapper_with_db, temp_run_dir):
        """Handles empty contacts list."""
        artifacts = {
            "outreach": {"channel": "email", "subject_or_hook": "Subject", "body": "Body"},
        }

        activities = mapper_with_db._create_activities(
            account_id="acc_test",
            contacts=[],  # Empty contacts
            artifacts=artifacts,
            run_id="run_123",
            run_dir=temp_run_dir,
            all_source_ids=[],
        )

        # Should still create activity
        assert len(activities) == 1
        assert activities[0].contact_id is None

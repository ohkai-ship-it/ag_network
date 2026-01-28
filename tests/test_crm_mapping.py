"""Tests for CRM mapping layer (Task D).

Verifies that:
- Pipeline runs are mapped to CRM objects correctly
- source_ids is deduped and stable-ordered
- No artifact schema changes required
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from agnetwork.crm.mapping import PipelineMapper, map_run_to_crm
from agnetwork.crm.models import ActivityType
from agnetwork.storage.sqlite import SQLiteManager


@pytest.fixture
def temp_run_dir():
    """Create a temporary run directory with sample artifacts."""
    with TemporaryDirectory() as tmpdir:
        run_dir = Path(tmpdir) / "20260126_test__testcompany__pipeline"
        run_dir.mkdir(parents=True)
        (run_dir / "artifacts").mkdir()
        (run_dir / "sources").mkdir()
        (run_dir / "logs").mkdir()

        # Create inputs.json
        inputs = {
            "company": "TestCompany",
            "snapshot": "A test company for mapping tests",
            "pains": ["Pain 1", "Pain 2"],
            "triggers": ["Trigger 1"],
            "competitors": ["Competitor A", "Competitor B"],
            "persona": "VP Sales",
            "channel": "email",
            "meeting_type": "discovery",
            "notes": "Test notes",
            "source_ids": ["src_input_1", "src_input_2"],
        }
        with open(run_dir / "inputs.json", "w") as f:
            json.dump(inputs, f, indent=2)

        # Create research_brief.json
        research_brief = {
            "company": "TestCompany",
            "snapshot": "A test company for mapping tests",
            "pains": ["Pain 1", "Pain 2"],
            "triggers": ["Trigger 1"],
            "competitors": ["Competitor A"],
            "personalization_angles": [
                {
                    "name": "Market Expansion",
                    "fact": "TestCompany is expanding",
                    "is_assumption": True,
                    "source_ids": ["src_angle_1"],
                },
            ],
            "meta": {
                "artifact_version": "1.0",
                "skill_name": "research_brief",
                "run_id": "20260126_test__testcompany__pipeline",
            },
        }
        with open(run_dir / "artifacts" / "research_brief.json", "w") as f:
            json.dump(research_brief, f, indent=2)

        # Create target_map.json
        target_map = {
            "company": "TestCompany",
            "personas": [
                {"title": "VP Sales", "role": "economic_buyer", "hypothesis": "Controls budget"},
                {"title": "Sales Manager", "role": "champion", "hypothesis": "Advocates internally"},
                {"title": "IT Director", "role": "blocker", "hypothesis": "Has technical concerns"},
            ],
            "meta": {
                "artifact_version": "1.0",
                "skill_name": "target_map",
                "run_id": "20260126_test__testcompany__pipeline",
            },
        }
        with open(run_dir / "artifacts" / "target_map.json", "w") as f:
            json.dump(target_map, f, indent=2)

        # Create outreach.json
        outreach = {
            "company": "TestCompany",
            "persona": "VP Sales",
            "channel": "email",
            "subject_or_hook": "Partnership opportunity with TestCompany",
            "body": "Hi VP Sales,\n\nI'd like to explore a partnership...",
            "personalization_notes": "Research recent announcements",
            "sequence_steps": [
                "Initial outreach (Day 0)",
                "Follow-up if no response (Day 3)",
                "Value-add content share (Day 7)",
            ],
            "objection_responses": {
                "no_budget": "Let me share ROI analysis...",
                "no_time": "How about a 15-min call?",
            },
            "meta": {
                "artifact_version": "1.0",
                "skill_name": "outreach",
                "run_id": "20260126_test__testcompany__pipeline",
            },
        }
        with open(run_dir / "artifacts" / "outreach.json", "w") as f:
            json.dump(outreach, f, indent=2)

        # Create meeting_prep.json
        meeting_prep = {
            "company": "TestCompany",
            "meeting_type": "discovery",
            "agenda": ["Introductions (5 min)", "Problem discovery (15 min)"],
            "questions": ["What are your current challenges?"],
            "stakeholder_map": {"VP Sales": "Economic buyer"},
            "meta": {
                "artifact_version": "1.0",
                "skill_name": "meeting_prep",
                "run_id": "20260126_test__testcompany__pipeline",
            },
        }
        with open(run_dir / "artifacts" / "meeting_prep.json", "w") as f:
            json.dump(meeting_prep, f, indent=2)

        # Create followup.json
        followup = {
            "company": "TestCompany",
            "summary": "Good initial conversation",
            "next_steps": ["Send proposal", "Schedule demo"],
            "tasks": [{"task": "Send proposal", "owner": "sales", "due": "2 days"}],
            "crm_notes": "Strong interest in solution",
            "meta": {
                "artifact_version": "1.0",
                "skill_name": "followup",
                "run_id": "20260126_test__testcompany__pipeline",
            },
        }
        with open(run_dir / "artifacts" / "followup.json", "w") as f:
            json.dump(followup, f, indent=2)

        yield run_dir


@pytest.fixture
def temp_db():
    """Provide temporary database."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.sqlite"
        db = SQLiteManager(db_path=db_path)
        yield db
        db.close()  # M6.2: Ensure DB is closed before temp cleanup


class TestPipelineMapper:
    """Tests for PipelineMapper."""

    def test_map_run_creates_account(self, temp_run_dir, temp_db):
        """Mapping creates an Account from company inputs."""
        mapper = PipelineMapper(db=temp_db)
        run_id = temp_run_dir.name

        package = mapper.map_run(run_id, run_dir=temp_run_dir)

        assert len(package.accounts) == 1
        account = package.accounts[0]
        assert account.name == "TestCompany"
        assert account.description == "A test company for mapping tests"
        assert "pain:Pain 1" in account.tags

    def test_map_run_creates_contacts(self, temp_run_dir, temp_db):
        """Mapping creates Contacts from target_map personas."""
        mapper = PipelineMapper(db=temp_db)
        run_id = temp_run_dir.name

        package = mapper.map_run(run_id, run_dir=temp_run_dir)

        assert len(package.contacts) == 3
        titles = [c.role_title for c in package.contacts]
        assert "VP Sales" in titles
        assert "Sales Manager" in titles
        assert "IT Director" in titles

        # Check persona_type mapping
        vp = next(c for c in package.contacts if c.role_title == "VP Sales")
        assert vp.persona_type == "economic_buyer"

    def test_map_run_creates_activities(self, temp_run_dir, temp_db):
        """Mapping creates Activities from artifacts."""
        mapper = PipelineMapper(db=temp_db)
        run_id = temp_run_dir.name

        package = mapper.map_run(run_id, run_dir=temp_run_dir)

        # Should have: outreach, meeting_prep, followup, research_brief
        assert len(package.activities) >= 3

        # M6.2: Find activities by metadata.artifact_type (M6.1 changed IDs to hashes)
        # Check outreach activity
        outreach_act = next(
            (a for a in package.activities
             if a.metadata.get("artifact_type") == "outreach"),
            None
        )
        assert outreach_act is not None, (
            f"Expected outreach activity, got: "
            f"{[(a.activity_id, a.metadata.get('artifact_type')) for a in package.activities]}"
        )
        assert outreach_act.activity_type == ActivityType.EMAIL
        assert outreach_act.direction.value == "outbound"
        assert outreach_act.run_id == run_id

        # Check meeting_prep activity
        prep_act = next(
            (a for a in package.activities
             if a.metadata.get("artifact_type") == "meeting_prep"),
            None
        )
        assert prep_act is not None, (
            f"Expected meeting_prep activity, got: "
            f"{[(a.activity_id, a.metadata.get('artifact_type')) for a in package.activities]}"
        )
        assert prep_act.activity_type == ActivityType.NOTE

    def test_map_run_collects_source_ids(self, temp_run_dir, temp_db):
        """Mapping collects source_ids from inputs and artifacts."""
        mapper = PipelineMapper(db=temp_db)
        run_id = temp_run_dir.name

        package = mapper.map_run(run_id, run_dir=temp_run_dir)

        # Check that activities have source_ids
        for activity in package.activities:
            assert isinstance(activity.source_ids, list)

        # Should include source_ids from inputs
        all_source_ids = set()
        for activity in package.activities:
            all_source_ids.update(activity.source_ids)

        assert "src_input_1" in all_source_ids
        assert "src_input_2" in all_source_ids
        assert "src_angle_1" in all_source_ids

    def test_source_ids_are_stable_ordered(self, temp_run_dir, temp_db):
        """source_ids are deduped and stable-ordered (sorted)."""
        mapper = PipelineMapper(db=temp_db)
        run_id = temp_run_dir.name

        # Run mapping twice
        package1 = mapper.map_run(run_id, run_dir=temp_run_dir)
        package2 = mapper.map_run(run_id, run_dir=temp_run_dir)

        # source_ids should be identical
        for act1, act2 in zip(package1.activities, package2.activities):
            assert act1.source_ids == act2.source_ids

        # Should be sorted
        for activity in package1.activities:
            assert activity.source_ids == sorted(activity.source_ids)

    def test_map_run_creates_manifest(self, temp_run_dir, temp_db):
        """Mapping creates complete manifest."""
        mapper = PipelineMapper(db=temp_db)
        run_id = temp_run_dir.name

        package = mapper.map_run(run_id, run_dir=temp_run_dir)

        assert package.manifest.run_id == run_id
        assert package.manifest.company == "TestCompany"
        assert package.manifest.account_count == 1
        assert package.manifest.contact_count == 3
        assert package.manifest.activity_count >= 3
        assert package.manifest.crm_export_version == "1.0"

    def test_map_run_artifact_refs(self, temp_run_dir, temp_db):
        """Activities include artifact references."""
        mapper = PipelineMapper(db=temp_db)
        run_id = temp_run_dir.name

        package = mapper.map_run(run_id, run_dir=temp_run_dir)

        for activity in package.activities:
            assert len(activity.artifact_refs) > 0
            # Should reference actual artifact files
            for ref in activity.artifact_refs:
                assert "artifacts" in ref


class TestMapRunTocrm:
    """Tests for convenience function."""

    def test_map_run_to_crm_works(self, temp_run_dir, temp_db):
        """map_run_to_crm convenience function works."""
        run_id = temp_run_dir.name

        package = map_run_to_crm(run_id, run_dir=temp_run_dir, db=temp_db)

        assert package is not None
        assert len(package.accounts) == 1

    def test_map_run_not_found_raises(self, temp_db, tmp_path):
        """map_run_to_crm raises for non-existent run."""
        mapper = PipelineMapper(db=temp_db)

        # Provide a non-existent but valid path
        fake_run_dir = tmp_path / "nonexistent_run_id"

        with pytest.raises(ValueError, match="not found"):
            mapper.map_run("nonexistent_run_id", run_dir=fake_run_dir)


class TestMappingWithoutTargetMap:
    """Tests for mapping when target_map is missing."""

    def test_creates_placeholder_contact(self, temp_run_dir, temp_db):
        """Creates placeholder contact when no target_map."""
        # Remove target_map.json
        (temp_run_dir / "artifacts" / "target_map.json").unlink()

        mapper = PipelineMapper(db=temp_db)
        package = mapper.map_run(temp_run_dir.name, run_dir=temp_run_dir)

        # Should still have at least one placeholder contact
        assert len(package.contacts) >= 1
        assert any("placeholder" in c.tags for c in package.contacts)

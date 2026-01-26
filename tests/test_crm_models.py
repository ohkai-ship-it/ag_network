"""Tests for CRM models (Task A).

Verifies that canonical CRM models:
- Validate and serialize correctly
- Have no vendor-specific fields
- Support external_refs pattern
"""

import json
from datetime import datetime, timezone

from agnetwork.crm.models import (
    Account,
    Activity,
    ActivityDirection,
    ActivityType,
    Contact,
    CRMExportManifest,
    CRMExportPackage,
    ExternalRef,
    Opportunity,
    OpportunityStage,
)


class TestAccount:
    """Tests for Account model."""

    def test_create_minimal_account(self):
        """Account can be created with minimal required fields."""
        account = Account(
            account_id="acc_123",
            name="Test Company",
        )
        assert account.account_id == "acc_123"
        assert account.name == "Test Company"
        assert account.domain is None
        assert account.tags == []
        assert account.external_refs == []

    def test_create_full_account(self):
        """Account can be created with all fields."""
        account = Account(
            account_id="acc_456",
            name="Full Company",
            domain="fullcompany.com",
            industry="Technology",
            location="San Francisco, CA",
            description="A test company description",
            employee_count=500,
            tags=["enterprise", "tech"],
            external_refs=[
                ExternalRef(provider="hubspot", external_id="hs_123"),
            ],
            metadata={"source": "import"},
        )
        assert account.domain == "fullcompany.com"
        assert account.industry == "Technology"
        assert len(account.external_refs) == 1
        assert account.external_refs[0].provider == "hubspot"

    def test_account_serialization(self):
        """Account serializes to JSON correctly."""
        account = Account(
            account_id="acc_json",
            name="JSON Test",
            tags=["tag1", "tag2"],
        )
        data = account.model_dump(mode="json")
        assert isinstance(data, dict)
        assert data["account_id"] == "acc_json"
        assert data["tags"] == ["tag1", "tag2"]

        # Should be JSON serializable
        json_str = json.dumps(data, default=str)
        assert "acc_json" in json_str

    def test_account_get_external_id(self):
        """get_external_id returns correct ID for provider."""
        account = Account(
            account_id="acc_ext",
            name="External Test",
            external_refs=[
                ExternalRef(provider="hubspot", external_id="hs_100"),
                ExternalRef(provider="salesforce", external_id="sf_200"),
            ],
        )
        assert account.get_external_id("hubspot") == "hs_100"
        assert account.get_external_id("salesforce") == "sf_200"
        assert account.get_external_id("pipedrive") is None


class TestContact:
    """Tests for Contact model."""

    def test_create_minimal_contact(self):
        """Contact can be created with minimal required fields."""
        contact = Contact(
            contact_id="con_123",
            full_name="John Doe",
        )
        assert contact.contact_id == "con_123"
        assert contact.full_name == "John Doe"
        assert contact.account_id is None
        assert contact.email is None

    def test_create_full_contact(self):
        """Contact can be created with all fields."""
        contact = Contact(
            contact_id="con_456",
            account_id="acc_123",
            full_name="Jane Smith",
            first_name="Jane",
            last_name="Smith",
            role_title="VP Sales",
            department="Sales",
            email="jane@example.com",
            phone="+1-555-1234",
            linkedin_url="https://linkedin.com/in/janesmith",
            tags=["champion", "decision-maker"],
            persona_type="economic_buyer",
            hypothesis="Controls budget for new solutions",
        )
        assert contact.account_id == "acc_123"
        assert contact.role_title == "VP Sales"
        assert contact.persona_type == "economic_buyer"

    def test_contact_serialization(self):
        """Contact serializes to JSON correctly."""
        contact = Contact(
            contact_id="con_json",
            full_name="Test Person",
            email="test@example.com",
        )
        data = contact.model_dump(mode="json")
        json_str = json.dumps(data, default=str)
        assert "con_json" in json_str
        assert "test@example.com" in json_str


class TestActivity:
    """Tests for Activity model."""

    def test_create_minimal_activity(self):
        """Activity can be created with minimal required fields."""
        activity = Activity(
            activity_id="act_123",
            account_id="acc_123",
            activity_type=ActivityType.EMAIL,
            subject="Test Subject",
        )
        assert activity.activity_id == "act_123"
        assert activity.activity_type == ActivityType.EMAIL
        assert activity.direction == ActivityDirection.OUTBOUND
        assert activity.is_planned is False

    def test_create_planned_activity(self):
        """Activity can be created as planned."""
        scheduled = datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc)
        activity = Activity(
            activity_id="act_planned",
            account_id="acc_123",
            activity_type=ActivityType.EMAIL,
            subject="Planned Email",
            is_planned=True,
            scheduled_for=scheduled,
            sequence_step=1,
            sequence_name="Test Sequence",
        )
        assert activity.is_planned is True
        assert activity.scheduled_for == scheduled
        assert activity.sequence_step == 1

    def test_activity_with_traceability(self):
        """Activity carries full traceability information."""
        activity = Activity(
            activity_id="act_traced",
            account_id="acc_123",
            contact_id="con_123",
            activity_type=ActivityType.NOTE,
            subject="Research Notes",
            body="Meeting notes content",
            run_id="20260126_101856__test__pipeline",
            artifact_refs=["artifacts/research_brief.json"],
            source_ids=["src_1", "src_2", "src_3"],
        )
        assert activity.run_id == "20260126_101856__test__pipeline"
        assert len(activity.artifact_refs) == 1
        assert len(activity.source_ids) == 3

    def test_activity_types(self):
        """All activity types are valid."""
        for activity_type in ActivityType:
            activity = Activity(
                activity_id=f"act_{activity_type.value}",
                account_id="acc_123",
                activity_type=activity_type,
                subject=f"Test {activity_type.value}",
            )
            assert activity.activity_type == activity_type

    def test_activity_serialization(self):
        """Activity serializes to JSON correctly."""
        activity = Activity(
            activity_id="act_json",
            account_id="acc_json",
            activity_type=ActivityType.LINKEDIN,
            subject="LinkedIn Message",
            direction=ActivityDirection.OUTBOUND,
            source_ids=["src_a", "src_b"],
        )
        data = activity.model_dump(mode="json")
        assert data["activity_type"] == "linkedin"
        assert data["direction"] == "outbound"
        assert data["source_ids"] == ["src_a", "src_b"]


class TestExternalRef:
    """Tests for ExternalRef model."""

    def test_create_external_ref(self):
        """ExternalRef can be created."""
        ref = ExternalRef(
            provider="hubspot",
            external_id="hs_12345",
        )
        assert ref.provider == "hubspot"
        assert ref.external_id == "hs_12345"
        assert ref.last_synced_at is None
        assert ref.sync_hash is None

    def test_external_ref_with_sync_info(self):
        """ExternalRef can have sync information."""
        ref = ExternalRef(
            provider="salesforce",
            external_id="sf_67890",
            last_synced_at=datetime.now(timezone.utc),
            sync_hash="abc123def456",
        )
        assert ref.last_synced_at is not None
        assert ref.sync_hash == "abc123def456"


class TestCRMExportPackage:
    """Tests for CRMExportPackage model."""

    def test_create_export_package(self):
        """CRMExportPackage can be created with manifest and data."""
        manifest = CRMExportManifest(
            export_id="exp_123",
            run_id="test_run",
            company="Test Co",
            account_count=1,
            contact_count=2,
            activity_count=3,
        )
        account = Account(account_id="acc_1", name="Test Co")
        contact1 = Contact(contact_id="con_1", full_name="Person 1")
        contact2 = Contact(contact_id="con_2", full_name="Person 2")

        package = CRMExportPackage(
            manifest=manifest,
            accounts=[account],
            contacts=[contact1, contact2],
            activities=[],
        )

        assert package.manifest.export_id == "exp_123"
        assert len(package.accounts) == 1
        assert len(package.contacts) == 2
        assert len(package.activities) == 0

    def test_export_package_serialization(self):
        """CRMExportPackage serializes completely."""
        manifest = CRMExportManifest(
            export_id="exp_serial",
            crm_export_version="1.0",
        )
        package = CRMExportPackage(manifest=manifest)

        data = package.model_dump(mode="json")
        json_str = json.dumps(data, default=str)
        assert "exp_serial" in json_str
        assert "1.0" in json_str


class TestOpportunityInterface:
    """Tests for Opportunity model (interface definition)."""

    def test_opportunity_interface_exists(self):
        """Opportunity interface is defined."""
        opp = Opportunity(
            opportunity_id="opp_123",
            account_id="acc_123",
            name="Test Deal",
        )
        assert opp.stage == OpportunityStage.PROSPECTING
        assert opp.currency == "USD"

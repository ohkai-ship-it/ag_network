"""Tests for CRM adapters (Task C).

Verifies that:
- FileCRMAdapter exports and imports correctly
- Round-trip (export → import) works
- Approval gate prevents push operations
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from agnetwork.crm.adapters import (
    CRMAdapterError,
    FileCRMAdapter,
)
from agnetwork.crm.adapters.base import (
    AdapterRegistry,
    ApprovalRequiredError,
    ApprovalToken,
    SideEffectCategory,
    get_adapter,
    requires_approval,
)
from agnetwork.crm.models import (
    Account,
    Activity,
    ActivityType,
    Contact,
    CRMExportManifest,
    CRMExportPackage,
)
from agnetwork.crm.storage import CRMStorage


@pytest.fixture
def temp_storage():
    """Provide a temporary storage for tests."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.sqlite"
        storage = CRMStorage(db_path=db_path)
        yield storage


@pytest.fixture
def temp_adapter(temp_storage):
    """Provide a temporary file adapter."""
    with TemporaryDirectory() as tmpdir:
        adapter = FileCRMAdapter(
            storage=temp_storage,
            base_path=Path(tmpdir),
        )
        yield adapter, Path(tmpdir)


@pytest.fixture
def sample_package():
    """Provide a sample export package."""
    manifest = CRMExportManifest(
        export_id="test_export",
        run_id="test_run_123",
        company="Test Company",
        account_count=1,
        contact_count=2,
        activity_count=1,
    )

    account = Account(
        account_id="acc_test",
        name="Test Company",
        domain="test.com",
        industry="Technology",
        tags=["tag1", "tag2"],
    )

    contacts = [
        Contact(
            contact_id="con_1",
            account_id="acc_test",
            full_name="John Doe",
            role_title="VP Sales",
            email="john@test.com",
        ),
        Contact(
            contact_id="con_2",
            account_id="acc_test",
            full_name="Jane Smith",
            role_title="CTO",
            email="jane@test.com",
        ),
    ]

    activity = Activity(
        activity_id="act_1",
        account_id="acc_test",
        contact_id="con_1",
        activity_type=ActivityType.EMAIL,
        subject="Test Email",
        body="Test body content",
        run_id="test_run_123",
        source_ids=["src_1", "src_2"],
    )

    return CRMExportPackage(
        manifest=manifest,
        accounts=[account],
        contacts=contacts,
        activities=[activity],
    )


class TestFileCRMAdapterExport:
    """Tests for export operations."""

    def test_export_json(self, temp_adapter, sample_package):
        """Can export package as JSON."""
        adapter, base_path = temp_adapter
        output_dir = base_path / "export_json"

        result = adapter.export_data(sample_package, str(output_dir), format="json")

        assert result.success
        assert result.accounts_exported == 1
        assert result.contacts_exported == 2
        assert result.activities_exported == 1

        # Check files exist
        assert (output_dir / "manifest.json").exists()
        assert (output_dir / "accounts.json").exists()
        assert (output_dir / "contacts.json").exists()
        assert (output_dir / "activities.json").exists()

    def test_export_csv(self, temp_adapter, sample_package):
        """Can export package as CSV."""
        adapter, base_path = temp_adapter
        output_dir = base_path / "export_csv"

        result = adapter.export_data(sample_package, str(output_dir), format="csv")

        assert result.success
        assert (output_dir / "manifest.json").exists()  # Manifest always JSON
        assert (output_dir / "accounts.csv").exists()
        assert (output_dir / "contacts.csv").exists()
        assert (output_dir / "activities.csv").exists()

    def test_export_manifest_content(self, temp_adapter, sample_package):
        """Manifest contains expected fields."""
        adapter, base_path = temp_adapter
        output_dir = base_path / "export_manifest"

        adapter.export_data(sample_package, str(output_dir), format="json")

        with open(output_dir / "manifest.json", "r") as f:
            manifest = json.load(f)

        assert manifest["export_id"] == "test_export"
        assert manifest["run_id"] == "test_run_123"
        assert manifest["company"] == "Test Company"
        assert manifest["crm_export_version"] == "1.0"


class TestFileCRMAdapterImport:
    """Tests for import operations."""

    def test_import_json_dry_run(self, temp_adapter, sample_package):
        """Can import JSON in dry-run mode."""
        adapter, base_path = temp_adapter
        export_dir = base_path / "export_for_import"

        # First export
        adapter.export_data(sample_package, str(export_dir), format="json")

        # Then import (dry run)
        result = adapter.import_data(str(export_dir), dry_run=True)

        assert result.success
        assert result.dry_run is True
        assert result.accounts_imported == 1
        assert result.contacts_imported == 2
        assert result.activities_imported == 1

    def test_import_json_persist(self, temp_adapter, sample_package):
        """Can import JSON and persist."""
        adapter, base_path = temp_adapter
        export_dir = base_path / "export_persist"

        # First export
        adapter.export_data(sample_package, str(export_dir), format="json")

        # Then import (persist)
        result = adapter.import_data(str(export_dir), dry_run=False)

        assert result.success
        assert result.dry_run is False

        # Verify data is in storage
        accounts = adapter.list_accounts()
        assert len(accounts) == 1
        assert accounts[0].name == "Test Company"

    def test_import_csv(self, temp_adapter, sample_package):
        """Can import CSV files."""
        adapter, base_path = temp_adapter
        export_dir = base_path / "export_csv_import"

        # Export as CSV
        adapter.export_data(sample_package, str(export_dir), format="csv")

        # Import
        result = adapter.import_data(str(export_dir), dry_run=True)

        assert result.success
        assert result.accounts_imported >= 1


class TestFileCRMAdapterRoundTrip:
    """Tests for export → import round-trip."""

    def test_round_trip_preserves_data(self, temp_adapter, sample_package):
        """Round-trip preserves all data fields."""
        adapter, base_path = temp_adapter
        export_dir = base_path / "round_trip"

        # Export
        adapter.export_data(sample_package, str(export_dir), format="json")

        # Create new adapter with fresh storage
        fresh_storage = CRMStorage(db_path=base_path / "fresh.sqlite")
        fresh_adapter = FileCRMAdapter(storage=fresh_storage, base_path=base_path)

        # Import into fresh storage
        result = fresh_adapter.import_data(str(export_dir), dry_run=False)
        assert result.success

        # Verify data
        accounts = fresh_adapter.list_accounts()
        assert len(accounts) == 1
        assert accounts[0].name == "Test Company"
        assert accounts[0].domain == "test.com"
        assert accounts[0].tags == ["tag1", "tag2"]

        contacts = fresh_adapter.list_contacts()
        assert len(contacts) == 2

        activities = fresh_adapter.list_activities()
        assert len(activities) == 1
        assert activities[0].source_ids == ["src_1", "src_2"]


class TestAdapterRegistry:
    """Tests for adapter registry."""

    def test_file_adapter_registered(self):
        """FileCRMAdapter is registered."""
        adapter_class = AdapterRegistry.get("file")
        assert adapter_class is not None
        assert adapter_class is FileCRMAdapter

    def test_list_adapters(self):
        """Can list registered adapters."""
        adapters = AdapterRegistry.list_adapters()
        assert "file" in adapters

    def test_get_adapter_default(self):
        """get_adapter returns file adapter by default."""
        adapter = get_adapter()
        assert isinstance(adapter, FileCRMAdapter)

    def test_get_adapter_unknown_raises(self):
        """get_adapter raises for unknown adapter."""
        with pytest.raises(CRMAdapterError):
            get_adapter("nonexistent_adapter")


class TestApprovalGate:
    """Tests for approval gate infrastructure."""

    def test_approval_required_error(self):
        """ApprovalRequiredError contains operation info."""
        error = ApprovalRequiredError("push_accounts", SideEffectCategory.CRM_WRITE)
        assert "push_accounts" in str(error)
        assert "crm_write" in str(error)

    def test_approval_token_valid(self):
        """Valid token passes validation."""
        token = ApprovalToken(
            token_id="test_token",
            side_effect=SideEffectCategory.CRM_WRITE,
            granted_by="test",
        )
        assert token.is_valid()

    def test_approval_token_expired(self):
        """Expired token fails validation."""
        from datetime import timedelta

        token = ApprovalToken(
            token_id="test_token",
            side_effect=SideEffectCategory.CRM_WRITE,
            granted_by="test",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert not token.is_valid()

    def test_requires_approval_decorator(self):
        """@requires_approval decorator enforces gate."""

        class MockAdapter:
            @requires_approval(SideEffectCategory.CRM_WRITE)
            def push_data(self, data, approval_token=None):
                return "success"

        adapter = MockAdapter()

        # Without token - should raise
        with pytest.raises(ApprovalRequiredError):
            adapter.push_data("test_data")

        # With valid token - should succeed
        token = ApprovalToken(
            token_id="valid_token",
            side_effect=SideEffectCategory.CRM_WRITE,
            granted_by="test",
        )
        result = adapter.push_data("test_data", approval_token=token)
        assert result == "success"

    def test_file_write_exempt_from_approval(self):
        """FILE_WRITE operations don't require approval token."""

        class MockAdapter:
            @requires_approval(SideEffectCategory.FILE_WRITE)
            def write_file(self, data, approval_token=None):
                return "written"

        adapter = MockAdapter()
        # Should not raise even without token
        result = adapter.write_file("test_data")
        assert result == "written"

    def test_wrong_side_effect_token_fails(self):
        """Token for wrong side effect is rejected."""

        class MockAdapter:
            @requires_approval(SideEffectCategory.CRM_WRITE)
            def push_data(self, data, approval_token=None):
                return "success"

        adapter = MockAdapter()

        # Token for different side effect
        wrong_token = ApprovalToken(
            token_id="wrong_token",
            side_effect=SideEffectCategory.CRM_READ,
            granted_by="test",
        )

        with pytest.raises(ApprovalRequiredError):
            adapter.push_data("test_data", approval_token=wrong_token)

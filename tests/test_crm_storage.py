"""Tests for CRM storage (Task B).

Verifies that CRM storage:
- Creates tables correctly
- Inserts and queries accounts/contacts/activities
- Doesn't break existing tables
"""

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from agnetwork.crm.models import (
    Account,
    Activity,
    ActivityType,
    Contact,
    ExternalRef,
)
from agnetwork.crm.storage import CRMStorage


@pytest.fixture
def temp_db():
    """Provide a temporary database for tests.

    Uses unscoped() to bypass workspace verification for unit tests.
    """
    with TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_crm.sqlite"
        storage = CRMStorage.unscoped(db_path=db_path)
        yield storage
        storage.close()  # M6.2: Ensure DB is closed before temp cleanup


class TestCRMStorageAccounts:
    """Tests for account storage operations."""

    def test_insert_and_get_account(self, temp_db):
        """Can insert and retrieve an account."""
        account = Account(
            account_id="acc_test1",
            name="Test Company",
            domain="test.com",
            industry="Technology",
        )
        temp_db.insert_account(account)

        retrieved = temp_db.get_account("acc_test1")
        assert retrieved is not None
        assert retrieved.name == "Test Company"
        assert retrieved.domain == "test.com"

    def test_get_account_by_domain(self, temp_db):
        """Can retrieve account by domain."""
        account = Account(
            account_id="acc_domain",
            name="Domain Co",
            domain="unique-domain.com",
        )
        temp_db.insert_account(account)

        retrieved = temp_db.get_account_by_domain("unique-domain.com")
        assert retrieved is not None
        assert retrieved.account_id == "acc_domain"

    def test_list_accounts(self, temp_db):
        """Can list all accounts."""
        for i in range(3):
            temp_db.insert_account(Account(
                account_id=f"acc_list_{i}",
                name=f"Company {i}",
            ))

        accounts = temp_db.list_accounts()
        assert len(accounts) == 3

    def test_search_accounts(self, temp_db):
        """Can search accounts by name."""
        temp_db.insert_account(Account(account_id="acc_s1", name="Acme Corp"))
        temp_db.insert_account(Account(account_id="acc_s2", name="Beta Inc"))
        temp_db.insert_account(Account(account_id="acc_s3", name="Acme Solutions"))

        results = temp_db.search_accounts("Acme")
        assert len(results) == 2

    def test_account_with_external_refs(self, temp_db):
        """Account external refs are stored and retrieved."""
        account = Account(
            account_id="acc_ext",
            name="External Co",
            external_refs=[
                ExternalRef(provider="hubspot", external_id="hs_123"),
                ExternalRef(provider="salesforce", external_id="sf_456"),
            ],
        )
        temp_db.insert_account(account)

        retrieved = temp_db.get_account("acc_ext")
        assert len(retrieved.external_refs) == 2
        assert retrieved.external_refs[0].provider == "hubspot"


class TestCRMStorageContacts:
    """Tests for contact storage operations."""

    def test_insert_and_get_contact(self, temp_db):
        """Can insert and retrieve a contact."""
        contact = Contact(
            contact_id="con_test1",
            account_id="acc_test",
            full_name="John Doe",
            role_title="VP Sales",
            email="john@test.com",
        )
        temp_db.insert_contact(contact)

        retrieved = temp_db.get_contact("con_test1")
        assert retrieved is not None
        assert retrieved.full_name == "John Doe"
        assert retrieved.email == "john@test.com"

    def test_get_contact_by_email(self, temp_db):
        """Can retrieve contact by email."""
        contact = Contact(
            contact_id="con_email",
            full_name="Email Test",
            email="unique@email.com",
        )
        temp_db.insert_contact(contact)

        retrieved = temp_db.get_contact_by_email("unique@email.com")
        assert retrieved is not None
        assert retrieved.contact_id == "con_email"

    def test_list_contacts_by_account(self, temp_db):
        """Can list contacts filtered by account."""
        # Create contacts for different accounts
        temp_db.insert_contact(Contact(
            contact_id="con_a1", account_id="acc_a", full_name="Person A1"
        ))
        temp_db.insert_contact(Contact(
            contact_id="con_a2", account_id="acc_a", full_name="Person A2"
        ))
        temp_db.insert_contact(Contact(
            contact_id="con_b1", account_id="acc_b", full_name="Person B1"
        ))

        contacts_a = temp_db.list_contacts(account_id="acc_a")
        assert len(contacts_a) == 2

        contacts_b = temp_db.list_contacts(account_id="acc_b")
        assert len(contacts_b) == 1

    def test_search_contacts(self, temp_db):
        """Can search contacts by name or title."""
        temp_db.insert_contact(Contact(
            contact_id="con_s1", full_name="Alice VP", role_title="VP Engineering"
        ))
        temp_db.insert_contact(Contact(
            contact_id="con_s2", full_name="Bob Manager", role_title="Sales Manager"
        ))

        results = temp_db.search_contacts("VP")
        assert len(results) >= 1


class TestCRMStorageActivities:
    """Tests for activity storage operations."""

    def test_insert_and_get_activity(self, temp_db):
        """Can insert and retrieve an activity."""
        activity = Activity(
            activity_id="act_test1",
            account_id="acc_test",
            activity_type=ActivityType.EMAIL,
            subject="Test Email",
            body="Test body content",
        )
        temp_db.insert_activity(activity)

        retrieved = temp_db.get_activity("act_test1")
        assert retrieved is not None
        assert retrieved.subject == "Test Email"
        assert retrieved.activity_type == ActivityType.EMAIL

    def test_activity_with_source_ids(self, temp_db):
        """Activity source_ids are stored and retrieved."""
        activity = Activity(
            activity_id="act_sources",
            account_id="acc_test",
            activity_type=ActivityType.NOTE,
            subject="Sourced Note",
            run_id="test_run_123",
            source_ids=["src_1", "src_2", "src_3"],
            artifact_refs=["artifact1.json", "artifact2.json"],
        )
        temp_db.insert_activity(activity)

        retrieved = temp_db.get_activity("act_sources")
        assert retrieved.source_ids == ["src_1", "src_2", "src_3"]
        assert retrieved.artifact_refs == ["artifact1.json", "artifact2.json"]
        assert retrieved.run_id == "test_run_123"

    def test_list_activities_by_run(self, temp_db):
        """Can list activities filtered by run_id."""
        temp_db.insert_activity(Activity(
            activity_id="act_r1",
            account_id="acc_test",
            activity_type=ActivityType.EMAIL,
            subject="Run 1 Activity",
            run_id="run_001",
        ))
        temp_db.insert_activity(Activity(
            activity_id="act_r2",
            account_id="acc_test",
            activity_type=ActivityType.NOTE,
            subject="Run 2 Activity",
            run_id="run_002",
        ))

        activities = temp_db.get_activities_by_run("run_001")
        assert len(activities) == 1
        assert activities[0].activity_id == "act_r1"

    def test_planned_activity(self, temp_db):
        """Planned activities are stored correctly."""
        scheduled = datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc)
        activity = Activity(
            activity_id="act_planned",
            account_id="acc_test",
            activity_type=ActivityType.EMAIL,
            subject="Planned Email",
            is_planned=True,
            scheduled_for=scheduled,
            sequence_step=1,
            sequence_name="Test Sequence",
        )
        temp_db.insert_activity(activity)

        retrieved = temp_db.get_activity("act_planned")
        assert retrieved.is_planned is True
        assert retrieved.scheduled_for == scheduled
        assert retrieved.sequence_step == 1


class TestCRMStorageBulkOperations:
    """Tests for bulk operations."""

    def test_bulk_insert_accounts(self, temp_db):
        """Can bulk insert accounts."""
        accounts = [
            Account(account_id=f"bulk_acc_{i}", name=f"Bulk Company {i}")
            for i in range(5)
        ]
        count = temp_db.bulk_insert_accounts(accounts)
        assert count == 5
        assert len(temp_db.list_accounts()) == 5

    def test_bulk_insert_contacts(self, temp_db):
        """Can bulk insert contacts."""
        contacts = [
            Contact(contact_id=f"bulk_con_{i}", full_name=f"Bulk Person {i}")
            for i in range(5)
        ]
        count = temp_db.bulk_insert_contacts(contacts)
        assert count == 5

    def test_bulk_insert_activities(self, temp_db):
        """Can bulk insert activities."""
        activities = [
            Activity(
                activity_id=f"bulk_act_{i}",
                account_id="acc_test",
                activity_type=ActivityType.NOTE,
                subject=f"Bulk Activity {i}",
            )
            for i in range(5)
        ]
        count = temp_db.bulk_insert_activities(activities)
        assert count == 5


class TestCRMStorageStats:
    """Tests for storage statistics."""

    def test_get_stats_empty(self, temp_db):
        """Stats work on empty database."""
        stats = temp_db.get_stats()
        assert stats["accounts"] == 0
        assert stats["contacts"] == 0
        assert stats["activities"] == 0

    def test_get_stats_with_data(self, temp_db):
        """Stats reflect inserted data."""
        temp_db.insert_account(Account(account_id="acc_1", name="Company 1"))
        temp_db.insert_contact(Contact(contact_id="con_1", full_name="Person 1"))
        temp_db.insert_contact(Contact(contact_id="con_2", full_name="Person 2"))
        temp_db.insert_activity(Activity(
            activity_id="act_1",
            account_id="acc_1",
            activity_type=ActivityType.EMAIL,
            subject="Email 1",
        ))

        stats = temp_db.get_stats()
        assert stats["accounts"] == 1
        assert stats["contacts"] == 2
        assert stats["activities"] == 1


class TestCRMStorageLifecycle:
    """Tests for storage lifecycle management (M6.2)."""

    def test_close_allows_file_deletion(self, tmp_path):
        """After close(), the database file can be deleted on Windows.

        This is a regression test for Windows SQLite file locking issues.
        """
        db_path = tmp_path / "lifecycle_test.sqlite"
        storage = CRMStorage.unscoped(db_path=db_path)

        # Write some data
        storage.insert_account(Account(account_id="acc_test", name="Test"))

        # Close storage
        storage.close()

        # File should be deletable after close
        assert db_path.exists()
        db_path.unlink()  # This would fail before M6.2 fix on Windows
        assert not db_path.exists()

    def test_context_manager_cleanup(self, tmp_path):
        """Context manager ensures proper cleanup."""
        db_path = tmp_path / "context_test.sqlite"

        with CRMStorage.unscoped(db_path=db_path) as storage:
            storage.insert_account(Account(account_id="acc_ctx", name="Context Test"))

        # File should be deletable after context exit
        assert db_path.exists()
        db_path.unlink()
        assert not db_path.exists()

    def test_double_close_is_safe(self, tmp_path):
        """Calling close() multiple times is safe."""
        db_path = tmp_path / "double_close.sqlite"
        storage = CRMStorage.unscoped(db_path=db_path)
        storage.insert_account(Account(account_id="acc_dbl", name="Double"))

        # Close multiple times - should not raise
        storage.close()
        storage.close()
        storage.close()

        # File should still be deletable
        db_path.unlink()

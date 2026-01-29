"""CRM storage layer using SQLite.

Extends the existing SQLite storage with tables for canonical CRM data:
- crm_accounts
- crm_contacts
- crm_activities

External refs are stored as JSON in each table for simplicity.

M6: Read/write to local database only. No breaking changes to existing tables.
PR3: Workspace isolation enforced via workspace_id guard (like SQLiteManager).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from agnetwork.crm.models import (
    Account,
    Activity,
    ActivityDirection,
    ActivityType,
    Contact,
    ExternalRef,
)

if TYPE_CHECKING:
    from agnetwork.workspaces.context import WorkspaceContext


class CRMStorage:
    """SQLite storage for canonical CRM data.

    Provides CRUD operations for accounts, contacts, and activities.
    Maintains traceability to the run system via run_id, artifact_refs, source_ids.

    IMPORTANT: Always use the `for_workspace()` factory or provide explicit
    db_path + workspace_id to ensure workspace isolation.

    Supports context manager protocol for automatic cleanup:
        with CRMStorage.for_workspace(ws_ctx) as storage:
            storage.insert_account(...)
    """

    def __init__(self, db_path: Path, *, workspace_id: str):
        """Initialize CRM storage with workspace isolation.

        Args:
            db_path: Path to SQLite database. REQUIRED.
            workspace_id: Workspace ID for isolation guard. REQUIRED.
                         verify_workspace_id() is called automatically.

        Raises:
            TypeError: If db_path is None or workspace_id is not provided.

        Note:
            For tests or migrations that need unscoped access, use
            CRMStorage.unscoped(db_path) instead.
        """
        self._init_internal(db_path, workspace_id=workspace_id, verify=True)

    def _init_internal(
        self,
        db_path: Path,
        *,
        workspace_id: Optional[str] = None,
        verify: bool = True,
    ) -> None:
        """Internal initializer (shared by __init__ and unscoped).

        Args:
            db_path: Path to SQLite database file.
            workspace_id: Workspace ID for isolation guard.
            verify: Whether to verify workspace ID after init.
        """
        if db_path is None:
            raise TypeError(
                "CRMStorage requires explicit db_path. "
                "Use CRMStorage.for_workspace(ws_ctx) or pass db_path explicitly."
            )
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._closed = False
        self._workspace_id_verified = False
        self._init_tables()

        # Verify workspace ID if provided
        if verify and workspace_id is not None:
            self.verify_workspace_id(workspace_id)

    @classmethod
    def for_workspace(cls, ws_ctx: "WorkspaceContext") -> "CRMStorage":
        """Factory method to create a workspace-bound CRMStorage.

        This is the preferred way to create a CRMStorage instance.
        It automatically binds to the workspace's CRM database with
        workspace ID verification.

        Args:
            ws_ctx: WorkspaceContext with exports_dir and workspace_id.

        Returns:
            CRMStorage bound to the workspace.

        Example:
            with CRMStorage.for_workspace(ws_ctx) as storage:
                storage.insert_account(...)
        """
        # CRM uses its own db file in exports_dir (not the main workspace.sqlite)
        crm_db_path = ws_ctx.exports_dir / "crm.db"
        return cls(db_path=crm_db_path, workspace_id=ws_ctx.workspace_id)

    @classmethod
    def unscoped(cls, db_path: Path) -> "CRMStorage":
        """Create unscoped CRMStorage for tests/migrations only.

        WARNING: This bypasses workspace verification and should only
        be used in test fixtures or migration scripts.

        Args:
            db_path: Path to SQLite database file.

        Returns:
            CRMStorage without workspace verification.
        """
        instance = object.__new__(cls)
        instance._init_internal(db_path, workspace_id=None, verify=False)
        return instance

    def __enter__(self) -> "CRMStorage":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager, ensuring cleanup."""
        self.close()

    def close(self) -> None:
        """Close the storage and release all database resources.

        This method ensures all SQLite connections are properly closed and
        any WAL/journal files are cleaned up. Call this before deleting
        the database file, especially on Windows.
        """
        if self._closed:
            return
        self._closed = True

        # Force garbage collection to release any lingering connections
        import gc
        gc.collect()

        # Force a checkpoint and close any WAL files
        try:
            conn = sqlite3.connect(self.db_path)
            # Disable WAL mode to ensure no -wal/-shm files remain
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
        except sqlite3.Error:
            pass  # Database may not exist or be accessible

        # Final GC pass
        gc.collect()

    def _init_tables(self) -> None:
        """Initialize CRM tables (migrations)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # PR3: Workspace metadata table for isolation guard
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS crm_workspace_meta (
                    workspace_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL
                )
                """
            )

            # CRM Accounts table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS crm_accounts (
                    account_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    domain TEXT,
                    industry TEXT,
                    location TEXT,
                    description TEXT,
                    employee_count INTEGER,
                    tags TEXT DEFAULT '[]',
                    external_refs TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            # Index on domain for natural key lookups
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_crm_accounts_domain
                ON crm_accounts(domain)
                """
            )

            # M6.1: Unique constraint on domain (when not null) for dedupe
            # Note: SQLite UNIQUE allows multiple NULLs, which is what we want
            cursor.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_crm_accounts_domain_unique
                ON crm_accounts(domain) WHERE domain IS NOT NULL AND domain != ''
                """
            )

            # M6.1: Unique constraint on name+location for accounts without domain
            cursor.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_crm_accounts_name_location
                ON crm_accounts(name, location)
                WHERE domain IS NULL OR domain = ''
                """
            )

            # CRM Contacts table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS crm_contacts (
                    contact_id TEXT PRIMARY KEY,
                    account_id TEXT,
                    full_name TEXT NOT NULL,
                    first_name TEXT,
                    last_name TEXT,
                    role_title TEXT,
                    department TEXT,
                    email TEXT,
                    phone TEXT,
                    linkedin_url TEXT,
                    tags TEXT DEFAULT '[]',
                    persona_type TEXT,
                    hypothesis TEXT,
                    external_refs TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(account_id) REFERENCES crm_accounts(account_id)
                )
                """
            )

            # Index on email for natural key lookups
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_crm_contacts_email
                ON crm_contacts(email)
                """
            )

            # M6.1: Unique constraint on email (when not null) for dedupe
            cursor.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_crm_contacts_email_unique
                ON crm_contacts(email) WHERE email IS NOT NULL AND email != ''
                """
            )

            # M6.1: Unique constraint on account+name+role for contacts without email
            cursor.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_crm_contacts_account_name_role
                ON crm_contacts(account_id, full_name, role_title)
                WHERE email IS NULL OR email = ''
                """
            )

            # Index on account_id for joins
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_crm_contacts_account
                ON crm_contacts(account_id)
                """
            )

            # CRM Activities table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS crm_activities (
                    activity_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    contact_id TEXT,
                    activity_type TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT DEFAULT '',
                    direction TEXT DEFAULT 'outbound',
                    occurred_at TEXT NOT NULL,
                    is_planned INTEGER DEFAULT 0,
                    scheduled_for TEXT,
                    sequence_step INTEGER,
                    sequence_name TEXT,
                    run_id TEXT,
                    artifact_refs TEXT DEFAULT '[]',
                    source_ids TEXT DEFAULT '[]',
                    external_refs TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(account_id) REFERENCES crm_accounts(account_id),
                    FOREIGN KEY(contact_id) REFERENCES crm_contacts(contact_id)
                )
                """
            )

            # Index on run_id for traceability
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_crm_activities_run
                ON crm_activities(run_id)
                """
            )

            # M6.1: Unique constraint on (run_id, artifact_ref, type) for dedupe
            # Uses JSON extraction for artifact_refs (first element)
            cursor.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_crm_activities_run_artifact_type
                ON crm_activities(run_id, activity_type, json_extract(artifact_refs, '$[0]'))
                WHERE run_id IS NOT NULL
                """
            )

            # Index on account_id for queries
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_crm_activities_account
                ON crm_activities(account_id)
                """
            )

            conn.commit()

    # =========================================================================
    # Workspace Metadata (PR3: Isolation Guard)
    # =========================================================================

    def init_workspace_metadata(self, workspace_id: str) -> None:
        """Initialize workspace metadata for a new CRM database.

        Args:
            workspace_id: Workspace ID to set

        Raises:
            ValueError: If workspace metadata already exists with different ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if metadata already exists
            cursor.execute("SELECT workspace_id FROM crm_workspace_meta")
            row = cursor.fetchone()

            if row:
                existing_id = row[0]
                if existing_id != workspace_id:
                    raise ValueError(
                        f"CRM database already initialized with workspace_id {existing_id}, "
                        f"cannot reinitialize with {workspace_id}"
                    )
                # Already initialized with correct ID, just update access time
                cursor.execute(
                    "UPDATE crm_workspace_meta SET last_accessed = ?",
                    (datetime.now(timezone.utc).isoformat(),),
                )
            else:
                # Initialize new workspace metadata
                cursor.execute(
                    """
                    INSERT INTO crm_workspace_meta (workspace_id, created_at, last_accessed)
                    VALUES (?, ?, ?)
                    """,
                    (
                        workspace_id,
                        datetime.now(timezone.utc).isoformat(),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )

            conn.commit()
            self._workspace_id_verified = True

    def get_workspace_id(self) -> Optional[str]:
        """Get the workspace ID from CRM database metadata.

        Returns:
            Workspace ID if set, None if not initialized
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT workspace_id FROM crm_workspace_meta")
            row = cursor.fetchone()
            return row[0] if row else None

    def verify_workspace_id(self, expected_workspace_id: str) -> None:
        """Verify that CRM database workspace ID matches expected ID.

        This is a guard to prevent cross-workspace access.

        Args:
            expected_workspace_id: Expected workspace ID

        Raises:
            WorkspaceMismatchError: If workspace ID doesn't match
        """
        if self._workspace_id_verified:
            return  # Already verified

        actual_id = self.get_workspace_id()

        if actual_id is None:
            # Database not initialized, initialize it now
            self.init_workspace_metadata(expected_workspace_id)
            self._workspace_id_verified = True
            return

        if actual_id != expected_workspace_id:
            from agnetwork.workspaces import WorkspaceMismatchError

            raise WorkspaceMismatchError(expected=expected_workspace_id, actual=actual_id)

        # Update last accessed
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE crm_workspace_meta SET last_accessed = ?",
                (datetime.now(timezone.utc).isoformat(),),
            )
            conn.commit()

        self._workspace_id_verified = True

    # =========================================================================
    # Account Operations
    # =========================================================================

    def insert_account(self, account: Account) -> None:
        """Insert or update an account.

        Args:
            account: Account to insert/update
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO crm_accounts
                (account_id, name, domain, industry, location, description,
                 employee_count, tags, external_refs, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account.account_id,
                    account.name,
                    account.domain,
                    account.industry,
                    account.location,
                    account.description,
                    account.employee_count,
                    json.dumps(account.tags),
                    json.dumps([ref.model_dump() for ref in account.external_refs]),
                    json.dumps(account.metadata),
                    account.created_at.isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def get_account(self, account_id: str) -> Optional[Account]:
        """Get an account by ID.

        Args:
            account_id: Account ID to retrieve

        Returns:
            Account or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM crm_accounts WHERE account_id = ?", (account_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_account(dict(row))
            return None

    def get_account_by_domain(self, domain: str) -> Optional[Account]:
        """Get an account by domain (natural key lookup).

        Args:
            domain: Company domain

        Returns:
            Account or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM crm_accounts WHERE domain = ?", (domain,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_account(dict(row))
            return None

    def list_accounts(self, limit: int = 100) -> List[Account]:
        """List all accounts.

        Args:
            limit: Maximum number of accounts to return

        Returns:
            List of accounts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM crm_accounts ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )
            return [self._row_to_account(dict(row)) for row in cursor.fetchall()]

    def search_accounts(self, query: str, limit: int = 20) -> List[Account]:
        """Search accounts by name or domain.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching accounts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            search_term = f"%{query}%"
            cursor.execute(
                """
                SELECT * FROM crm_accounts
                WHERE name LIKE ? OR domain LIKE ?
                ORDER BY updated_at DESC LIMIT ?
                """,
                (search_term, search_term, limit),
            )
            return [self._row_to_account(dict(row)) for row in cursor.fetchall()]

    def _row_to_account(self, row: Dict[str, Any]) -> Account:
        """Convert a database row to an Account."""
        return Account(
            account_id=row["account_id"],
            name=row["name"],
            domain=row.get("domain"),
            industry=row.get("industry"),
            location=row.get("location"),
            description=row.get("description"),
            employee_count=row.get("employee_count"),
            tags=json.loads(row.get("tags") or "[]"),
            external_refs=[
                ExternalRef(**ref) for ref in json.loads(row.get("external_refs") or "[]")
            ],
            metadata=json.loads(row.get("metadata") or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # =========================================================================
    # Contact Operations
    # =========================================================================

    def insert_contact(self, contact: Contact) -> None:
        """Insert or update a contact.

        Args:
            contact: Contact to insert/update
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO crm_contacts
                (contact_id, account_id, full_name, first_name, last_name,
                 role_title, department, email, phone, linkedin_url, tags,
                 persona_type, hypothesis, external_refs, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    contact.contact_id,
                    contact.account_id,
                    contact.full_name,
                    contact.first_name,
                    contact.last_name,
                    contact.role_title,
                    contact.department,
                    contact.email,
                    contact.phone,
                    contact.linkedin_url,
                    json.dumps(contact.tags),
                    contact.persona_type,
                    contact.hypothesis,
                    json.dumps([ref.model_dump() for ref in contact.external_refs]),
                    json.dumps(contact.metadata),
                    contact.created_at.isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def get_contact(self, contact_id: str) -> Optional[Contact]:
        """Get a contact by ID.

        Args:
            contact_id: Contact ID to retrieve

        Returns:
            Contact or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM crm_contacts WHERE contact_id = ?", (contact_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_contact(dict(row))
            return None

    def get_contact_by_email(self, email: str) -> Optional[Contact]:
        """Get a contact by email (natural key lookup).

        Args:
            email: Contact email

        Returns:
            Contact or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM crm_contacts WHERE email = ?", (email,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_contact(dict(row))
            return None

    def list_contacts(
        self, account_id: Optional[str] = None, limit: int = 100
    ) -> List[Contact]:
        """List contacts, optionally filtered by account.

        Args:
            account_id: Optional account ID to filter by
            limit: Maximum number of contacts to return

        Returns:
            List of contacts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if account_id:
                cursor.execute(
                    """
                    SELECT * FROM crm_contacts
                    WHERE account_id = ?
                    ORDER BY updated_at DESC LIMIT ?
                    """,
                    (account_id, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM crm_contacts ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                )
            return [self._row_to_contact(dict(row)) for row in cursor.fetchall()]

    def search_contacts(self, query: str, limit: int = 20) -> List[Contact]:
        """Search contacts by name or email.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching contacts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            search_term = f"%{query}%"
            cursor.execute(
                """
                SELECT * FROM crm_contacts
                WHERE full_name LIKE ? OR email LIKE ? OR role_title LIKE ?
                ORDER BY updated_at DESC LIMIT ?
                """,
                (search_term, search_term, search_term, limit),
            )
            return [self._row_to_contact(dict(row)) for row in cursor.fetchall()]

    def _row_to_contact(self, row: Dict[str, Any]) -> Contact:
        """Convert a database row to a Contact."""
        return Contact(
            contact_id=row["contact_id"],
            account_id=row.get("account_id"),
            full_name=row["full_name"],
            first_name=row.get("first_name"),
            last_name=row.get("last_name"),
            role_title=row.get("role_title"),
            department=row.get("department"),
            email=row.get("email"),
            phone=row.get("phone"),
            linkedin_url=row.get("linkedin_url"),
            tags=json.loads(row.get("tags") or "[]"),
            persona_type=row.get("persona_type"),
            hypothesis=row.get("hypothesis"),
            external_refs=[
                ExternalRef(**ref) for ref in json.loads(row.get("external_refs") or "[]")
            ],
            metadata=json.loads(row.get("metadata") or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # =========================================================================
    # Activity Operations
    # =========================================================================

    def insert_activity(self, activity: Activity) -> None:
        """Insert or update an activity.

        Args:
            activity: Activity to insert/update
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO crm_activities
                (activity_id, account_id, contact_id, activity_type, subject, body,
                 direction, occurred_at, is_planned, scheduled_for, sequence_step,
                 sequence_name, run_id, artifact_refs, source_ids, external_refs,
                 metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    activity.activity_id,
                    activity.account_id,
                    activity.contact_id,
                    activity.activity_type.value,
                    activity.subject,
                    activity.body,
                    activity.direction.value,
                    activity.occurred_at.isoformat(),
                    1 if activity.is_planned else 0,
                    activity.scheduled_for.isoformat() if activity.scheduled_for else None,
                    activity.sequence_step,
                    activity.sequence_name,
                    activity.run_id,
                    json.dumps(activity.artifact_refs),
                    json.dumps(activity.source_ids),
                    json.dumps([ref.model_dump() for ref in activity.external_refs]),
                    json.dumps(activity.metadata),
                    activity.created_at.isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def get_activity(self, activity_id: str) -> Optional[Activity]:
        """Get an activity by ID.

        Args:
            activity_id: Activity ID to retrieve

        Returns:
            Activity or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM crm_activities WHERE activity_id = ?", (activity_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_activity(dict(row))
            return None

    def list_activities(
        self,
        account_id: Optional[str] = None,
        run_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Activity]:
        """List activities, optionally filtered.

        Args:
            account_id: Optional account ID to filter by
            run_id: Optional run ID to filter by
            limit: Maximum number of activities to return

        Returns:
            List of activities
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            conditions = []
            params: List[Any] = []

            if account_id:
                conditions.append("account_id = ?")
                params.append(account_id)
            if run_id:
                conditions.append("run_id = ?")
                params.append(run_id)

            where_clause = " AND ".join(conditions) if conditions else "1=1"
            params.append(limit)

            cursor.execute(
                f"""
                SELECT * FROM crm_activities
                WHERE {where_clause}
                ORDER BY occurred_at DESC LIMIT ?
                """,
                params,
            )
            return [self._row_to_activity(dict(row)) for row in cursor.fetchall()]

    def get_activities_by_run(self, run_id: str) -> List[Activity]:
        """Get all activities for a specific run.

        Args:
            run_id: Run ID to filter by

        Returns:
            List of activities
        """
        return self.list_activities(run_id=run_id, limit=1000)

    def _row_to_activity(self, row: Dict[str, Any]) -> Activity:
        """Convert a database row to an Activity."""
        return Activity(
            activity_id=row["activity_id"],
            account_id=row["account_id"],
            contact_id=row.get("contact_id"),
            activity_type=ActivityType(row["activity_type"]),
            subject=row["subject"],
            body=row.get("body") or "",
            direction=ActivityDirection(row.get("direction") or "outbound"),
            occurred_at=datetime.fromisoformat(row["occurred_at"]),
            is_planned=bool(row.get("is_planned")),
            scheduled_for=(
                datetime.fromisoformat(row["scheduled_for"])
                if row.get("scheduled_for")
                else None
            ),
            sequence_step=row.get("sequence_step"),
            sequence_name=row.get("sequence_name"),
            run_id=row.get("run_id"),
            artifact_refs=json.loads(row.get("artifact_refs") or "[]"),
            source_ids=json.loads(row.get("source_ids") or "[]"),
            external_refs=[
                ExternalRef(**ref) for ref in json.loads(row.get("external_refs") or "[]")
            ],
            metadata=json.loads(row.get("metadata") or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    def bulk_insert_accounts(self, accounts: List[Account]) -> int:
        """Bulk insert accounts.

        Args:
            accounts: List of accounts to insert

        Returns:
            Number of accounts inserted
        """
        for account in accounts:
            self.insert_account(account)
        return len(accounts)

    def bulk_insert_contacts(self, contacts: List[Contact]) -> int:
        """Bulk insert contacts.

        Args:
            contacts: List of contacts to insert

        Returns:
            Number of contacts inserted
        """
        for contact in contacts:
            self.insert_contact(contact)
        return len(contacts)

    def bulk_insert_activities(self, activities: List[Activity]) -> int:
        """Bulk insert activities.

        Args:
            activities: List of activities to insert

        Returns:
            Number of activities inserted
        """
        for activity in activities:
            self.insert_activity(activity)
        return len(activities)

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> Dict[str, int]:
        """Get CRM storage statistics.

        Returns:
            Dict with counts for accounts, contacts, activities
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM crm_accounts")
            account_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM crm_contacts")
            contact_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM crm_activities")
            activity_count = cursor.fetchone()[0]

            return {
                "accounts": account_count,
                "contacts": contact_count,
                "activities": activity_count,
            }

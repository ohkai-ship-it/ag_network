"""File-based CRM adapter (reference implementation).

Reads/writes CRM data to local CSV/JSON files.
This is the default adapter for M6 (AG_CRM_ADAPTER=file).

Features:
- Import from CSV or JSON files
- Export to CSV or JSON format
- Round-trip support (export → import)
- No external dependencies

Usage:
    adapter = FileCRMAdapter()
    result = adapter.export_data(package, "exports/", format="json")
    result = adapter.import_data("exports/accounts.json")
"""

import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agnetwork.config import config
from agnetwork.crm.adapters.base import (
    AdapterRegistry,
    BaseCRMAdapter,
    ExportResult,
    ImportResult,
    SideEffectCategory,
    requires_approval,
)
from agnetwork.crm.models import (
    Account,
    Activity,
    ActivityDirection,
    ActivityType,
    Contact,
    CRMExportPackage,
    ExternalRef,
)
from agnetwork.crm.storage import CRMStorage


class FileCRMAdapter(BaseCRMAdapter):
    """File-based CRM adapter for local CSV/JSON operations.

    This is the reference adapter for M6. It:
    - Reads CRM data from local SQLite via CRMStorage
    - Imports data from CSV/JSON files into CRMStorage
    - Exports data to CSV/JSON files on disk

    No network operations. Fully testable offline.
    """

    adapter_name = "file"
    supports_push = False

    def __init__(
        self,
        storage: CRMStorage,
        base_path: Optional[Path] = None,
    ):
        """Initialize the file adapter.

        Args:
            storage: CRMStorage instance. REQUIRED.
            base_path: Base path for CSV/JSON file exports. Defaults to data/crm_exports/

        Raises:
            TypeError: If storage is None.
        """
        if storage is None:
            raise TypeError(
                "FileCRMAdapter requires a CRMStorage instance. "
                "Use CRMStorage.for_workspace(ws_ctx) to create one."
            )
        self.storage = storage

        # Base path is for CSV/JSON exports only (not for the SQLite db)
        # Storage handles its own db_path separately
        default_path = config.project_root / "data" / "crm_exports"
        self.base_path = base_path or default_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # Read Operations (delegate to storage)
    # =========================================================================

    def list_accounts(self, limit: int = 100) -> List[Account]:
        """List all accounts from storage."""
        return self.storage.list_accounts(limit=limit)

    def search_accounts(self, query: str, limit: int = 20) -> List[Account]:
        """Search accounts by name or domain."""
        return self.storage.search_accounts(query, limit=limit)

    def list_contacts(
        self, account_id: Optional[str] = None, limit: int = 100
    ) -> List[Contact]:
        """List contacts from storage."""
        return self.storage.list_contacts(account_id=account_id, limit=limit)

    def search_contacts(self, query: str, limit: int = 20) -> List[Contact]:
        """Search contacts by name, email, or title."""
        return self.storage.search_contacts(query, limit=limit)

    def list_activities(
        self, account_id: Optional[str] = None, limit: int = 100
    ) -> List[Activity]:
        """List activities from storage."""
        return self.storage.list_activities(account_id=account_id, limit=limit)

    # =========================================================================
    # Import Operations
    # =========================================================================

    def import_data(
        self,
        file_path: str,
        dry_run: bool = True,
    ) -> ImportResult:
        """Import CRM data from a CSV or JSON file.

        Supports importing:
        - Single entity files (accounts.json, contacts.csv, etc.)
        - Full export packages (directory with manifest.json)

        Args:
            file_path: Path to file or directory to import
            dry_run: If True, validate only without persisting

        Returns:
            ImportResult with counts and any errors
        """
        path = Path(file_path)
        result = ImportResult(success=True, dry_run=dry_run)

        try:
            if path.is_dir():
                # Import from export package directory
                return self._import_package(path, dry_run)
            elif path.suffix.lower() == ".json":
                return self._import_json_file(path, dry_run)
            elif path.suffix.lower() == ".csv":
                return self._import_csv_file(path, dry_run)
            else:
                result.success = False
                result.errors.append(f"Unsupported file type: {path.suffix}")
                return result

        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            return result

    def _import_package(self, dir_path: Path, dry_run: bool) -> ImportResult:
        """Import a full export package directory.

        M6.1: Checks manifest version compatibility before import.
        """
        from agnetwork.crm.version import (
            VersionCompatibility,
            check_version_compatibility,
        )

        result = ImportResult(success=True, dry_run=dry_run)

        # Check for manifest
        manifest_path = dir_path / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)

            # M6.1: Version compatibility check
            manifest_version = manifest_data.get("crm_export_version", "1.0")
            version_check = check_version_compatibility(manifest_version)

            if version_check.status == VersionCompatibility.INCOMPATIBLE:
                result.success = False
                result.errors.append(version_check.message)
                return result
            elif version_check.status == VersionCompatibility.WARN:
                result.warnings.append(version_check.message)
        else:
            result.warnings.append("No manifest.json found, importing individual files")

        # Import each entity type
        for entity_type in ["accounts", "contacts", "activities"]:
            json_path = dir_path / f"{entity_type}.json"
            csv_path = dir_path / f"{entity_type}.csv"

            if json_path.exists():
                sub_result = self._import_json_file(json_path, dry_run)
                self._merge_results(result, sub_result)
            elif csv_path.exists():
                sub_result = self._import_csv_file(csv_path, dry_run)
                self._merge_results(result, sub_result)

        return result

    def _import_json_file(self, file_path: Path, dry_run: bool) -> ImportResult:
        """Import from a JSON file."""
        result = ImportResult(success=True, dry_run=dry_run)

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Determine entity type from filename first (most reliable)
        filename = file_path.stem.lower()
        entity_type = self._detect_entity_type(filename, data)

        if entity_type == "accounts":
            accounts = [self._dict_to_account(item) for item in data]
            result.accounts_imported = len(accounts)
            if not dry_run:
                self.storage.bulk_insert_accounts(accounts)

        elif entity_type == "contacts":
            contacts = [self._dict_to_contact(item) for item in data]
            result.contacts_imported = len(contacts)
            if not dry_run:
                self.storage.bulk_insert_contacts(contacts)

        elif entity_type == "activities":
            activities = [self._dict_to_activity(item) for item in data]
            result.activities_imported = len(activities)
            if not dry_run:
                self.storage.bulk_insert_activities(activities)

        else:
            result.warnings.append(f"Could not determine entity type for {file_path}")

        return result

    def _detect_entity_type(self, filename: str, data: List[Dict[str, Any]]) -> Optional[str]:
        """Detect entity type from filename or data structure.

        Priority: filename > unique field detection
        """
        # Check filename first (most reliable)
        if filename in ("accounts", "account"):
            return "accounts"
        if filename in ("contacts", "contact"):
            return "contacts"
        if filename in ("activities", "activity"):
            return "activities"

        # Fall back to field detection (check for unique fields)
        if not isinstance(data, list) or not data:
            return None

        first_item = data[0]
        # Check for unique identifier fields (contact_id and activity_id are unique)
        # account_id alone is ambiguous since contacts also have account_id as FK
        if "contact_id" in first_item:
            return "contacts"
        if "activity_id" in first_item:
            return "activities"
        # Only match accounts if it has account_id and NOT contact_id/activity_id
        if "account_id" in first_item and "name" in first_item:
            return "accounts"

        return None

    def _import_csv_file(self, file_path: Path, dry_run: bool) -> ImportResult:
        """Import from a CSV file."""
        result = ImportResult(success=True, dry_run=dry_run)

        with open(file_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            result.warnings.append(f"Empty CSV file: {file_path}")
            return result

        # Determine entity type from filename or columns (reuse detection logic)
        filename = file_path.stem.lower()
        entity_type = self._detect_entity_type(filename, rows)

        if entity_type == "accounts":
            accounts = [self._dict_to_account(row) for row in rows]
            result.accounts_imported = len(accounts)
            if not dry_run:
                self.storage.bulk_insert_accounts(accounts)

        elif entity_type == "contacts":
            contacts = [self._dict_to_contact(row) for row in rows]
            result.contacts_imported = len(contacts)
            if not dry_run:
                self.storage.bulk_insert_contacts(contacts)

        elif entity_type == "activities":
            activities = [self._dict_to_activity(row) for row in rows]
            result.activities_imported = len(activities)
            if not dry_run:
                self.storage.bulk_insert_activities(activities)

        else:
            result.warnings.append(f"Could not determine entity type for {file_path}")

        return result

    def _merge_results(self, target: ImportResult, source: ImportResult) -> None:
        """Merge import results."""
        target.accounts_imported += source.accounts_imported
        target.contacts_imported += source.contacts_imported
        target.activities_imported += source.activities_imported
        target.errors.extend(source.errors)
        target.warnings.extend(source.warnings)
        if not source.success:
            target.success = False

    # =========================================================================
    # Export Operations
    # =========================================================================

    @requires_approval(SideEffectCategory.FILE_WRITE)
    def export_data(
        self,
        package: CRMExportPackage,
        output_path: str,
        format: str = "json",
    ) -> ExportResult:
        """Export CRM data to local files.

        Creates a directory with:
        - manifest.json (always JSON)
        - accounts.{format}
        - contacts.{format}
        - activities.{format}

        Args:
            package: CRMExportPackage with data to export
            output_path: Directory to write files
            format: "json" or "csv"

        Returns:
            ExportResult with paths and counts
        """
        result = ExportResult(success=True)
        output_dir = Path(output_path)

        try:
            output_dir.mkdir(parents=True, exist_ok=True)

            # Write manifest (always JSON)
            manifest_path = output_dir / "manifest.json"
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(
                    package.manifest.model_dump(mode="json"),
                    f,
                    indent=2,
                    default=str,
                )
            result.manifest_path = str(manifest_path)

            # Export entities
            if format.lower() == "json":
                self._export_json(package, output_dir)
            elif format.lower() == "csv":
                self._export_csv(package, output_dir)
            else:
                result.success = False
                result.errors.append(f"Unsupported format: {format}")
                return result

            result.output_path = str(output_dir)
            result.accounts_exported = len(package.accounts)
            result.contacts_exported = len(package.contacts)
            result.activities_exported = len(package.activities)

        except Exception as e:
            result.success = False
            result.errors.append(str(e))

        return result

    def _export_json(self, package: CRMExportPackage, output_dir: Path) -> None:
        """Export entities as JSON files."""
        # Accounts
        accounts_path = output_dir / "accounts.json"
        with open(accounts_path, "w", encoding="utf-8") as f:
            json.dump(
                [a.model_dump(mode="json") for a in package.accounts],
                f,
                indent=2,
                default=str,
            )

        # Contacts
        contacts_path = output_dir / "contacts.json"
        with open(contacts_path, "w", encoding="utf-8") as f:
            json.dump(
                [c.model_dump(mode="json") for c in package.contacts],
                f,
                indent=2,
                default=str,
            )

        # Activities
        activities_path = output_dir / "activities.json"
        with open(activities_path, "w", encoding="utf-8") as f:
            json.dump(
                [a.model_dump(mode="json") for a in package.activities],
                f,
                indent=2,
                default=str,
            )

    def _export_csv(self, package: CRMExportPackage, output_dir: Path) -> None:
        """Export entities as CSV files."""
        # Accounts
        if package.accounts:
            accounts_path = output_dir / "accounts.csv"
            self._write_csv(
                accounts_path,
                [self._account_to_flat_dict(a) for a in package.accounts],
            )

        # Contacts
        if package.contacts:
            contacts_path = output_dir / "contacts.csv"
            self._write_csv(
                contacts_path,
                [self._contact_to_flat_dict(c) for c in package.contacts],
            )

        # Activities
        if package.activities:
            activities_path = output_dir / "activities.csv"
            self._write_csv(
                activities_path,
                [self._activity_to_flat_dict(a) for a in package.activities],
            )

    def _write_csv(self, path: Path, rows: List[Dict[str, Any]]) -> None:
        """Write rows to a CSV file."""
        if not rows:
            return

        fieldnames = list(rows[0].keys())
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    # =========================================================================
    # Conversion Helpers
    # =========================================================================

    def _dict_to_account(self, data: Dict[str, Any]) -> Account:
        """Convert a dict to an Account."""
        # Handle nested JSON strings from CSV
        tags = data.get("tags", [])
        if isinstance(tags, str):
            tags = json.loads(tags) if tags else []

        external_refs = data.get("external_refs", [])
        if isinstance(external_refs, str):
            external_refs = json.loads(external_refs) if external_refs else []
            external_refs = [ExternalRef(**ref) for ref in external_refs]
        elif isinstance(external_refs, list) and external_refs and isinstance(external_refs[0], dict):
            external_refs = [ExternalRef(**ref) for ref in external_refs]

        metadata = data.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata) if metadata else {}

        return Account(
            account_id=data.get("account_id") or str(uuid.uuid4()),
            name=data["name"],
            domain=data.get("domain"),
            industry=data.get("industry"),
            location=data.get("location"),
            description=data.get("description"),
            employee_count=int(data["employee_count"]) if data.get("employee_count") else None,
            tags=tags,
            external_refs=external_refs,
            metadata=metadata,
            created_at=self._parse_datetime(data.get("created_at")),
            updated_at=self._parse_datetime(data.get("updated_at")),
        )

    def _dict_to_contact(self, data: Dict[str, Any]) -> Contact:
        """Convert a dict to a Contact."""
        tags = data.get("tags", [])
        if isinstance(tags, str):
            tags = json.loads(tags) if tags else []

        external_refs = data.get("external_refs", [])
        if isinstance(external_refs, str):
            external_refs = json.loads(external_refs) if external_refs else []
            external_refs = [ExternalRef(**ref) for ref in external_refs]
        elif isinstance(external_refs, list) and external_refs and isinstance(external_refs[0], dict):
            external_refs = [ExternalRef(**ref) for ref in external_refs]

        metadata = data.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata) if metadata else {}

        return Contact(
            contact_id=data.get("contact_id") or str(uuid.uuid4()),
            account_id=data.get("account_id"),
            full_name=data["full_name"],
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            role_title=data.get("role_title"),
            department=data.get("department"),
            email=data.get("email"),
            phone=data.get("phone"),
            linkedin_url=data.get("linkedin_url"),
            tags=tags,
            persona_type=data.get("persona_type"),
            hypothesis=data.get("hypothesis"),
            external_refs=external_refs,
            metadata=metadata,
            created_at=self._parse_datetime(data.get("created_at")),
            updated_at=self._parse_datetime(data.get("updated_at")),
        )

    def _dict_to_activity(self, data: Dict[str, Any]) -> Activity:
        """Convert a dict to an Activity."""
        artifact_refs = data.get("artifact_refs", [])
        if isinstance(artifact_refs, str):
            artifact_refs = json.loads(artifact_refs) if artifact_refs else []

        source_ids = data.get("source_ids", [])
        if isinstance(source_ids, str):
            source_ids = json.loads(source_ids) if source_ids else []

        external_refs = data.get("external_refs", [])
        if isinstance(external_refs, str):
            external_refs = json.loads(external_refs) if external_refs else []
            external_refs = [ExternalRef(**ref) for ref in external_refs]
        elif isinstance(external_refs, list) and external_refs and isinstance(external_refs[0], dict):
            external_refs = [ExternalRef(**ref) for ref in external_refs]

        metadata = data.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata) if metadata else {}

        # Parse activity type
        activity_type = data.get("activity_type", "note")
        if isinstance(activity_type, str):
            activity_type = ActivityType(activity_type.lower())

        # Parse direction
        direction = data.get("direction", "outbound")
        if isinstance(direction, str):
            direction = ActivityDirection(direction.lower())

        return Activity(
            activity_id=data.get("activity_id") or str(uuid.uuid4()),
            account_id=data["account_id"],
            contact_id=data.get("contact_id"),
            activity_type=activity_type,
            subject=data["subject"],
            body=data.get("body", ""),
            direction=direction,
            occurred_at=self._parse_datetime(data.get("occurred_at")),
            is_planned=self._parse_bool(data.get("is_planned", False)),
            scheduled_for=self._parse_datetime(data.get("scheduled_for")) if data.get("scheduled_for") else None,
            sequence_step=int(data["sequence_step"]) if data.get("sequence_step") else None,
            sequence_name=data.get("sequence_name"),
            run_id=data.get("run_id"),
            artifact_refs=artifact_refs,
            source_ids=source_ids,
            external_refs=external_refs,
            metadata=metadata,
            created_at=self._parse_datetime(data.get("created_at")),
            updated_at=self._parse_datetime(data.get("updated_at")),
        )

    def _account_to_flat_dict(self, account: Account) -> Dict[str, Any]:
        """Convert Account to flat dict for CSV export."""
        return {
            "account_id": account.account_id,
            "name": account.name,
            "domain": account.domain or "",
            "industry": account.industry or "",
            "location": account.location or "",
            "description": account.description or "",
            "employee_count": account.employee_count or "",
            "tags": json.dumps(account.tags),
            "external_refs": json.dumps([ref.model_dump() for ref in account.external_refs]),
            "metadata": json.dumps(account.metadata),
            "created_at": account.created_at.isoformat(),
            "updated_at": account.updated_at.isoformat(),
        }

    def _contact_to_flat_dict(self, contact: Contact) -> Dict[str, Any]:
        """Convert Contact to flat dict for CSV export."""
        return {
            "contact_id": contact.contact_id,
            "account_id": contact.account_id or "",
            "full_name": contact.full_name,
            "first_name": contact.first_name or "",
            "last_name": contact.last_name or "",
            "role_title": contact.role_title or "",
            "department": contact.department or "",
            "email": contact.email or "",
            "phone": contact.phone or "",
            "linkedin_url": contact.linkedin_url or "",
            "tags": json.dumps(contact.tags),
            "persona_type": contact.persona_type or "",
            "hypothesis": contact.hypothesis or "",
            "external_refs": json.dumps([ref.model_dump() for ref in contact.external_refs]),
            "metadata": json.dumps(contact.metadata),
            "created_at": contact.created_at.isoformat(),
            "updated_at": contact.updated_at.isoformat(),
        }

    def _activity_to_flat_dict(self, activity: Activity) -> Dict[str, Any]:
        """Convert Activity to flat dict for CSV export."""
        return {
            "activity_id": activity.activity_id,
            "account_id": activity.account_id,
            "contact_id": activity.contact_id or "",
            "activity_type": activity.activity_type.value,
            "subject": activity.subject,
            "body": activity.body,
            "direction": activity.direction.value,
            "occurred_at": activity.occurred_at.isoformat(),
            "is_planned": "1" if activity.is_planned else "0",
            "scheduled_for": activity.scheduled_for.isoformat() if activity.scheduled_for else "",
            "sequence_step": activity.sequence_step if activity.sequence_step is not None else "",
            "sequence_name": activity.sequence_name or "",
            "run_id": activity.run_id or "",
            "artifact_refs": json.dumps(activity.artifact_refs),
            "source_ids": json.dumps(activity.source_ids),
            "external_refs": json.dumps([ref.model_dump() for ref in activity.external_refs]),
            "metadata": json.dumps(activity.metadata),
            "created_at": activity.created_at.isoformat(),
            "updated_at": activity.updated_at.isoformat(),
        }

    def _parse_datetime(self, value: Any) -> datetime:
        """Parse a datetime value."""
        if value is None:
            return datetime.now(timezone.utc)
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.now(timezone.utc)

    def _parse_bool(self, value: Any) -> bool:
        """Parse a boolean value."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        if isinstance(value, int):
            return value != 0
        return False


# Register the adapter
AdapterRegistry.register("file", FileCRMAdapter)

"""Base CRM adapter interface and approval gate infrastructure.

Defines the Protocol that all CRM adapters must implement.
Includes the approval gate mechanism for future "push" operations.

M6: Export-only. Push operations require an approval token but
are not implemented in M6. The infrastructure is in place for
future vendor adapters.

Side-effect categories:
- crm_read: Read data from CRM (always allowed)
- crm_write: Write/push data to CRM (requires approval token)

Future vendor adapters (HubSpot, Salesforce, etc.) plug in by:
1. Implementing the CRMAdapter Protocol
2. Registering with the adapter factory
3. Using the @requires_approval decorator for write operations
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Protocol, TypeVar, runtime_checkable

from agnetwork.crm.models import (
    Account,
    Activity,
    Contact,
    CRMExportPackage,
)


class SideEffectCategory(str, Enum):
    """Categories of side effects for approval gating."""

    CRM_READ = "crm_read"  # Read from CRM (always allowed)
    CRM_WRITE = "crm_write"  # Write/push to CRM (requires approval)
    FILE_WRITE = "file_write"  # Write to local files (allowed in M6)


class CRMAdapterError(Exception):
    """Base exception for CRM adapter errors."""

    pass


class ApprovalRequiredError(CRMAdapterError):
    """Raised when an operation requires approval but none was provided."""

    def __init__(self, operation: str, side_effect: SideEffectCategory):
        self.operation = operation
        self.side_effect = side_effect
        super().__init__(
            f"Operation '{operation}' requires approval for side effect: {side_effect.value}"
        )


@dataclass
class ApprovalToken:
    """Token authorizing a side-effect operation.

    In M6, this is infrastructure for future use. No actual
    CRM writes are performed.
    """

    token_id: str
    side_effect: SideEffectCategory
    granted_by: str  # user, system, or test
    granted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        """Check if the token is still valid."""
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True


F = TypeVar("F", bound=Callable[..., Any])


def requires_approval(side_effect: SideEffectCategory) -> Callable[[F], F]:
    """Decorator to mark methods that require approval for side effects.

    This ensures that any method performing CRM writes must receive
    an approval token. If no token is provided, raises ApprovalRequiredError.

    Usage:
        @requires_approval(SideEffectCategory.CRM_WRITE)
        def push_contacts(self, contacts, approval_token=None):
            ...

    Args:
        side_effect: The category of side effect this method performs

    Returns:
        Decorated function that checks for approval
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            # Check for approval token in kwargs
            approval_token: Optional[ApprovalToken] = kwargs.get("approval_token")

            # CRM_READ and FILE_WRITE don't require approval in M6
            if side_effect in (SideEffectCategory.CRM_READ, SideEffectCategory.FILE_WRITE):
                return func(self, *args, **kwargs)

            # CRM_WRITE requires approval
            if side_effect == SideEffectCategory.CRM_WRITE:
                if approval_token is None:
                    raise ApprovalRequiredError(func.__name__, side_effect)

                if not approval_token.is_valid():
                    raise ApprovalRequiredError(
                        f"{func.__name__} (token expired)", side_effect
                    )

                if approval_token.side_effect != side_effect:
                    raise ApprovalRequiredError(
                        f"{func.__name__} (wrong side effect)", side_effect
                    )

            return func(self, *args, **kwargs)

        return wrapper  # type: ignore

    return decorator


@dataclass
class ImportResult:
    """Result of a CRM import operation."""

    success: bool
    accounts_imported: int = 0
    contacts_imported: int = 0
    activities_imported: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    dry_run: bool = False


@dataclass
class ExportResult:
    """Result of a CRM export operation."""

    success: bool
    output_path: Optional[str] = None
    accounts_exported: int = 0
    contacts_exported: int = 0
    activities_exported: int = 0
    manifest_path: Optional[str] = None
    errors: List[str] = field(default_factory=list)


@runtime_checkable
class CRMAdapter(Protocol):
    """Protocol defining the CRM adapter interface.

    All CRM adapters (File, HubSpot, Salesforce, etc.) must implement
    this interface. The interface supports:

    - Listing/searching accounts, contacts, activities (read)
    - Importing data from external sources
    - Exporting data to external formats/systems

    M6 scope: Only local file operations are implemented.
    Future adapters will implement push_* methods with approval gates.
    """

    # =========================================================================
    # Read Operations (always allowed)
    # =========================================================================

    def list_accounts(self, limit: int = 100) -> List[Account]:
        """List all accounts.

        Args:
            limit: Maximum number of accounts to return

        Returns:
            List of Account objects
        """
        ...

    def search_accounts(self, query: str, limit: int = 20) -> List[Account]:
        """Search accounts by name or domain.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching Account objects
        """
        ...

    def list_contacts(
        self, account_id: Optional[str] = None, limit: int = 100
    ) -> List[Contact]:
        """List contacts, optionally filtered by account.

        Args:
            account_id: Optional account ID to filter by
            limit: Maximum number of contacts to return

        Returns:
            List of Contact objects
        """
        ...

    def search_contacts(self, query: str, limit: int = 20) -> List[Contact]:
        """Search contacts by name, email, or title.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching Contact objects
        """
        ...

    def list_activities(
        self, account_id: Optional[str] = None, limit: int = 100
    ) -> List[Activity]:
        """List activities, optionally filtered by account.

        Args:
            account_id: Optional account ID to filter by
            limit: Maximum number of activities to return

        Returns:
            List of Activity objects
        """
        ...

    # =========================================================================
    # Import Operations (read from external source)
    # =========================================================================

    def import_data(
        self,
        file_path: str,
        dry_run: bool = True,
    ) -> ImportResult:
        """Import data from an external file.

        Default behavior is dry_run=True (validate but don't persist).

        Args:
            file_path: Path to the import file (CSV or JSON)
            dry_run: If True, validate only without persisting

        Returns:
            ImportResult with counts and any errors
        """
        ...

    # =========================================================================
    # Export Operations (write to local files)
    # =========================================================================

    def export_data(
        self,
        package: CRMExportPackage,
        output_path: str,
        format: str = "json",
    ) -> ExportResult:
        """Export CRM data to local files.

        Args:
            package: CRMExportPackage containing data to export
            output_path: Directory to write export files
            format: Output format ("json" or "csv")

        Returns:
            ExportResult with output path and counts
        """
        ...

    # =========================================================================
    # Future: Push Operations (require approval, not implemented in M6)
    # =========================================================================
    # These methods are defined in the protocol for future implementation.
    # In M6, they raise NotImplementedError or ApprovalRequiredError.

    # @requires_approval(SideEffectCategory.CRM_WRITE)
    # def push_accounts(
    #     self,
    #     accounts: List[Account],
    #     approval_token: Optional[ApprovalToken] = None,
    # ) -> PushResult:
    #     """Push accounts to external CRM. Requires approval."""
    #     ...


class BaseCRMAdapter(ABC):
    """Abstract base class for CRM adapters.

    Provides common functionality and enforces the interface.
    Concrete adapters should inherit from this class.
    """

    adapter_name: str = "base"
    supports_push: bool = False  # M6: No adapters support push yet

    @abstractmethod
    def list_accounts(self, limit: int = 100) -> List[Account]:
        """List all accounts."""
        pass

    @abstractmethod
    def search_accounts(self, query: str, limit: int = 20) -> List[Account]:
        """Search accounts."""
        pass

    @abstractmethod
    def list_contacts(
        self, account_id: Optional[str] = None, limit: int = 100
    ) -> List[Contact]:
        """List contacts."""
        pass

    @abstractmethod
    def search_contacts(self, query: str, limit: int = 20) -> List[Contact]:
        """Search contacts."""
        pass

    @abstractmethod
    def list_activities(
        self, account_id: Optional[str] = None, limit: int = 100
    ) -> List[Activity]:
        """List activities."""
        pass

    @abstractmethod
    def import_data(
        self,
        file_path: str,
        dry_run: bool = True,
    ) -> ImportResult:
        """Import data from file."""
        pass

    @abstractmethod
    def export_data(
        self,
        package: CRMExportPackage,
        output_path: str,
        format: str = "json",
    ) -> ExportResult:
        """Export data to files."""
        pass


# =============================================================================
# Adapter Registry (for future vendor adapters)
# =============================================================================


class AdapterRegistry:
    """Registry of available CRM adapters.

    Future vendor adapters register themselves here.
    """

    _adapters: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str, adapter_class: type) -> None:
        """Register an adapter class.

        Args:
            name: Adapter name (e.g., "file", "hubspot", "salesforce")
            adapter_class: Class implementing CRMAdapter protocol
        """
        cls._adapters[name] = adapter_class

    @classmethod
    def get(cls, name: str) -> Optional[type]:
        """Get an adapter class by name.

        Args:
            name: Adapter name

        Returns:
            Adapter class or None if not found
        """
        return cls._adapters.get(name)

    @classmethod
    def list_adapters(cls) -> List[str]:
        """List all registered adapter names.

        Returns:
            List of adapter names
        """
        return list(cls._adapters.keys())


def get_adapter(
    name: Optional[str] = None,
    **kwargs: Any,
) -> "CRMAdapter":
    """Get a CRM adapter instance by name.

    Args:
        name: Adapter name. Defaults to AG_CRM_ADAPTER env var or "file"
        **kwargs: Additional arguments passed to adapter constructor

    Returns:
        CRMAdapter instance

    Raises:
        CRMAdapterError: If adapter not found
    """
    import os

    if name is None:
        name = os.getenv("AG_CRM_ADAPTER", "file")

    adapter_class = AdapterRegistry.get(name)
    if adapter_class is None:
        available = AdapterRegistry.list_adapters()
        raise CRMAdapterError(
            f"Unknown CRM adapter: '{name}'. Available: {available}"
        )

    return adapter_class(**kwargs)

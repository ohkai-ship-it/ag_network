"""Core connector abstractions and protocols (M6.1).

Defines the foundation for vendor connectors (HubSpot, Salesforce, etc.):
- Connector Protocol: Interface all connectors must implement
- AuthStrategy: Authentication method abstraction
- RequestPolicy: Rate limiting, retries, timeouts
- ConnectorError hierarchy: Typed exceptions

This is preparation only - no real vendor integrations in M6.1.
Everything is offline-testable.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Set, runtime_checkable

# =============================================================================
# Connector Capabilities
# =============================================================================


class ConnectorCapability(str, Enum):
    """Capabilities a connector may support."""

    # Read capabilities
    READ_ACCOUNTS = "read_accounts"
    READ_CONTACTS = "read_contacts"
    READ_ACTIVITIES = "read_activities"
    READ_DEALS = "read_deals"
    SEARCH = "search"

    # Write capabilities
    WRITE_ACCOUNTS = "write_accounts"
    WRITE_CONTACTS = "write_contacts"
    WRITE_ACTIVITIES = "write_activities"
    WRITE_DEALS = "write_deals"

    # Sync capabilities
    SYNC_BIDIRECTIONAL = "sync_bidirectional"
    WEBHOOKS = "webhooks"


# =============================================================================
# Authentication Strategies
# =============================================================================


class AuthType(str, Enum):
    """Type of authentication strategy."""

    NONE = "none"
    API_KEY = "api_key"
    OAUTH_TOKEN = "oauth_token"
    BASIC = "basic"


@dataclass
class AuthStrategy:
    """Base authentication strategy (data holder).

    Subclasses define specific authentication methods.
    No actual authentication happens in M6.1 - these are placeholders.
    """

    auth_type: AuthType = AuthType.NONE

    def is_configured(self) -> bool:
        """Check if authentication is properly configured."""
        return True

    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers for requests."""
        return {}


@dataclass
class NoAuth(AuthStrategy):
    """No authentication required."""

    auth_type: AuthType = field(default=AuthType.NONE, init=False)


@dataclass
class ApiKeyAuth(AuthStrategy):
    """API key authentication.

    Typical usage: Authorization: Bearer <key> or X-API-Key: <key>
    """

    auth_type: AuthType = field(default=AuthType.API_KEY, init=False)
    api_key: str = ""
    header_name: str = "Authorization"
    header_prefix: str = "Bearer"

    def is_configured(self) -> bool:
        """Check if API key is set."""
        return bool(self.api_key)

    def get_headers(self) -> Dict[str, str]:
        """Get authorization header."""
        if not self.api_key:
            return {}
        if self.header_prefix:
            return {self.header_name: f"{self.header_prefix} {self.api_key}"}
        return {self.header_name: self.api_key}


@dataclass
class OAuthTokenAuth(AuthStrategy):
    """OAuth token authentication (placeholder for future OAuth flows).

    M6.1: No actual OAuth implementation. Just holds token data.
    """

    auth_type: AuthType = field(default=AuthType.OAUTH_TOKEN, init=False)
    access_token: str = ""
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_at: Optional[datetime] = None

    def is_configured(self) -> bool:
        """Check if token is set."""
        return bool(self.access_token)

    def is_expired(self) -> bool:
        """Check if token is expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def get_headers(self) -> Dict[str, str]:
        """Get authorization header."""
        if not self.access_token:
            return {}
        return {"Authorization": f"{self.token_type} {self.access_token}"}


@dataclass
class BasicAuth(AuthStrategy):
    """Basic authentication (username/password)."""

    auth_type: AuthType = field(default=AuthType.BASIC, init=False)
    username: str = ""
    password: str = ""

    def is_configured(self) -> bool:
        """Check if credentials are set."""
        return bool(self.username and self.password)


# =============================================================================
# Request Policy
# =============================================================================


@dataclass
class RequestPolicy:
    """Policy for HTTP requests: timeouts, retries, rate limits.

    Used by http_client to enforce consistent behavior.
    """

    # Timeouts
    connect_timeout: float = 10.0  # seconds
    read_timeout: float = 30.0  # seconds
    total_timeout: float = 60.0  # seconds

    # Retries
    max_retries: int = 3
    retry_delay: float = 1.0  # base delay in seconds
    retry_backoff: float = 2.0  # exponential backoff multiplier
    retry_on_status: List[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])

    # Rate limiting (per host)
    requests_per_second: Optional[float] = None  # None = no limit
    burst_size: int = 10  # max burst before throttling

    # Headers
    user_agent: str = "agnetwork/1.0"
    default_headers: Dict[str, str] = field(default_factory=dict)

    def get_timeout_tuple(self) -> tuple:
        """Get timeout as (connect, read) tuple for httpx."""
        return (self.connect_timeout, self.read_timeout)


# Default policies for common scenarios
DEFAULT_POLICY = RequestPolicy()

CONSERVATIVE_POLICY = RequestPolicy(
    max_retries=5,
    retry_delay=2.0,
    requests_per_second=1.0,
    connect_timeout=15.0,
    read_timeout=45.0,
)

AGGRESSIVE_POLICY = RequestPolicy(
    max_retries=2,
    retry_delay=0.5,
    connect_timeout=5.0,
    read_timeout=15.0,
)


# =============================================================================
# Connector Error Hierarchy
# =============================================================================


class ConnectorError(Exception):
    """Base exception for connector errors."""

    def __init__(self, message: str, connector_name: str = "", details: Optional[Dict[str, Any]] = None):
        self.connector_name = connector_name
        self.details = details or {}
        super().__init__(message)


class ConnectionError(ConnectorError):
    """Failed to connect to the service."""

    pass


class TimeoutError(ConnectorError):
    """Request timed out."""

    def __init__(
        self,
        message: str = "Request timed out",
        connector_name: str = "",
        timeout_seconds: Optional[float] = None,
    ):
        super().__init__(message, connector_name, {"timeout_seconds": timeout_seconds})
        self.timeout_seconds = timeout_seconds


class AuthenticationError(ConnectorError):
    """Authentication failed (invalid credentials, expired token, etc.)."""

    pass


class AuthorizationError(ConnectorError):
    """Authorized but not permitted (insufficient permissions)."""

    pass


class RateLimitError(ConnectorError):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        connector_name: str = "",
        retry_after: Optional[float] = None,
    ):
        super().__init__(message, connector_name, {"retry_after": retry_after})
        self.retry_after = retry_after


class ValidationError(ConnectorError):
    """Request validation failed (bad data, missing fields, etc.)."""

    def __init__(
        self,
        message: str,
        connector_name: str = "",
        field_errors: Optional[Dict[str, str]] = None,
    ):
        super().__init__(message, connector_name, {"field_errors": field_errors or {}})
        self.field_errors = field_errors or {}


class ResourceNotFoundError(ConnectorError):
    """Requested resource not found."""

    def __init__(
        self,
        message: str = "Resource not found",
        connector_name: str = "",
        resource_type: str = "",
        resource_id: str = "",
    ):
        super().__init__(
            message, connector_name, {"resource_type": resource_type, "resource_id": resource_id}
        )
        self.resource_type = resource_type
        self.resource_id = resource_id


class ConflictError(ConnectorError):
    """Resource conflict (duplicate, version mismatch, etc.)."""

    pass


class ServiceUnavailableError(ConnectorError):
    """Service is temporarily unavailable."""

    pass


# =============================================================================
# Connector Protocol
# =============================================================================


@runtime_checkable
class Connector(Protocol):
    """Protocol defining the connector interface.

    All vendor connectors (HubSpot, Salesforce, etc.) must implement this.
    M6.1: Only health_check is required; other methods are optional.
    """

    @property
    def name(self) -> str:
        """Connector name (e.g., 'hubspot', 'salesforce')."""
        ...

    @property
    def capabilities(self) -> Set[ConnectorCapability]:
        """Set of capabilities this connector supports."""
        ...

    def health_check(self) -> bool:
        """Check if the connector is healthy and can connect.

        Returns:
            True if healthy, False otherwise
        """
        ...


class BaseConnector(ABC):
    """Abstract base class for connectors.

    Provides common functionality and enforces the interface.
    """

    _name: str = "base"
    _capabilities: Set[ConnectorCapability] = set()

    def __init__(
        self,
        auth: Optional[AuthStrategy] = None,
        policy: Optional[RequestPolicy] = None,
    ):
        """Initialize the connector.

        Args:
            auth: Authentication strategy
            policy: Request policy (timeouts, retries, etc.)
        """
        self.auth = auth or NoAuth()
        self.policy = policy or DEFAULT_POLICY

    @property
    def name(self) -> str:
        """Connector name."""
        return self._name

    @property
    def capabilities(self) -> Set[ConnectorCapability]:
        """Set of capabilities this connector supports."""
        return self._capabilities

    def has_capability(self, capability: ConnectorCapability) -> bool:
        """Check if connector has a specific capability."""
        return capability in self._capabilities

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the connector is healthy."""
        pass


# =============================================================================
# Connector Registry
# =============================================================================


class ConnectorRegistry:
    """Registry of available connectors.

    Similar to CRMAdapterRegistry, but for external service connectors.
    """

    _connectors: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str, connector_class: type) -> None:
        """Register a connector class.

        Args:
            name: Connector name (e.g., "hubspot", "salesforce")
            connector_class: Class implementing Connector protocol
        """
        cls._connectors[name.lower()] = connector_class

    @classmethod
    def unregister(cls, name: str) -> None:
        """Unregister a connector."""
        cls._connectors.pop(name.lower(), None)

    @classmethod
    def get(cls, name: str) -> Optional[type]:
        """Get a connector class by name."""
        return cls._connectors.get(name.lower())

    @classmethod
    def list_connectors(cls) -> List[str]:
        """List all registered connector names."""
        return list(cls._connectors.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a connector is registered."""
        return name.lower() in cls._connectors

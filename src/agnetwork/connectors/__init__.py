"""Connector layer for external service integrations (M6.1).

This module provides the foundation for connecting to external CRM
and sales services (HubSpot, Salesforce, Pipedrive, etc.).

M6.1 scope: Skeleton only, no real vendor implementations.

Key components:
- Connector Protocol: Interface all connectors must implement
- AuthStrategy: Authentication abstraction (NoAuth, ApiKeyAuth, OAuthTokenAuth)
- RequestPolicy: Rate limiting, retries, timeouts
- HTTPClient: httpx wrapper with policy enforcement
- DummyConnector: Test connector without network calls
"""

from .base import (
    AGGRESSIVE_POLICY,
    CONSERVATIVE_POLICY,
    DEFAULT_POLICY,
    ApiKeyAuth,
    AuthenticationError,
    AuthorizationError,
    AuthStrategy,
    # Authentication
    AuthType,
    BaseConnector,
    BasicAuth,
    ConflictError,
    ConnectionError,
    # Protocol and base class
    Connector,
    # Capabilities
    ConnectorCapability,
    # Error hierarchy
    ConnectorError,
    ConnectorRegistry,
    NoAuth,
    OAuthTokenAuth,
    RateLimitError,
    # Request policy
    RequestPolicy,
    ResourceNotFoundError,
    ServiceUnavailableError,
    TimeoutError,
    ValidationError,
)
from .dummy import (
    DummyConnector,
    DummyResponse,
    FailingConnector,
    NullConnector,
)

# HTTP client is optional - only import if httpx is available
try:
    from .http_client import (
        HTTPX_AVAILABLE,
        AsyncHTTPClient,
        HTTPClient,
        HTTPResponse,
    )
except ImportError:
    # httpx not installed - HTTP clients not available
    HTTPClient = None  # type: ignore
    AsyncHTTPClient = None  # type: ignore
    HTTPResponse = None  # type: ignore
    HTTPX_AVAILABLE = False


__all__ = [
    # Protocol and base
    "Connector",
    "BaseConnector",
    "ConnectorRegistry",
    # Capabilities
    "ConnectorCapability",
    # Auth
    "AuthType",
    "AuthStrategy",
    "NoAuth",
    "ApiKeyAuth",
    "OAuthTokenAuth",
    "BasicAuth",
    # Policy
    "RequestPolicy",
    "DEFAULT_POLICY",
    "CONSERVATIVE_POLICY",
    "AGGRESSIVE_POLICY",
    # Errors
    "ConnectorError",
    "ConnectionError",
    "TimeoutError",
    "AuthenticationError",
    "AuthorizationError",
    "RateLimitError",
    "ValidationError",
    "ResourceNotFoundError",
    "ConflictError",
    "ServiceUnavailableError",
    # Dummy connectors
    "DummyConnector",
    "DummyResponse",
    "NullConnector",
    "FailingConnector",
    # HTTP client (optional)
    "HTTPClient",
    "AsyncHTTPClient",
    "HTTPResponse",
    "HTTPX_AVAILABLE",
]

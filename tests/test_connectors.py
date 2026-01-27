"""Tests for connector layer (M6.1).

Tests cover:
- Connector protocol and base class
- Authentication strategies
- Request policy
- Error hierarchy
- DummyConnector functionality
- ConnectorRegistry

No network calls - all tests are offline.
"""

import pytest

from agnetwork.connectors import (
    AGGRESSIVE_POLICY,
    CONSERVATIVE_POLICY,
    DEFAULT_POLICY,
    ApiKeyAuth,
    AuthenticationError,
    AuthType,
    BasicAuth,
    # Protocol and base
    Connector,
    ConnectorCapability,
    # Errors
    ConnectorError,
    ConnectorRegistry,
    # Dummy
    DummyConnector,
    DummyResponse,
    FailingConnector,
    NoAuth,
    NullConnector,
    OAuthTokenAuth,
    RateLimitError,
    # Policy
    RequestPolicy,
    ResourceNotFoundError,
    TimeoutError,
    ValidationError,
)

# =============================================================================
# Authentication Strategy Tests
# =============================================================================


class TestNoAuth:
    """Tests for NoAuth strategy."""

    def test_auth_type(self):
        """NoAuth has correct auth type."""
        auth = NoAuth()
        assert auth.auth_type == AuthType.NONE

    def test_is_configured(self):
        """NoAuth is always configured."""
        auth = NoAuth()
        assert auth.is_configured() is True

    def test_get_headers(self):
        """NoAuth returns empty headers."""
        auth = NoAuth()
        assert auth.get_headers() == {}


class TestApiKeyAuth:
    """Tests for ApiKeyAuth strategy."""

    def test_auth_type(self):
        """ApiKeyAuth has correct auth type."""
        auth = ApiKeyAuth(api_key="test-key")
        assert auth.auth_type == AuthType.API_KEY

    def test_is_configured_with_key(self):
        """ApiKeyAuth is configured when key is set."""
        auth = ApiKeyAuth(api_key="test-key")
        assert auth.is_configured() is True

    def test_is_configured_without_key(self):
        """ApiKeyAuth is not configured without key."""
        auth = ApiKeyAuth()
        assert auth.is_configured() is False

    def test_get_headers_default_format(self):
        """ApiKeyAuth returns Bearer token by default."""
        auth = ApiKeyAuth(api_key="test-key")
        headers = auth.get_headers()
        assert headers == {"Authorization": "Bearer test-key"}

    def test_get_headers_custom_format(self):
        """ApiKeyAuth supports custom header format."""
        auth = ApiKeyAuth(
            api_key="test-key",
            header_name="X-API-Key",
            header_prefix="",
        )
        headers = auth.get_headers()
        assert headers == {"X-API-Key": "test-key"}

    def test_get_headers_no_key(self):
        """ApiKeyAuth returns empty headers without key."""
        auth = ApiKeyAuth()
        assert auth.get_headers() == {}


class TestOAuthTokenAuth:
    """Tests for OAuthTokenAuth strategy."""

    def test_auth_type(self):
        """OAuthTokenAuth has correct auth type."""
        auth = OAuthTokenAuth(access_token="token123")
        assert auth.auth_type == AuthType.OAUTH_TOKEN

    def test_is_configured_with_token(self):
        """OAuthTokenAuth is configured when token is set."""
        auth = OAuthTokenAuth(access_token="token123")
        assert auth.is_configured() is True

    def test_is_configured_without_token(self):
        """OAuthTokenAuth is not configured without token."""
        auth = OAuthTokenAuth()
        assert auth.is_configured() is False

    def test_get_headers(self):
        """OAuthTokenAuth returns authorization header."""
        auth = OAuthTokenAuth(access_token="token123")
        headers = auth.get_headers()
        assert headers == {"Authorization": "Bearer token123"}

    def test_is_expired_no_expiry(self):
        """OAuthTokenAuth without expiry is not expired."""
        auth = OAuthTokenAuth(access_token="token123")
        assert auth.is_expired() is False

    def test_is_expired_with_future_expiry(self):
        """OAuthTokenAuth with future expiry is not expired."""
        from datetime import datetime, timedelta, timezone

        future = datetime.now(timezone.utc) + timedelta(hours=1)
        auth = OAuthTokenAuth(access_token="token123", expires_at=future)
        assert auth.is_expired() is False

    def test_is_expired_with_past_expiry(self):
        """OAuthTokenAuth with past expiry is expired."""
        from datetime import datetime, timedelta, timezone

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        auth = OAuthTokenAuth(access_token="token123", expires_at=past)
        assert auth.is_expired() is True


class TestBasicAuth:
    """Tests for BasicAuth strategy."""

    def test_auth_type(self):
        """BasicAuth has correct auth type."""
        auth = BasicAuth(username="user", password="pass")
        assert auth.auth_type == AuthType.BASIC

    def test_is_configured_with_credentials(self):
        """BasicAuth is configured with both credentials."""
        auth = BasicAuth(username="user", password="pass")
        assert auth.is_configured() is True

    def test_is_configured_missing_username(self):
        """BasicAuth is not configured without username."""
        auth = BasicAuth(password="pass")
        assert auth.is_configured() is False

    def test_is_configured_missing_password(self):
        """BasicAuth is not configured without password."""
        auth = BasicAuth(username="user")
        assert auth.is_configured() is False


# =============================================================================
# Request Policy Tests
# =============================================================================


class TestRequestPolicy:
    """Tests for RequestPolicy."""

    def test_default_values(self):
        """RequestPolicy has sensible defaults."""
        policy = RequestPolicy()
        assert policy.connect_timeout == 10.0
        assert policy.read_timeout == 30.0
        assert policy.max_retries == 3
        assert policy.retry_backoff == 2.0
        assert 429 in policy.retry_on_status
        assert 500 in policy.retry_on_status

    def test_get_timeout_tuple(self):
        """get_timeout_tuple returns correct format."""
        policy = RequestPolicy(connect_timeout=5.0, read_timeout=15.0)
        assert policy.get_timeout_tuple() == (5.0, 15.0)

    def test_conservative_policy(self):
        """CONSERVATIVE_POLICY has higher limits."""
        assert CONSERVATIVE_POLICY.max_retries > DEFAULT_POLICY.max_retries
        assert CONSERVATIVE_POLICY.retry_delay > DEFAULT_POLICY.retry_delay

    def test_aggressive_policy(self):
        """AGGRESSIVE_POLICY has lower limits."""
        assert AGGRESSIVE_POLICY.max_retries < DEFAULT_POLICY.max_retries
        assert AGGRESSIVE_POLICY.connect_timeout < DEFAULT_POLICY.connect_timeout


# =============================================================================
# Connector Error Tests
# =============================================================================


class TestConnectorErrors:
    """Tests for connector error hierarchy."""

    def test_connector_error_base(self):
        """ConnectorError stores basic info."""
        error = ConnectorError("Test error", connector_name="test", details={"key": "value"})
        assert str(error) == "Test error"
        assert error.connector_name == "test"
        assert error.details == {"key": "value"}

    def test_authentication_error(self):
        """AuthenticationError is a ConnectorError."""
        error = AuthenticationError("Bad token", connector_name="hubspot")
        assert isinstance(error, ConnectorError)
        assert error.connector_name == "hubspot"

    def test_rate_limit_error(self):
        """RateLimitError stores retry_after."""
        error = RateLimitError(retry_after=60.0)
        assert error.retry_after == 60.0

    def test_timeout_error(self):
        """TimeoutError stores timeout_seconds."""
        error = TimeoutError(timeout_seconds=30.0)
        assert error.timeout_seconds == 30.0

    def test_resource_not_found_error(self):
        """ResourceNotFoundError stores resource info."""
        error = ResourceNotFoundError(
            resource_type="contact",
            resource_id="123",
        )
        assert error.resource_type == "contact"
        assert error.resource_id == "123"

    def test_validation_error(self):
        """ValidationError stores field errors."""
        error = ValidationError(
            "Invalid data",
            field_errors={"email": "Invalid format"},
        )
        assert error.field_errors == {"email": "Invalid format"}


# =============================================================================
# DummyConnector Tests
# =============================================================================


class TestDummyConnector:
    """Tests for DummyConnector."""

    def test_name(self):
        """DummyConnector has correct name."""
        connector = DummyConnector()
        assert connector.name == "dummy"

    def test_capabilities(self):
        """DummyConnector has expected capabilities."""
        connector = DummyConnector()
        assert ConnectorCapability.READ_ACCOUNTS in connector.capabilities
        assert ConnectorCapability.WRITE_CONTACTS in connector.capabilities

    def test_health_check_default(self):
        """DummyConnector is healthy by default."""
        connector = DummyConnector()
        assert connector.health_check() is True

    def test_health_check_unhealthy(self):
        """DummyConnector can be set unhealthy."""
        connector = DummyConnector(healthy=False)
        assert connector.health_check() is False

    def test_set_healthy(self):
        """DummyConnector health can be toggled."""
        connector = DummyConnector(healthy=True)
        connector.set_healthy(False)
        assert connector.health_check() is False

    def test_call_logging(self):
        """DummyConnector logs all calls."""
        connector = DummyConnector()
        connector.get_account("123")
        connector.list_contacts(company="Acme")

        log = connector.get_call_log()
        assert len(log) == 2
        assert log[0]["operation"] == "get_account"
        assert log[0]["args"] == {"account_id": "123"}
        assert log[1]["operation"] == "list_contacts"

    def test_was_called(self):
        """was_called() checks if operation was called."""
        connector = DummyConnector()
        connector.get_account("123")

        assert connector.was_called("get_account") is True
        assert connector.was_called("list_contacts") is False

    def test_call_count(self):
        """call_count() counts operation calls."""
        connector = DummyConnector()
        connector.get_account("1")
        connector.get_account("2")
        connector.get_contact("3")

        assert connector.call_count("get_account") == 2
        assert connector.call_count("get_contact") == 1
        assert connector.call_count("list_accounts") == 0

    def test_set_response_data(self):
        """DummyConnector returns configured response data."""
        connector = DummyConnector()
        connector.set_response(
            "get_account",
            DummyResponse(data={"id": "123", "name": "Acme"}),
        )

        result = connector.get_account("123")
        assert result == {"id": "123", "name": "Acme"}

    def test_set_response_error(self):
        """DummyConnector raises configured error."""
        connector = DummyConnector()
        connector.set_response(
            "get_account",
            DummyResponse(error=ResourceNotFoundError("Not found")),
        )

        with pytest.raises(ResourceNotFoundError):
            connector.get_account("123")

    def test_clear_responses(self):
        """clear_responses() removes all configured responses."""
        connector = DummyConnector()
        connector.set_response("get_account", DummyResponse(data={"id": "123"}))
        connector.clear_responses()

        result = connector.get_account("123")
        assert result is None  # Default response

    def test_clear_call_log(self):
        """clear_call_log() clears the log."""
        connector = DummyConnector()
        connector.get_account("123")
        connector.clear_call_log()

        assert connector.get_call_log() == []

    def test_create_account_default(self):
        """create_account returns default response."""
        connector = DummyConnector()
        result = connector.create_account({"name": "NewCorp"})

        assert result["name"] == "NewCorp"
        assert "id" in result

    def test_implements_protocol(self):
        """DummyConnector implements Connector protocol."""
        connector = DummyConnector()
        assert isinstance(connector, Connector)


class TestNullConnector:
    """Tests for NullConnector."""

    def test_name(self):
        """NullConnector has correct name."""
        connector = NullConnector()
        assert connector.name == "null"

    def test_no_capabilities(self):
        """NullConnector has no capabilities."""
        connector = NullConnector()
        assert connector.capabilities == set()

    def test_health_check(self):
        """NullConnector is always healthy."""
        connector = NullConnector()
        assert connector.health_check() is True

    def test_returns_none_or_empty(self):
        """NullConnector returns None or empty collections."""
        connector = NullConnector()
        assert connector.get_account("123") is None
        assert connector.list_accounts() == []
        assert connector.create_account({}) == {}


class TestFailingConnector:
    """Tests for FailingConnector."""

    def test_name(self):
        """FailingConnector has correct name."""
        connector = FailingConnector()
        assert connector.name == "failing"

    def test_health_check_fails(self):
        """FailingConnector is never healthy."""
        connector = FailingConnector()
        assert connector.health_check() is False

    def test_operations_fail(self):
        """FailingConnector operations raise errors."""
        connector = FailingConnector()

        with pytest.raises(ConnectorError):
            connector.get_account("123")

        with pytest.raises(ConnectorError):
            connector.list_accounts()

    def test_custom_error(self):
        """FailingConnector can use custom error."""
        custom_error = AuthenticationError("Custom auth failure")
        connector = FailingConnector(error=custom_error)

        with pytest.raises(AuthenticationError) as exc:
            connector.get_account("123")

        assert "Custom auth failure" in str(exc.value)


# =============================================================================
# ConnectorRegistry Tests
# =============================================================================


class TestConnectorRegistry:
    """Tests for ConnectorRegistry."""

    def test_register_and_get(self):
        """Can register and retrieve connectors."""
        # Dummy connectors already registered in dummy.py
        cls = ConnectorRegistry.get("dummy")
        assert cls is DummyConnector

    def test_get_case_insensitive(self):
        """get() is case-insensitive."""
        assert ConnectorRegistry.get("DUMMY") is DummyConnector
        assert ConnectorRegistry.get("Dummy") is DummyConnector

    def test_get_unknown(self):
        """get() returns None for unknown connectors."""
        assert ConnectorRegistry.get("nonexistent") is None

    def test_list_connectors(self):
        """list_connectors() returns all registered names."""
        names = ConnectorRegistry.list_connectors()
        assert "dummy" in names
        assert "null" in names
        assert "failing" in names

    def test_is_registered(self):
        """is_registered() checks registration status."""
        assert ConnectorRegistry.is_registered("dummy") is True
        assert ConnectorRegistry.is_registered("nonexistent") is False

    def test_unregister(self):
        """unregister() removes a connector."""
        # Register a test connector
        ConnectorRegistry.register("test_temp", DummyConnector)
        assert ConnectorRegistry.is_registered("test_temp") is True

        # Unregister it
        ConnectorRegistry.unregister("test_temp")
        assert ConnectorRegistry.is_registered("test_temp") is False


# =============================================================================
# BaseConnector Tests
# =============================================================================


class TestBaseConnector:
    """Tests for BaseConnector."""

    def test_has_capability(self):
        """has_capability() checks capability existence."""
        connector = DummyConnector()
        assert connector.has_capability(ConnectorCapability.READ_ACCOUNTS) is True
        assert connector.has_capability(ConnectorCapability.WEBHOOKS) is False

    def test_default_auth(self):
        """Connector defaults to NoAuth."""
        connector = DummyConnector()
        assert isinstance(connector.auth, NoAuth)

    def test_default_policy(self):
        """Connector defaults to DEFAULT_POLICY."""
        connector = DummyConnector()
        assert connector.policy.connect_timeout == DEFAULT_POLICY.connect_timeout

    def test_custom_auth_and_policy(self):
        """Connector accepts custom auth and policy."""
        auth = ApiKeyAuth(api_key="test")
        policy = CONSERVATIVE_POLICY

        connector = DummyConnector(auth=auth, policy=policy)
        assert connector.auth is auth
        assert connector.policy is policy

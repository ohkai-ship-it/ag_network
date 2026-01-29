"""Dummy/null connectors for testing (M6.1).

These connectors implement the Connector protocol without making
any real network calls. Used for:
- Unity tests
- Integration tests
- Development without external dependencies

DummyConnector can be configured to return specific responses
or raise specific errors for testing different scenarios.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .base import (
    AuthStrategy,
    BaseConnector,
    ConnectorCapability,
    ConnectorError,
    ConnectorRegistry,
    RequestPolicy,
)


@dataclass
class DummyResponse:
    """Canned response for DummyConnector."""

    data: Any = None
    error: Optional[ConnectorError] = None
    delay_seconds: float = 0.0


class DummyConnector(BaseConnector):
    """Dummy connector for testing.

    Returns canned responses without making real network calls.
    Can be configured to:
    - Return specific data for different operations
    - Raise specific errors
    - Track method calls for assertions
    """

    _name = "dummy"
    _capabilities = {
        ConnectorCapability.READ_ACCOUNTS,
        ConnectorCapability.READ_CONTACTS,
        ConnectorCapability.READ_ACTIVITIES,
        ConnectorCapability.WRITE_ACCOUNTS,
        ConnectorCapability.WRITE_CONTACTS,
        ConnectorCapability.WRITE_ACTIVITIES,
    }

    def __init__(
        self,
        auth: Optional[AuthStrategy] = None,
        policy: Optional[RequestPolicy] = None,
        healthy: bool = True,
    ):
        """Initialize dummy connector.

        Args:
            auth: Authentication strategy (ignored, but stored)
            policy: Request policy (ignored, but stored)
            healthy: Whether health_check() returns True
        """
        super().__init__(auth, policy)
        self._healthy = healthy
        self._responses: Dict[str, DummyResponse] = {}
        self._call_log: List[Dict[str, Any]] = []

    def health_check(self) -> bool:
        """Return configured health status."""
        self._log_call("health_check", {})
        return self._healthy

    def set_healthy(self, healthy: bool) -> None:
        """Set health status for health_check()."""
        self._healthy = healthy

    def set_response(self, operation: str, response: DummyResponse) -> None:
        """Set canned response for an operation.

        Args:
            operation: Operation name (e.g., "get_account", "list_contacts")
            response: DummyResponse to return/raise
        """
        self._responses[operation] = response

    def clear_responses(self) -> None:
        """Clear all canned responses."""
        self._responses.clear()

    def _log_call(self, operation: str, args: Dict[str, Any]) -> None:
        """Log a method call for later assertions."""
        self._call_log.append({
            "operation": operation,
            "args": args,
        })

    def get_call_log(self) -> List[Dict[str, Any]]:
        """Get log of all method calls."""
        return self._call_log.copy()

    def clear_call_log(self) -> None:
        """Clear the call log."""
        self._call_log.clear()

    def was_called(self, operation: str) -> bool:
        """Check if an operation was called."""
        return any(call["operation"] == operation for call in self._call_log)

    def call_count(self, operation: str) -> int:
        """Count how many times an operation was called."""
        return sum(1 for call in self._call_log if call["operation"] == operation)

    def _get_response(self, operation: str) -> Any:
        """Get response for operation, raising error if configured."""
        import time

        response = self._responses.get(operation)
        if response is None:
            return None

        if response.delay_seconds > 0:
            time.sleep(response.delay_seconds)

        if response.error is not None:
            raise response.error

        return response.data

    # Placeholder CRM-like operations for testing
    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get account by ID (dummy implementation)."""
        self._log_call("get_account", {"account_id": account_id})
        return self._get_response("get_account")

    def list_accounts(self, **filters) -> List[Dict[str, Any]]:
        """List accounts (dummy implementation)."""
        self._log_call("list_accounts", {"filters": filters})
        result = self._get_response("list_accounts")
        return result if result is not None else []

    def create_account(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create account (dummy implementation)."""
        self._log_call("create_account", {"data": data})
        result = self._get_response("create_account")
        return result if result is not None else {"id": "dummy-id", **data}

    def get_contact(self, contact_id: str) -> Optional[Dict[str, Any]]:
        """Get contact by ID (dummy implementation)."""
        self._log_call("get_contact", {"contact_id": contact_id})
        return self._get_response("get_contact")

    def list_contacts(self, **filters) -> List[Dict[str, Any]]:
        """List contacts (dummy implementation)."""
        self._log_call("list_contacts", {"filters": filters})
        result = self._get_response("list_contacts")
        return result if result is not None else []

    def create_contact(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create contact (dummy implementation)."""
        self._log_call("create_contact", {"data": data})
        result = self._get_response("create_contact")
        return result if result is not None else {"id": "dummy-id", **data}


class NullConnector(BaseConnector):
    """Null connector that does nothing.

    Returns empty responses, never raises errors.
    Used when you need a connector but don't care about results.
    """

    _name = "null"
    _capabilities = set()  # No capabilities

    def __init__(
        self,
        auth: Optional[AuthStrategy] = None,
        policy: Optional[RequestPolicy] = None,
    ):
        """Initialize null connector."""
        super().__init__(auth, policy)

    def health_check(self) -> bool:
        """Always healthy."""
        return True

    def get_account(self, account_id: str) -> None:
        """Return None."""
        return None

    def list_accounts(self, **filters) -> List[Dict[str, Any]]:
        """Return empty list."""
        return []

    def create_account(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Return empty dict."""
        return {}

    def get_contact(self, contact_id: str) -> None:
        """Return None."""
        return None

    def list_contacts(self, **filters) -> List[Dict[str, Any]]:
        """Return empty list."""
        return []

    def create_contact(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Return empty dict."""
        return {}


class FailingConnector(BaseConnector):
    """Connector that always fails.

    Raises specified error on every operation.
    Useful for testing error handling paths.
    """

    _name = "failing"
    _capabilities = {
        ConnectorCapability.READ_ACCOUNTS,
        ConnectorCapability.READ_CONTACTS,
    }

    def __init__(
        self,
        auth: Optional[AuthStrategy] = None,
        policy: Optional[RequestPolicy] = None,
        error: Optional[ConnectorError] = None,
    ):
        """Initialize failing connector.

        Args:
            auth: Authentication strategy
            policy: Request policy
            error: Error to raise on every operation
        """
        super().__init__(auth, policy)
        self._error = error or ConnectorError("Simulated failure", connector_name="failing")

    def health_check(self) -> bool:
        """Always unhealthy."""
        return False

    def _fail(self) -> None:
        """Raise the configured error."""
        raise self._error

    def get_account(self, account_id: str) -> Dict[str, Any]:
        """Always fails."""
        self._fail()

    def list_accounts(self, **filters) -> List[Dict[str, Any]]:
        """Always fails."""
        self._fail()

    def create_account(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Always fails."""
        self._fail()


# Register dummy connectors
ConnectorRegistry.register("dummy", DummyConnector)
ConnectorRegistry.register("null", NullConnector)
ConnectorRegistry.register("failing", FailingConnector)

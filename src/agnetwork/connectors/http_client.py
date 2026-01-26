"""HTTP client wrapper with retry/rate-limit support (M6.1).

Wraps httpx with RequestPolicy enforcement:
- Configurable timeouts
- Automatic retries with exponential backoff
- Rate limiting (prepared, not enforced in M6.1)
- Error mapping to ConnectorError hierarchy

This is a thin wrapper - actual HTTP calls use httpx.
Tests can mock httpx or use the DummyConnector.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, TypeVar

from .base import (
    AuthenticationError,
    AuthStrategy,
    ConnectionError,
    ConnectorError,
    RateLimitError,
    RequestPolicy,
    ResourceNotFoundError,
    ServiceUnavailableError,
    TimeoutError,
    ValidationError,
)

# Optional httpx import - not required for tests
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    httpx = None  # type: ignore
    HTTPX_AVAILABLE = False


T = TypeVar("T")


@dataclass
class HTTPResponse:
    """Simplified HTTP response wrapper.

    Used to provide consistent interface regardless of underlying HTTP library.
    """

    status_code: int
    headers: Dict[str, str]
    body: bytes
    json_data: Optional[Any] = None
    elapsed_seconds: float = 0.0

    @property
    def ok(self) -> bool:
        """Check if status code indicates success (2xx)."""
        return 200 <= self.status_code < 300

    def json(self) -> Any:
        """Get JSON data (parsed body)."""
        if self.json_data is not None:
            return self.json_data
        import json as json_module
        self.json_data = json_module.loads(self.body)
        return self.json_data


class HTTPClient:
    """HTTP client with retry and rate-limit support.

    Wraps httpx with RequestPolicy enforcement.
    """

    def __init__(
        self,
        auth: Optional[AuthStrategy] = None,
        policy: Optional[RequestPolicy] = None,
        base_url: str = "",
    ):
        """Initialize HTTP client.

        Args:
            auth: Authentication strategy for requests
            policy: Request policy (timeouts, retries)
            base_url: Base URL for all requests
        """
        if not HTTPX_AVAILABLE:
            raise ImportError(
                "httpx is required for HTTP operations. "
                "Install with: pip install httpx"
            )

        self.auth = auth
        self.policy = policy or RequestPolicy()
        self.base_url = base_url.rstrip("/")

        # Track rate limiting (simple in-memory, per-instance)
        self._last_request_time: float = 0.0
        self._request_count: int = 0

    def _build_headers(self, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Build request headers including auth and defaults."""
        headers = {"User-Agent": self.policy.user_agent}
        headers.update(self.policy.default_headers)

        if self.auth:
            headers.update(self.auth.get_headers())

        if extra_headers:
            headers.update(extra_headers)

        return headers

    def _get_url(self, path: str) -> str:
        """Build full URL from path."""
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def _should_retry(self, status_code: int, attempt: int) -> bool:
        """Check if request should be retried."""
        if attempt >= self.policy.max_retries:
            return False
        return status_code in self.policy.retry_on_status

    def _get_retry_delay(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """Calculate retry delay with exponential backoff."""
        if retry_after is not None:
            return retry_after
        return self.policy.retry_delay * (self.policy.retry_backoff ** attempt)

    def _map_error(
        self,
        status_code: int,
        body: bytes,
        headers: Dict[str, str],
        connector_name: str = "http_client",
    ) -> ConnectorError:
        """Map HTTP status code to appropriate ConnectorError."""
        body_str = body.decode("utf-8", errors="replace")

        if status_code == 401:
            return AuthenticationError(
                f"Authentication failed: {body_str}",
                connector_name=connector_name,
            )
        elif status_code == 403:
            return AuthenticationError(
                f"Permission denied: {body_str}",
                connector_name=connector_name,
            )
        elif status_code == 404:
            return ResourceNotFoundError(
                f"Resource not found: {body_str}",
                connector_name=connector_name,
            )
        elif status_code == 409:
            from .base import ConflictError
            return ConflictError(
                f"Resource conflict: {body_str}",
                connector_name=connector_name,
            )
        elif status_code == 422:
            return ValidationError(
                f"Validation failed: {body_str}",
                connector_name=connector_name,
            )
        elif status_code == 429:
            retry_after = headers.get("Retry-After")
            retry_seconds = float(retry_after) if retry_after else None
            return RateLimitError(
                f"Rate limit exceeded: {body_str}",
                connector_name=connector_name,
                retry_after=retry_seconds,
            )
        elif status_code >= 500:
            return ServiceUnavailableError(
                f"Service error ({status_code}): {body_str}",
                connector_name=connector_name,
            )
        else:
            return ConnectorError(
                f"HTTP error {status_code}: {body_str}",
                connector_name=connector_name,
            )

    def _enforce_rate_limit(self) -> None:
        """Enforce rate limiting if configured.

        Simple token bucket algorithm (in-memory, per-instance).
        """
        if self.policy.requests_per_second is None:
            return

        now = time.monotonic()
        min_interval = 1.0 / self.policy.requests_per_second

        time_since_last = now - self._last_request_time
        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            time.sleep(sleep_time)

        self._last_request_time = time.monotonic()

    def _sleep_and_retry(self, attempt: int, retry_after: Optional[float] = None) -> bool:
        """Sleep before retry if attempts remain. Returns True if should retry."""
        if attempt < self.policy.max_retries:
            delay = self._get_retry_delay(attempt, retry_after)
            time.sleep(delay)
            return True
        return False

    def _execute_request(
        self,
        method: str,
        url: str,
        request_headers: Dict[str, str],
        timeout: "httpx.Timeout",
        json: Optional[Any],
        data: Optional[Dict[str, Any]],
        params: Optional[Dict[str, Any]],
    ) -> HTTPResponse:
        """Execute a single HTTP request."""
        start_time = time.monotonic()
        with httpx.Client(timeout=timeout) as client:
            response = client.request(
                method=method,
                url=url,
                json=json,
                data=data,
                params=params,
                headers=request_headers,
            )
        elapsed = time.monotonic() - start_time
        return HTTPResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.content,
            elapsed_seconds=elapsed,
        )

    def request(  # noqa: C901
        self,
        method: str,
        path: str,
        *,
        json: Optional[Any] = None,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        raise_for_status: bool = True,
    ) -> HTTPResponse:
        """Make HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: URL path (relative to base_url)
            json: JSON body to send
            data: Form data to send
            params: Query parameters
            headers: Additional headers
            raise_for_status: Raise exception on non-2xx status

        Returns:
            HTTPResponse with status, headers, and body

        Raises:
            ConnectorError: On HTTP errors (if raise_for_status=True)
            TimeoutError: On request timeout
            ConnectionError: On connection failure
        """
        url = self._get_url(path)
        request_headers = self._build_headers(headers)
        timeout = httpx.Timeout(
            connect=self.policy.connect_timeout,
            read=self.policy.read_timeout,
            write=self.policy.read_timeout,
            pool=self.policy.total_timeout,
        )

        last_error: Optional[Exception] = None

        for attempt in range(self.policy.max_retries + 1):
            self._enforce_rate_limit()

            try:
                result = self._execute_request(
                    method, url, request_headers, timeout, json, data, params
                )

                # Check if we should retry on this status
                if not result.ok and self._should_retry(result.status_code, attempt):
                    self._sleep_and_retry(attempt)
                    continue

                # Raise error if requested and response not OK
                if raise_for_status and not result.ok:
                    raise self._map_error(result.status_code, result.body, result.headers)

                return result

            except httpx.TimeoutException:
                last_error = TimeoutError(
                    f"Request timed out after {self.policy.read_timeout}s",
                    timeout_seconds=self.policy.read_timeout,
                )
                if self._sleep_and_retry(attempt):
                    continue

            except httpx.ConnectError as e:
                last_error = ConnectionError(f"Failed to connect to {url}: {e}")
                if self._sleep_and_retry(attempt):
                    continue

            except httpx.HTTPError as e:
                last_error = ConnectorError(f"HTTP error: {e}")
                if self._sleep_and_retry(attempt):
                    continue

        # All retries exhausted
        if last_error:
            raise last_error
        raise ConnectorError("Request failed after all retries")

    def get(self, path: str, **kwargs) -> HTTPResponse:
        """HTTP GET request."""
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> HTTPResponse:
        """HTTP POST request."""
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> HTTPResponse:
        """HTTP PUT request."""
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs) -> HTTPResponse:
        """HTTP PATCH request."""
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs) -> HTTPResponse:
        """HTTP DELETE request."""
        return self.request("DELETE", path, **kwargs)


class AsyncHTTPClient:
    """Async HTTP client with retry and rate-limit support.

    Same as HTTPClient but for async operations.
    M6.1: Basic implementation, mirrors sync version.
    """

    def __init__(
        self,
        auth: Optional[AuthStrategy] = None,
        policy: Optional[RequestPolicy] = None,
        base_url: str = "",
    ):
        """Initialize async HTTP client."""
        if not HTTPX_AVAILABLE:
            raise ImportError(
                "httpx is required for HTTP operations. "
                "Install with: pip install httpx"
            )

        self.auth = auth
        self.policy = policy or RequestPolicy()
        self.base_url = base_url.rstrip("/")
        self._last_request_time: float = 0.0

    def _build_headers(self, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Build request headers including auth and defaults."""
        headers = {"User-Agent": self.policy.user_agent}
        headers.update(self.policy.default_headers)

        if self.auth:
            headers.update(self.auth.get_headers())

        if extra_headers:
            headers.update(extra_headers)

        return headers

    def _get_url(self, path: str) -> str:
        """Build full URL from path."""
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    async def _async_sleep_and_retry(self, attempt: int) -> bool:
        """Async sleep before retry if attempts remain."""
        if attempt < self.policy.max_retries:
            delay = self.policy.retry_delay * (self.policy.retry_backoff ** attempt)
            await asyncio.sleep(delay)
            return True
        return False

    async def request(  # noqa: C901
        self,
        method: str,
        path: str,
        *,
        json: Optional[Any] = None,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        raise_for_status: bool = True,
    ) -> HTTPResponse:
        """Make async HTTP request with retry logic."""
        url = self._get_url(path)
        request_headers = self._build_headers(headers)
        timeout = httpx.Timeout(
            connect=self.policy.connect_timeout,
            read=self.policy.read_timeout,
            write=self.policy.read_timeout,
            pool=self.policy.total_timeout,
        )

        last_error: Optional[Exception] = None

        for attempt in range(self.policy.max_retries + 1):
            try:
                start_time = time.monotonic()

                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        json=json,
                        data=data,
                        params=params,
                        headers=request_headers,
                    )

                elapsed = time.monotonic() - start_time

                result = HTTPResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=response.content,
                    elapsed_seconds=elapsed,
                )

                if not result.ok and response.status_code in self.policy.retry_on_status:
                    if await self._async_sleep_and_retry(attempt):
                        continue

                if raise_for_status and not result.ok:
                    # Reuse sync client's error mapping logic
                    sync_client = HTTPClient.__new__(HTTPClient)
                    sync_client.policy = self.policy
                    raise sync_client._map_error(
                        result.status_code,
                        result.body,
                        result.headers,
                    )

                return result

            except httpx.TimeoutException:
                last_error = TimeoutError(
                    f"Request timed out after {self.policy.read_timeout}s",
                    timeout_seconds=self.policy.read_timeout,
                )
                if await self._async_sleep_and_retry(attempt):
                    continue

            except httpx.ConnectError as e:
                last_error = ConnectionError(f"Failed to connect to {url}: {e}")
                if attempt < self.policy.max_retries:
                    delay = self.policy.retry_delay * (self.policy.retry_backoff ** attempt)
                    await asyncio.sleep(delay)
                    continue

        if last_error:
            raise last_error
        raise ConnectorError("Request failed after all retries")

    async def get(self, path: str, **kwargs) -> HTTPResponse:
        """Async HTTP GET request."""
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs) -> HTTPResponse:
        """Async HTTP POST request."""
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs) -> HTTPResponse:
        """Async HTTP PUT request."""
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str, **kwargs) -> HTTPResponse:
        """Async HTTP PATCH request."""
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs) -> HTTPResponse:
        """Async HTTP DELETE request."""
        return await self.request("DELETE", path, **kwargs)

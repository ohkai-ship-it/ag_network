"""Web fetch tool for retrieving URL content.

Provides safe, rate-limited URL fetching with retry support.
"""

import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional
from urllib.parse import urlparse

import httpx

# Per-host rate limiting state
_host_last_request: Dict[str, float] = {}
_MIN_HOST_INTERVAL_S = 1.0  # Minimum seconds between requests to same host


@dataclass
class FetchResult:
    """Result of a URL fetch operation."""

    url: str
    final_url: str
    status_code: int
    headers: Dict[str, str]
    content_bytes: bytes
    fetched_at: datetime
    content_hash: str
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """Check if fetch was successful (2xx status)."""
        return 200 <= self.status_code < 300 and self.error is None

    @property
    def is_html(self) -> bool:
        """Check if content appears to be HTML."""
        content_type = self.headers.get("content-type", "").lower()
        return "text/html" in content_type or "application/xhtml" in content_type

    @property
    def content_type(self) -> str:
        """Get the content type from headers."""
        return self.headers.get("content-type", "application/octet-stream")


def _rate_limit_host(host: str) -> None:
    """Apply per-host rate limiting."""
    global _host_last_request

    now = time.monotonic()
    last = _host_last_request.get(host, 0)
    elapsed = now - last

    if elapsed < _MIN_HOST_INTERVAL_S:
        sleep_time = _MIN_HOST_INTERVAL_S - elapsed
        time.sleep(sleep_time)

    _host_last_request[host] = time.monotonic()


def _compute_hash(content: bytes) -> str:
    """Compute SHA256 hash of content."""
    return hashlib.sha256(content).hexdigest()


def fetch_url(
    url: str,
    *,
    timeout_s: float = 30.0,
    user_agent: str = "AGNetwork/1.0 (Research Bot)",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB default
    allow_redirects: bool = True,
    max_retries: int = 2,
) -> FetchResult:
    """Fetch content from a URL.

    Args:
        url: URL to fetch
        timeout_s: Request timeout in seconds
        user_agent: User-Agent header value
        max_bytes: Maximum bytes to download (prevents huge files)
        allow_redirects: Whether to follow redirects
        max_retries: Maximum retry attempts (total attempts = max_retries)

    Returns:
        FetchResult with content and metadata
    """
    parsed = urlparse(url)
    host = parsed.netloc

    # Apply rate limiting
    _rate_limit_host(host)

    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    last_error: Optional[str] = None
    fetched_at = datetime.now(timezone.utc)

    for attempt in range(max_retries):
        try:
            with httpx.Client(
                timeout=timeout_s,
                follow_redirects=allow_redirects,
                headers=headers,
            ) as client:
                response = client.get(url)

                # Read content with size limit
                content = response.content[:max_bytes]

                # Extract headers as dict
                response_headers = {k.lower(): v for k, v in response.headers.items()}

                return FetchResult(
                    url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    headers=response_headers,
                    content_bytes=content,
                    fetched_at=fetched_at,
                    content_hash=_compute_hash(content),
                    error=None if response.is_success else f"HTTP {response.status_code}",
                )

        except httpx.TimeoutException as e:
            last_error = f"Timeout: {e}"
        except httpx.ConnectError as e:
            last_error = f"Connection error: {e}"
        except httpx.HTTPStatusError as e:
            last_error = f"HTTP error: {e}"
        except Exception as e:
            last_error = f"Unexpected error: {type(e).__name__}: {e}"

        # Wait before retry (exponential backoff)
        if attempt < max_retries - 1:
            time.sleep(2**attempt)

    # All retries exhausted
    return FetchResult(
        url=url,
        final_url=url,
        status_code=0,
        headers={},
        content_bytes=b"",
        fetched_at=fetched_at,
        content_hash=_compute_hash(b""),
        error=last_error or "Unknown error",
    )


def fetch_urls(
    urls: list[str],
    *,
    timeout_s: float = 30.0,
    user_agent: str = "AGNetwork/1.0 (Research Bot)",
    max_bytes: int = 10 * 1024 * 1024,
    allow_redirects: bool = True,
) -> list[FetchResult]:
    """Fetch multiple URLs sequentially with rate limiting.

    Args:
        urls: List of URLs to fetch
        timeout_s: Request timeout in seconds
        user_agent: User-Agent header value
        max_bytes: Maximum bytes per download
        allow_redirects: Whether to follow redirects

    Returns:
        List of FetchResult objects
    """
    results = []
    for url in urls:
        result = fetch_url(
            url,
            timeout_s=timeout_s,
            user_agent=user_agent,
            max_bytes=max_bytes,
            allow_redirects=allow_redirects,
        )
        results.append(result)
    return results

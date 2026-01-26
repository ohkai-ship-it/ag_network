"""Web tools for URL fetching and content extraction."""

from agnetwork.tools.web.capture import (
    CapturedSource,
    SourceCapture,
    capture_sources_for_run,
)
from agnetwork.tools.web.clean import CleanResult, extract_text, extract_text_simple
from agnetwork.tools.web.fetch import FetchResult, fetch_url, fetch_urls

__all__ = [
    "FetchResult",
    "fetch_url",
    "fetch_urls",
    "CleanResult",
    "extract_text",
    "extract_text_simple",
    "CapturedSource",
    "SourceCapture",
    "capture_sources_for_run",
]

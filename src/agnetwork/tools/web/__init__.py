"""Web tools for URL fetching and content extraction."""

from agnetwork.tools.web.capture import (
    CapturedSource,
    SourceCapture,
    capture_sources_for_run,
)
from agnetwork.tools.web.clean import CleanResult, extract_text, extract_text_simple
from agnetwork.tools.web.deeplinks import (
    DeepLinksAudit,
    DeepLinksConfig,
    DeepLinkSelection,
    LinkCandidate,
    ScoredCandidate,
    discover_deep_links,
    extract_link_candidates,
    is_homepage_url,
    score_and_rank,
    select_deterministic,
    select_with_agent,
)
from agnetwork.tools.web.fetch import FetchResult, fetch_url, fetch_urls

__all__ = [
    # Fetch
    "FetchResult",
    "fetch_url",
    "fetch_urls",
    # Clean
    "CleanResult",
    "extract_text",
    "extract_text_simple",
    # Capture
    "CapturedSource",
    "SourceCapture",
    "capture_sources_for_run",
    # Deep links (M8)
    "DeepLinksAudit",
    "DeepLinksConfig",
    "DeepLinkSelection",
    "LinkCandidate",
    "ScoredCandidate",
    "discover_deep_links",
    "extract_link_candidates",
    "is_homepage_url",
    "score_and_rank",
    "select_deterministic",
    "select_with_agent",
]

"""Source capture and caching for web content.

Handles fetching, cleaning, and storing URL content in run folders.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from agnetwork.tools.web.clean import extract_text
from agnetwork.tools.web.fetch import fetch_url


def _slugify(url: str) -> str:
    """Create a filesystem-safe slug from a URL."""
    # Remove protocol
    slug = re.sub(r"^https?://", "", url)
    # Replace non-alphanumeric with underscore
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", slug)
    # Trim underscores and limit length
    slug = slug.strip("_")[:80]
    # Add hash suffix for uniqueness
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:8]
    return f"{slug}_{url_hash}"


@dataclass
class CapturedSource:
    """A captured and processed URL source."""

    source_id: str
    url: str
    final_url: str
    title: Optional[str]
    clean_text: str
    content_hash: str
    status_code: int
    fetched_at: datetime
    is_cached: bool
    error: Optional[str]

    # File paths (relative to run dir)
    raw_path: Optional[str]
    clean_path: Optional[str]
    meta_path: Optional[str]

    @property
    def is_success(self) -> bool:
        """Check if capture was successful."""
        return self.error is None and self.status_code == 200


class SourceCapture:
    """Handles source capture and caching for a run."""

    def __init__(self, sources_dir: Path):
        """Initialize source capture.

        Args:
            sources_dir: Path to the sources/ directory within a run folder
        """
        self.sources_dir = sources_dir
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, CapturedSource] = {}
        self._load_existing_cache()

    def _load_existing_cache(self) -> None:
        """Load cached sources from existing meta files."""
        for meta_file in self.sources_dir.glob("*__meta.json"):
            try:
                with open(meta_file) as f:
                    meta = json.load(f)

                source_id = meta.get("source_id", meta_file.stem.replace("__meta", ""))
                url = meta.get("url", "")

                if url:
                    self._cache[url] = CapturedSource(
                        source_id=source_id,
                        url=url,
                        final_url=meta.get("final_url", url),
                        title=meta.get("title"),
                        clean_text="",  # Loaded on demand
                        content_hash=meta.get("content_hash", ""),
                        status_code=meta.get("status_code", 200),
                        fetched_at=datetime.fromisoformat(meta.get("fetched_at", "")),
                        is_cached=True,
                        error=meta.get("error"),
                        raw_path=meta.get("raw_path"),
                        clean_path=meta.get("clean_path"),
                        meta_path=str(meta_file.relative_to(self.sources_dir.parent)),
                    )
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

    def capture_url(
        self,
        url: str,
        *,
        force_refresh: bool = False,
        timeout_s: float = 30.0,
    ) -> CapturedSource:
        """Capture content from a URL.

        Args:
            url: URL to capture
            force_refresh: If True, refetch even if cached
            timeout_s: Fetch timeout in seconds

        Returns:
            CapturedSource with content and metadata
        """
        # Check cache first
        if not force_refresh and url in self._cache:
            cached = self._cache[url]
            # Load clean text if needed
            if not cached.clean_text and cached.clean_path:
                clean_file = self.sources_dir.parent / cached.clean_path
                if clean_file.exists():
                    cached.clean_text = clean_file.read_text(encoding="utf-8")
            return cached

        # Generate source ID and file paths
        slug = _slugify(url)
        source_id = f"src_{slug}"

        # Fetch URL
        fetch_result = fetch_url(url, timeout_s=timeout_s)

        if not fetch_result.is_success:
            # Return error result
            return CapturedSource(
                source_id=source_id,
                url=url,
                final_url=fetch_result.final_url,
                title=None,
                clean_text="",
                content_hash=fetch_result.content_hash,
                status_code=fetch_result.status_code,
                fetched_at=fetch_result.fetched_at,
                is_cached=False,
                error=fetch_result.error,
                raw_path=None,
                clean_path=None,
                meta_path=None,
            )

        # Determine file extension
        if fetch_result.is_html:
            raw_ext = "html"
        else:
            raw_ext = "bin"

        raw_path = f"sources/{slug}__raw.{raw_ext}"
        clean_path = f"sources/{slug}__clean.txt"
        meta_path = f"sources/{slug}__meta.json"

        # Save raw content
        raw_file = self.sources_dir / f"{slug}__raw.{raw_ext}"
        raw_file.write_bytes(fetch_result.content_bytes)

        # Extract and save clean text
        if fetch_result.is_html:
            clean_result = extract_text(fetch_result.content_bytes, url=url)
            clean_text = clean_result.text
            title = clean_result.title
        else:
            # Non-HTML: try to decode as text
            try:
                clean_text = fetch_result.content_bytes.decode("utf-8")
                title = None
            except UnicodeDecodeError:
                clean_text = f"[Binary content: {len(fetch_result.content_bytes)} bytes]"
                title = None

        clean_file = self.sources_dir / f"{slug}__clean.txt"
        clean_file.write_text(clean_text, encoding="utf-8")

        # Save metadata
        meta = {
            "source_id": source_id,
            "url": url,
            "final_url": fetch_result.final_url,
            "title": title,
            "status_code": fetch_result.status_code,
            "content_type": fetch_result.content_type,
            "content_hash": fetch_result.content_hash,
            "content_length": len(fetch_result.content_bytes),
            "clean_text_length": len(clean_text),
            "fetched_at": fetch_result.fetched_at.isoformat(),
            "headers_subset": {
                k: v
                for k, v in fetch_result.headers.items()
                if k in ("content-type", "content-length", "last-modified", "etag")
            },
            "raw_path": raw_path,
            "clean_path": clean_path,
        }

        meta_file = self.sources_dir / f"{slug}__meta.json"
        with open(meta_file, "w") as f:
            json.dump(meta, f, indent=2)

        # Create result
        result = CapturedSource(
            source_id=source_id,
            url=url,
            final_url=fetch_result.final_url,
            title=title,
            clean_text=clean_text,
            content_hash=fetch_result.content_hash,
            status_code=fetch_result.status_code,
            fetched_at=fetch_result.fetched_at,
            is_cached=False,
            error=None,
            raw_path=raw_path,
            clean_path=clean_path,
            meta_path=meta_path,
        )

        # Update cache
        self._cache[url] = result

        return result

    def capture_urls(
        self,
        urls: List[str],
        *,
        force_refresh: bool = False,
        timeout_s: float = 30.0,
    ) -> List[CapturedSource]:
        """Capture content from multiple URLs.

        Args:
            urls: URLs to capture
            force_refresh: If True, refetch even if cached
            timeout_s: Fetch timeout per URL

        Returns:
            List of CapturedSource results
        """
        results = []
        for url in urls:
            result = self.capture_url(url, force_refresh=force_refresh, timeout_s=timeout_s)
            results.append(result)
        return results

    def get_all_sources(self) -> List[CapturedSource]:
        """Get all captured sources."""
        return list(self._cache.values())

    def get_source_by_id(self, source_id: str) -> Optional[CapturedSource]:
        """Get a source by its ID."""
        for source in self._cache.values():
            if source.source_id == source_id:
                return source
        return None


def capture_sources_for_run(
    sources_dir: Path,
    urls: List[str],
) -> List[CapturedSource]:
    """Convenience function to capture URLs for a run.

    Args:
        sources_dir: Path to run's sources/ directory
        urls: URLs to capture

    Returns:
        List of captured sources
    """
    capture = SourceCapture(sources_dir)
    return capture.capture_urls(urls)

"""Tests for M5 web tools: fetch, clean, capture, and SQLite integration."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from agnetwork.tools.web.capture import CapturedSource, SourceCapture, capture_sources_for_run
from agnetwork.tools.web.clean import CleanResult, extract_text, extract_text_simple
from agnetwork.tools.web.fetch import FetchResult, _compute_hash, fetch_url, fetch_urls

# =============================================================================
# HTML Test Fixtures (as bytes, since that's what extract_text expects)
# =============================================================================

SIMPLE_HTML = b"""
<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
    <style>body { color: black; }</style>
    <script>console.log('test');</script>
</head>
<body>
    <header>Navigation Menu</header>
    <main>
        <h1>Main Title</h1>
        <p>This is the main content paragraph.</p>
        <p>Second paragraph with <strong>bold</strong> text.</p>
    </main>
    <footer>Copyright 2025</footer>
</body>
</html>
"""

ARTICLE_HTML = b"""
<!DOCTYPE html>
<html>
<head><title>News Article</title></head>
<body>
    <nav>Home | News | Contact</nav>
    <article>
        <h1>Breaking News Headline</h1>
        <p class="byline">By Author Name</p>
        <p>First paragraph of the article content.</p>
        <p>Second paragraph continues the story.</p>
    </article>
    <aside>Related Links</aside>
</body>
</html>
"""

COMPLEX_HTML = b"""
<!DOCTYPE html>
<html>
<head>
    <title>Complex Page</title>
    <style>
        .hidden { display: none; }
    </style>
    <script type="text/javascript">
        function doSomething() { alert('test'); }
    </script>
</head>
<body>
    <div id="header">
        <nav>Menu Item 1 | Menu Item 2</nav>
    </div>
    <div id="content">
        <section>
            <h2>Section One</h2>
            <p>Content in section one with
               multiple lines and   extra   whitespace.</p>
        </section>
        <section>
            <h2>Section Two</h2>
            <ul>
                <li>List item one</li>
                <li>List item two</li>
            </ul>
        </section>
    </div>
    <div id="sidebar">
        <h3>Advertisements</h3>
        <p>Buy our stuff!</p>
    </div>
    <footer>
        <p>&copy; 2025 Company Name</p>
    </footer>
</body>
</html>
"""


# =============================================================================
# Tests: HTML Extraction (clean.py)
# =============================================================================

class TestExtractText:
    """Tests for the extract_text() function."""

    def test_removes_script_tags(self):
        """Script content should be stripped."""
        result = extract_text(SIMPLE_HTML)
        assert "console.log" not in result.text

    def test_removes_style_tags(self):
        """Style content should be stripped."""
        result = extract_text(SIMPLE_HTML)
        assert "color: black" not in result.text

    def test_preserves_main_content(self):
        """Main content should be preserved."""
        result = extract_text(SIMPLE_HTML)
        assert "Main Title" in result.text
        assert "main content paragraph" in result.text
        assert "bold" in result.text

    def test_extracts_title(self):
        """Page title should be extracted."""
        result = extract_text(SIMPLE_HTML)
        assert result.title == "Test Page"

    def test_extracts_article_content(self):
        """Article tag content should be found."""
        result = extract_text(ARTICLE_HTML)
        assert "Breaking News Headline" in result.text
        assert "First paragraph" in result.text
        assert result.title == "News Article"

    def test_normalizes_whitespace(self):
        """Extra whitespace should be normalized."""
        result = extract_text(COMPLEX_HTML)
        # Should not have multiple consecutive spaces (3+)
        assert "   " not in result.text

    def test_returns_char_count(self):
        """Char count should be accurate."""
        result = extract_text(SIMPLE_HTML)
        assert result.char_count > 0
        assert isinstance(result.char_count, int)
        assert result.char_count == len(result.text)

    def test_handles_empty_html(self):
        """Empty HTML should return empty text."""
        result = extract_text(b"")
        assert result.text == ""

    def test_handles_invalid_html(self):
        """Invalid HTML should still be processed gracefully."""
        result = extract_text(b"<html><body><p>Unclosed paragraph")
        assert "Unclosed paragraph" in result.text

    def test_extract_text_simple(self):
        """Simple extraction should work without finding main content."""
        text = extract_text_simple(SIMPLE_HTML)
        assert "Main Title" in text
        assert "console.log" not in text


class TestCleanResult:
    """Tests for CleanResult dataclass."""

    def test_is_empty_property(self):
        """Should correctly check if text is empty."""
        empty = CleanResult(
            text="   ",
            title="Test",
            content_type="text/html",
            method="test",
            char_count=3
        )
        assert empty.is_empty is True

        non_empty = CleanResult(
            text="Content here",
            title="Test",
            content_type="text/html",
            method="test",
            char_count=12
        )
        assert non_empty.is_empty is False


# =============================================================================
# Tests: Fetch Tool (fetch.py)
# =============================================================================

class TestComputeHash:
    """Tests for the _compute_hash() function."""

    def test_sha256_format(self):
        """Hash should be SHA256 hex string."""
        h = _compute_hash(b"test content")
        assert len(h) == 64  # SHA256 = 64 hex chars
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_content_same_hash(self):
        """Same content should produce same hash."""
        h1 = _compute_hash(b"hello world")
        h2 = _compute_hash(b"hello world")
        assert h1 == h2

    def test_different_content_different_hash(self):
        """Different content should produce different hash."""
        h1 = _compute_hash(b"hello world")
        h2 = _compute_hash(b"goodbye world")
        assert h1 != h2


class TestFetchResult:
    """Tests for FetchResult dataclass."""

    def test_is_success_property(self):
        """Should correctly check success status."""
        success = FetchResult(
            url="https://example.com",
            final_url="https://example.com",
            status_code=200,
            headers={"content-type": "text/html"},
            content_bytes=b"test",
            fetched_at=datetime(2025, 1, 26, 12, 0, 0, tzinfo=timezone.utc),
            content_hash="abc123",
            error=None
        )
        assert success.is_success is True

        failure = FetchResult(
            url="https://example.com",
            final_url="https://example.com",
            status_code=404,
            headers={},
            content_bytes=b"",
            fetched_at=datetime.now(timezone.utc),
            content_hash="",
            error="HTTP 404"
        )
        assert failure.is_success is False

    def test_is_html_property(self):
        """Should correctly detect HTML content."""
        html = FetchResult(
            url="https://example.com",
            final_url="https://example.com",
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            content_bytes=b"<html>Test</html>",
            fetched_at=datetime.now(timezone.utc),
            content_hash="abc123",
            error=None
        )
        assert html.is_html is True

        non_html = FetchResult(
            url="https://example.com/data.json",
            final_url="https://example.com/data.json",
            status_code=200,
            headers={"content-type": "application/json"},
            content_bytes=b'{"key": "value"}',
            fetched_at=datetime.now(timezone.utc),
            content_hash="abc123",
            error=None
        )
        assert non_html.is_html is False


class TestFetchUrl:
    """Tests for fetch_url() function (mocked)."""

    def test_successful_fetch(self):
        """Successful fetch should return content and metadata."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<html>Test content</html>"
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.url = "https://example.com/test"
        mock_response.is_success = True

        with patch("agnetwork.tools.web.fetch.httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.__exit__.return_value = None
            mock_client.return_value = mock_instance

            result = fetch_url("https://example.com/test")

        assert result.is_success is True
        assert result.status_code == 200
        assert result.content_bytes == b"<html>Test content</html>"
        assert result.content_hash is not None

    def test_failed_fetch_returns_error(self):
        """Failed fetch should return error result."""
        with patch("agnetwork.tools.web.fetch.httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get.side_effect = Exception("Connection refused")
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.__exit__.return_value = None
            mock_client.return_value = mock_instance

            result = fetch_url("https://example.com/fail")

        assert result.is_success is False
        assert result.error is not None


class TestFetchUrls:
    """Tests for fetch_urls() function (mocked)."""

    def test_fetches_multiple_urls(self):
        """Should fetch multiple URLs."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<html>Test</html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.url = "https://example.com"
        mock_response.is_success = True

        with patch("agnetwork.tools.web.fetch.httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.__exit__.return_value = None
            mock_client.return_value = mock_instance

            results = fetch_urls(["https://a.com", "https://b.com"])

        assert len(results) == 2
        assert all(r.is_success for r in results)


# =============================================================================
# Tests: Source Capture (capture.py)
# =============================================================================

class TestCapturedSource:
    """Tests for CapturedSource dataclass."""

    def test_is_success_property(self):
        """Should correctly check if capture was successful."""
        success = CapturedSource(
            source_id="src_test",
            url="https://example.com",
            final_url="https://example.com",
            title="Test Page",
            clean_text="Content here",
            content_hash="abc123",
            status_code=200,
            fetched_at=datetime(2025, 1, 26, 12, 0, 0, tzinfo=timezone.utc),
            is_cached=False,
            error=None,
            raw_path="sources/test__raw.html",
            clean_path="sources/test__clean.txt",
            meta_path="sources/test__meta.json"
        )
        assert success.is_success is True

        failure = CapturedSource(
            source_id="src_fail",
            url="https://example.com/fail",
            final_url="https://example.com/fail",
            title=None,
            clean_text="",
            content_hash="",
            status_code=404,
            fetched_at=datetime.now(timezone.utc),
            is_cached=False,
            error="HTTP 404",
            raw_path=None,
            clean_path=None,
            meta_path=None
        )
        assert failure.is_success is False


class TestSourceCapture:
    """Tests for SourceCapture class."""

    def test_creates_sources_directory(self, tmp_path: Path):
        """Should create sources directory if it doesn't exist."""
        sources_dir = tmp_path / "run_123" / "sources"
        assert not sources_dir.exists()

        SourceCapture(sources_dir)  # Side effect: creates directory
        assert sources_dir.exists()

    def test_loads_existing_cache(self, tmp_path: Path):
        """Should load cached sources from existing meta files."""
        sources_dir = tmp_path / "sources"
        sources_dir.mkdir(parents=True)

        # Create a meta file
        meta = {
            "source_id": "src_test",
            "url": "https://example.com/cached",
            "final_url": "https://example.com/cached",
            "title": "Cached Page",
            "status_code": 200,
            "content_hash": "cached_hash_123",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "raw_path": "sources/test__raw.html",
            "clean_path": "sources/test__clean.txt",
        }
        meta_file = sources_dir / "test_abc123__meta.json"
        with open(meta_file, "w") as f:
            json.dump(meta, f)

        capture = SourceCapture(sources_dir)
        assert "https://example.com/cached" in capture._cache


class TestCaptureSourcesForRun:
    """Tests for capture_sources_for_run() function."""

    def test_captures_and_saves_sources(self, tmp_path: Path):
        """Should capture URLs and save to run folder."""
        sources_dir = tmp_path / "test_run" / "sources"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = SIMPLE_HTML
        mock_response.headers = {"content-type": "text/html"}
        mock_response.url = "https://example.com/page"
        mock_response.is_success = True

        with patch("agnetwork.tools.web.fetch.httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.__exit__.return_value = None
            mock_client.return_value = mock_instance

            sources = capture_sources_for_run(
                sources_dir=sources_dir,
                urls=["https://example.com/page"]
            )

        assert len(sources) == 1
        source = sources[0]
        assert source.is_success is True

        # Verify files exist
        assert sources_dir.exists()
        raw_files = list(sources_dir.glob("*__raw.html"))
        clean_files = list(sources_dir.glob("*__clean.txt"))
        meta_files = list(sources_dir.glob("*__meta.json"))

        assert len(raw_files) == 1
        assert len(clean_files) == 1
        assert len(meta_files) == 1

        # Verify content
        raw_content = raw_files[0].read_bytes()
        assert b"Main Title" in raw_content

        clean_content = clean_files[0].read_text(encoding="utf-8")
        assert "Main Title" in clean_content
        assert "console.log" not in clean_content


# =============================================================================
# Tests: SQLite Integration
# =============================================================================

class TestSQLiteSourceUpsert:
    """Tests for SQLite source storage with content_hash deduplication."""

    def test_upsert_source_from_capture(self, tmp_path: Path):
        """Should upsert source with content hash deduplication."""
        from agnetwork.storage.sqlite import SQLiteManager

        db_path = tmp_path / "test.db"
        db = SQLiteManager.unscoped(db_path)
        # _init_db is called automatically in __init__

        # Upsert a source
        success = db.upsert_source_from_capture(
            source_id="src_test_upsert",
            url="https://example.com/test",
            final_url="https://example.com/test",
            title="Test Page",
            clean_text="Test content for the page",
            content_hash="abc123def456",
            fetched_at=datetime.now(timezone.utc).isoformat(),
            run_id="test_run_001",
        )
        assert success is True

        # Verify it was stored using get_source_by_hash
        found = db.get_source_by_hash("abc123def456")
        assert found is not None
        assert found["uri"] == "https://example.com/test"
        assert found["content_hash"] == "abc123def456"
        assert found["run_id"] == "test_run_001"

    def test_upsert_deduplicates_by_hash(self, tmp_path: Path):
        """Same content hash should be detected as duplicate."""
        from agnetwork.storage.sqlite import SQLiteManager

        db_path = tmp_path / "test.db"
        db = SQLiteManager.unscoped(db_path)

        # Insert first source
        success1 = db.upsert_source_from_capture(
            source_id="src_page1",
            url="https://example.com/page1",
            final_url="https://example.com/page1",
            title="Page One",
            clean_text="Same content",
            content_hash="same_hash_123",
            fetched_at=datetime.now(timezone.utc).isoformat(),
            run_id="run_001",
        )
        assert success1 is True

        # Try to insert second source with same hash but different ID
        success2 = db.upsert_source_from_capture(
            source_id="src_page2",  # Different ID
            url="https://example.com/page2",
            final_url="https://example.com/page2",
            title="Page Two",
            clean_text="Same content",
            content_hash="same_hash_123",  # Same hash
            fetched_at=datetime.now(timezone.utc).isoformat(),
            run_id="run_002",
        )
        # Should return False for dedupe
        assert success2 is False

        # Verify only one record exists with that hash
        found = db.get_source_by_hash("same_hash_123")
        assert found is not None
        assert found["id"] == "src_page1"  # Original record preserved

    def test_get_source_by_hash(self, tmp_path: Path):
        """Should retrieve source by content hash."""
        from agnetwork.storage.sqlite import SQLiteManager

        db_path = tmp_path / "test.db"
        db = SQLiteManager.unscoped(db_path)

        # Insert a source
        db.upsert_source_from_capture(
            source_id="src_find_me",
            url="https://example.com/find-me",
            final_url="https://example.com/find-me",
            title="Find Me Page",
            clean_text="Find me content",
            content_hash="unique_hash_789",
            fetched_at=datetime.now(timezone.utc).isoformat(),
            run_id="run_xyz",
        )

        # Retrieve by hash
        found = db.get_source_by_hash("unique_hash_789")
        assert found is not None
        assert found["uri"] == "https://example.com/find-me"

        # Non-existent hash returns None
        not_found = db.get_source_by_hash("does_not_exist")
        assert not_found is None


# =============================================================================
# Tests: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Edge case and error handling tests."""

    def test_extract_text_with_no_body(self):
        """HTML without body should still work."""
        html = b"<html><head><title>No Body</title></head></html>"
        result = extract_text(html)
        assert result.title == "No Body"

    def test_extract_text_unicode(self):
        """Unicode content should be handled correctly."""
        html = b"""
        <html>
        <head><title>Japanese Title</title></head>
        <body><p>Hello World - \xc3\xa9\xc3\xa8\xc3\xa0</p></body>
        </html>
        """
        result = extract_text(html)
        assert "Hello World" in result.text
        assert result.title == "Japanese Title"

    def test_fetch_result_handles_binary_content(self):
        """FetchResult should handle non-text content."""
        result = FetchResult(
            url="https://example.com/image.png",
            final_url="https://example.com/image.png",
            status_code=200,
            headers={"content-type": "image/png"},
            content_bytes=b"\x89PNG\r\n\x1a\n",  # PNG magic bytes
            fetched_at=datetime.now(timezone.utc),
            content_hash="abc123",
            error=None
        )
        assert result.is_success is True
        assert result.is_html is False
        assert len(result.content_bytes) == 8

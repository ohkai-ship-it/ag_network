"""HTML to text extraction tool.

Provides clean text extraction from HTML content.
"""

import re
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup, Comment


@dataclass
class CleanResult:
    """Result of HTML text extraction."""

    text: str
    title: Optional[str]
    content_type: str
    method: str
    char_count: int

    @property
    def is_empty(self) -> bool:
        """Check if extracted text is empty."""
        return not self.text.strip()


# Tags to remove completely (including their content)
REMOVE_TAGS = {
    "script",
    "style",
    "noscript",
    "header",
    "footer",
    "nav",
    "aside",
    "form",
    "iframe",
    "svg",
    "canvas",
    "video",
    "audio",
    "map",
    "object",
    "embed",
}

# Tags that typically contain main content
CONTENT_TAGS = {"article", "main", "section", "div", "p", "h1", "h2", "h3", "h4", "h5", "h6"}


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text."""
    # Replace multiple whitespace with single space
    text = re.sub(r"[ \t]+", " ", text)
    # Replace multiple newlines with double newline (paragraph break)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip leading/trailing whitespace from lines
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def _extract_title(soup: BeautifulSoup) -> Optional[str]:
    """Extract page title from HTML."""
    # Try <title> tag first
    if soup.title and soup.title.string:
        return soup.title.string.strip()

    # Try <h1> tag
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)

    # Try og:title meta tag
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()

    return None


def _find_main_content(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    """Try to find the main content area of the page."""
    # Look for semantic main content tags
    for tag in ["main", "article"]:
        element = soup.find(tag)
        if element:
            return element

    # Look for common content div IDs/classes
    content_patterns = [
        {"id": re.compile(r"content|main|article|body", re.I)},
        {"class_": re.compile(r"content|main|article|body|post", re.I)},
    ]

    for pattern in content_patterns:
        element = soup.find("div", pattern)
        if element:
            # Check if it has substantial text
            text = element.get_text(strip=True)
            if len(text) > 200:
                return element

    return None


def extract_text(
    html_bytes: bytes,
    *,
    url: Optional[str] = None,
    encoding: Optional[str] = None,
) -> CleanResult:
    """Extract readable text from HTML content.

    Args:
        html_bytes: Raw HTML bytes
        url: Optional source URL (for context)
        encoding: Optional encoding override

    Returns:
        CleanResult with extracted text and metadata
    """
    # Detect encoding
    if encoding is None:
        # Try to detect from content
        try:
            # First try UTF-8
            html_str = html_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                # Fall back to latin-1 (always succeeds)
                html_str = html_bytes.decode("latin-1")
            except Exception:
                html_str = html_bytes.decode("utf-8", errors="replace")
    else:
        html_str = html_bytes.decode(encoding, errors="replace")

    # Parse HTML
    soup = BeautifulSoup(html_str, "lxml")

    # Extract title first
    title = _extract_title(soup)

    # Remove unwanted tags
    for tag in soup.find_all(REMOVE_TAGS):
        tag.decompose()

    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Try to find main content area
    main_content = _find_main_content(soup)

    if main_content:
        text = main_content.get_text(separator="\n")
        method = "main_content"
    else:
        # Fall back to body or full document
        body = soup.body or soup
        text = body.get_text(separator="\n")
        method = "bs4_body"

    # Normalize whitespace
    text = _normalize_whitespace(text)

    # Determine content type
    content_type = "text/html"
    meta_content_type = soup.find("meta", {"http-equiv": re.compile(r"content-type", re.I)})
    if meta_content_type and meta_content_type.get("content"):
        content_type = meta_content_type["content"].split(";")[0].strip()

    return CleanResult(
        text=text,
        title=title,
        content_type=content_type,
        method=method,
        char_count=len(text),
    )


def extract_text_simple(html_bytes: bytes) -> str:
    """Simple text extraction - just strip tags and normalize.

    Args:
        html_bytes: Raw HTML bytes

    Returns:
        Extracted text string
    """
    result = extract_text(html_bytes)
    return result.text

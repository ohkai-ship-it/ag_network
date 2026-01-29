"""Deep link discovery and extraction for multi-page source enrichment.

This module provides deterministic candidate extraction from HTML pages,
with optional LLM-assisted selection constrained to provided candidates.

M8 Implementation:
- extract_link_candidates(): Parse and filter links from HTML
- score_and_rank(): Deterministic scoring based on config keywords
- select_deterministic(): Pick top N per category
- select_with_agent(): Optional LLM-assisted selection (constrained)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class LinkCategory(str, Enum):
    """Categories for deep link classification."""

    ABOUT = "about"
    SERVICES = "services"
    NEWS = "news"
    CAREERS = "careers"
    PRODUCTS = "products"
    CONTACT = "contact"
    OTHER = "other"


@dataclass
class LinkCandidate:
    """A candidate link extracted from a page."""

    url: str
    anchor_text: str
    rel: Optional[str] = None
    css_class: Optional[str] = None
    source_location: str = "body"  # "nav", "header", "footer", "body"
    is_same_host: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "anchor_text": self.anchor_text,
            "rel": self.rel,
            "css_class": self.css_class,
            "source_location": self.source_location,
            "is_same_host": self.is_same_host,
        }


@dataclass
class ScoredCandidate:
    """A link candidate with category scores and ranking."""

    candidate: LinkCandidate
    category_scores: Dict[str, float] = field(default_factory=dict)
    best_category: str = "other"
    best_score: float = 0.0
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.candidate.url,
            "anchor_text": self.candidate.anchor_text,
            "category_scores": self.category_scores,
            "best_category": self.best_category,
            "best_score": self.best_score,
            "reasons": self.reasons,
            "source_location": self.candidate.source_location,
        }


@dataclass
class DeepLinkSelection:
    """A selected deep link for fetching."""

    category: str
    url: str
    reason: str
    method: str = "deterministic"  # "deterministic" or "agent"
    anchor_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "category": self.category,
            "url": self.url,
            "reason": self.reason,
            "method": self.method,
            "anchor_text": self.anchor_text,
        }


@dataclass
class DeepLinksConfig:
    """Configuration for deep link discovery."""

    # Keywords per category (matched in path and anchor text)
    category_keywords: Dict[str, List[str]] = field(default_factory=dict)

    # Keywords to blacklist (legal pages, etc.)
    blacklist_keywords: List[str] = field(default_factory=list)

    # Selection caps
    max_per_category: int = 1
    max_total: int = 4

    # Domain restrictions
    same_domain_only: bool = True

    # Config version for auditing
    version: str = "1.0.0"

    @classmethod
    def load_default(cls) -> "DeepLinksConfig":
        """Load default configuration."""
        return cls(
            category_keywords={
                "about": [
                    "about",
                    "about-us",
                    "uber-uns",
                    "ueber-uns",
                    "unternehmen",
                    "company",
                    "who-we-are",
                    "our-story",
                    "team",
                    "leadership",
                    "management",
                    "history",
                    "mission",
                    "vision",
                    "values",
                ],
                "services": [
                    "services",
                    "leistungen",
                    "dienstleistungen",
                    "angebot",
                    "offerings",
                    "solutions",
                    "what-we-do",
                    "capabilities",
                    "consulting",
                    "beratung",
                ],
                "news": [
                    "news",
                    "blog",
                    "aktuelles",
                    "neuigkeiten",
                    "press",
                    "presse",
                    "media",
                    "insights",
                    "articles",
                    "updates",
                    "announcements",
                    "releases",
                ],
                "careers": [
                    "careers",
                    "jobs",
                    "karriere",
                    "stellenangebote",
                    "work-with-us",
                    "join-us",
                    "opportunities",
                    "vacancies",
                    "employment",
                    "hiring",
                ],
                "products": [
                    "products",
                    "produkte",
                    "portfolio",
                    "brands",
                    "catalog",
                    "shop",
                    "store",
                ],
                "contact": [
                    "contact",
                    "kontakt",
                    "get-in-touch",
                    "reach-us",
                    "connect",
                    "locations",
                    "standorte",
                ],
            },
            blacklist_keywords=[
                "impressum",
                "imprint",
                "datenschutz",
                "privacy",
                "privacy-policy",
                "terms",
                "terms-of-service",
                "terms-of-use",
                "agb",
                "legal",
                "cookie",
                "cookies",
                "disclaimer",
                "nutzungsbedingungen",
                "rechtliches",
                "sitemap",
                "login",
                "signin",
                "sign-in",
                "register",
                "signup",
                "sign-up",
                "logout",
                "cart",
                "checkout",
                "warenkorb",
                "download",
                "pdf",
                "print",
                "drucken",
            ],
            max_per_category=1,
            max_total=4,
            same_domain_only=True,
            version="1.0.0",
        )

    @classmethod
    def from_file(cls, path: Path) -> "DeepLinksConfig":
        """Load configuration from YAML or TOML file.

        Args:
            path: Path to config file (.yaml, .yml, or .toml)

        Returns:
            DeepLinksConfig loaded from file, or defaults on error
        """
        try:
            suffix = path.suffix.lower()
            with open(path) as f:
                if suffix in (".yaml", ".yml"):
                    try:
                        import yaml

                        data = yaml.safe_load(f)
                    except ImportError:
                        logger.warning("pyyaml not installed, cannot load YAML config")
                        return cls.load_default()
                elif suffix == ".toml":
                    import toml

                    data = toml.load(f)
                else:
                    logger.warning(f"Unsupported config format: {suffix}")
                    return cls.load_default()

            return cls(
                category_keywords=data.get("category_keywords", {}),
                blacklist_keywords=data.get("blacklist_keywords", []),
                max_per_category=data.get("max_per_category", 1),
                max_total=data.get("max_total", 4),
                same_domain_only=data.get("same_domain_only", True),
                version=data.get("version", "1.0.0"),
            )
        except Exception as e:
            logger.warning(f"Failed to load config from {path}: {e}, using defaults")
            return cls.load_default()

    @classmethod
    def from_yaml(cls, path: Path) -> "DeepLinksConfig":
        """Load configuration from YAML file (alias for from_file)."""
        return cls.from_file(path)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "category_keywords": self.category_keywords,
            "blacklist_keywords": self.blacklist_keywords,
            "max_per_category": self.max_per_category,
            "max_total": self.max_total,
            "same_domain_only": self.same_domain_only,
            "version": self.version,
        }


def _get_host(url: str) -> str:
    """Extract host from URL."""
    parsed = urlparse(url)
    return parsed.netloc.lower()


def _normalize_url(base_url: str, href: str) -> Optional[str]:
    """Normalize a href to an absolute URL.

    Returns None for non-http links (mailto, tel, javascript, etc.)
    """
    if not href:
        return None

    href = href.strip()

    # Skip non-http schemes
    if href.startswith(("mailto:", "tel:", "javascript:", "data:", "#")):
        return None

    # Handle fragment-only links
    if href.startswith("#"):
        return None

    # Normalize to absolute URL
    try:
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)

        # Only allow http/https
        if parsed.scheme not in ("http", "https"):
            return None

        # Remove fragments
        absolute = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            absolute += f"?{parsed.query}"

        return absolute
    except Exception:
        return None


def _get_link_source_location(element) -> str:  # noqa: C901
    """Determine where in the page structure a link is located."""
    # Walk up the tree to find semantic containers
    for parent in element.parents:
        if parent.name in ("nav", "navigation"):
            return "nav"
        if parent.name == "header":
            return "header"
        if parent.name == "footer":
            return "footer"
        if parent.get("role") == "navigation":
            return "nav"
        # Check for common nav class patterns
        classes = parent.get("class", [])
        if isinstance(classes, list):
            class_str = " ".join(classes).lower()
            if any(x in class_str for x in ["nav", "menu", "header", "footer"]):
                if "nav" in class_str or "menu" in class_str:
                    return "nav"
                if "header" in class_str:
                    return "header"
                if "footer" in class_str:
                    return "footer"
    return "body"


def _is_blacklisted(url: str, anchor_text: str, blacklist: List[str]) -> bool:
    """Check if a link should be blacklisted."""
    url_lower = url.lower()
    anchor_lower = anchor_text.lower() if anchor_text else ""

    for keyword in blacklist:
        keyword_lower = keyword.lower()
        if keyword_lower in url_lower or keyword_lower in anchor_lower:
            return True
    return False


def extract_link_candidates(  # noqa: C901
    seed_url: str,
    raw_html: bytes,
    *,
    config: Optional[DeepLinksConfig] = None,
) -> List[LinkCandidate]:
    """Extract and filter link candidates from HTML.

    Args:
        seed_url: The URL of the page being parsed
        raw_html: Raw HTML content as bytes
        config: Configuration for filtering (uses default if None)

    Returns:
        List of LinkCandidate objects
    """
    if config is None:
        config = DeepLinksConfig.load_default()

    seed_host = _get_host(seed_url)
    candidates: List[LinkCandidate] = []
    seen_urls: set = set()

    try:
        soup = BeautifulSoup(raw_html, "html.parser")
    except Exception as e:
        logger.error(f"Failed to parse HTML: {e}")
        return []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "")
        normalized_url = _normalize_url(seed_url, href)

        if normalized_url is None:
            continue

        # Skip already seen URLs
        if normalized_url in seen_urls:
            continue
        seen_urls.add(normalized_url)

        # Skip if same as seed URL
        if normalized_url.rstrip("/") == seed_url.rstrip("/"):
            continue

        # Get anchor text
        anchor_text = a_tag.get_text(strip=True) or ""

        # Check blacklist
        if _is_blacklisted(normalized_url, anchor_text, config.blacklist_keywords):
            continue

        # Check same host
        link_host = _get_host(normalized_url)
        is_same_host = link_host == seed_host

        if config.same_domain_only and not is_same_host:
            continue

        # Extract additional attributes
        rel = a_tag.get("rel")
        if isinstance(rel, list):
            rel = " ".join(rel)

        css_class = a_tag.get("class")
        if isinstance(css_class, list):
            css_class = " ".join(css_class)

        source_location = _get_link_source_location(a_tag)

        candidate = LinkCandidate(
            url=normalized_url,
            anchor_text=anchor_text,
            rel=rel,
            css_class=css_class,
            source_location=source_location,
            is_same_host=is_same_host,
        )
        candidates.append(candidate)

    logger.info(f"Extracted {len(candidates)} link candidates from {seed_url}")
    return candidates


def _calculate_category_score(
    candidate: LinkCandidate,
    category: str,
    keywords: List[str],
) -> Tuple[float, List[str]]:
    """Calculate score for a specific category.

    Returns (score, list of matching reasons)
    """
    score = 0.0
    reasons = []

    anchor_lower = candidate.anchor_text.lower() if candidate.anchor_text else ""

    # Parse URL path for matching
    parsed = urlparse(candidate.url)
    path_lower = parsed.path.lower()

    for keyword in keywords:
        keyword_lower = keyword.lower()

        # Path match (highest weight)
        if keyword_lower in path_lower:
            score += 3.0
            reasons.append(f"path contains '{keyword}'")

        # Anchor text match (medium weight)
        if keyword_lower in anchor_lower:
            score += 2.0
            reasons.append(f"anchor contains '{keyword}'")

    # Bonus for nav/header location (usually main navigation)
    if candidate.source_location in ("nav", "header"):
        score *= 1.2

    return score, reasons


def score_and_rank(
    candidates: List[LinkCandidate],
    config: Optional[DeepLinksConfig] = None,
) -> List[ScoredCandidate]:
    """Score and rank candidates based on config keywords.

    Args:
        candidates: List of link candidates
        config: Configuration with keywords (uses default if None)

    Returns:
        List of ScoredCandidate objects, sorted by best score descending
    """
    if config is None:
        config = DeepLinksConfig.load_default()

    scored: List[ScoredCandidate] = []

    for candidate in candidates:
        category_scores: Dict[str, float] = {}
        all_reasons: List[str] = []
        best_category = "other"
        best_score = 0.0

        for category, keywords in config.category_keywords.items():
            score, reasons = _calculate_category_score(candidate, category, keywords)
            category_scores[category] = score
            all_reasons.extend(reasons)

            if score > best_score:
                best_score = score
                best_category = category

        scored_candidate = ScoredCandidate(
            candidate=candidate,
            category_scores=category_scores,
            best_category=best_category,
            best_score=best_score,
            reasons=list(set(all_reasons)),  # Deduplicate reasons
        )
        scored.append(scored_candidate)

    # Sort by best score descending
    scored.sort(key=lambda x: x.best_score, reverse=True)
    return scored


def select_deterministic(
    ranked: List[ScoredCandidate],
    config: Optional[DeepLinksConfig] = None,
) -> List[DeepLinkSelection]:
    """Select top links deterministically.

    Picks top 1 per category, capped at max_total.

    Args:
        ranked: Scored candidates sorted by score
        config: Configuration with selection caps

    Returns:
        List of DeepLinkSelection objects
    """
    if config is None:
        config = DeepLinksConfig.load_default()

    selections: List[DeepLinkSelection] = []
    categories_selected: Dict[str, int] = {}

    for scored in ranked:
        if len(selections) >= config.max_total:
            break

        category = scored.best_category

        # Skip if we've already selected max for this category
        if categories_selected.get(category, 0) >= config.max_per_category:
            continue

        # Skip zero-score candidates
        if scored.best_score <= 0:
            continue

        # Create selection
        reason = ", ".join(scored.reasons[:3]) if scored.reasons else "top ranked"
        selection = DeepLinkSelection(
            category=category,
            url=scored.candidate.url,
            reason=reason,
            method="deterministic",
            anchor_text=scored.candidate.anchor_text,
        )
        selections.append(selection)
        categories_selected[category] = categories_selected.get(category, 0) + 1

    logger.info(f"Deterministic selection: {len(selections)} links")
    return selections


def select_with_agent(  # noqa: C901
    candidates: List[ScoredCandidate],
    *,
    llm,
    seed_url: str,
    config: Optional[DeepLinksConfig] = None,
) -> List[DeepLinkSelection]:
    """Select links with LLM assistance (constrained to candidates).

    The LLM can only select from provided candidates. If the LLM returns
    invalid selections, falls back to deterministic selection.

    Args:
        candidates: Scored candidates to choose from
        llm: LLM client (must have .chat() method)
        seed_url: Original seed URL for context
        config: Configuration with selection caps

    Returns:
        List of DeepLinkSelection objects
    """
    if config is None:
        config = DeepLinksConfig.load_default()

    # Build candidate list for LLM (limited to top candidates)
    top_candidates = candidates[: min(20, len(candidates))]
    valid_urls = {c.candidate.url for c in top_candidates}

    # Format candidates for LLM prompt
    candidate_list = []
    for i, scored in enumerate(top_candidates):
        candidate_list.append(
            {
                "index": i,
                "url": scored.candidate.url,
                "anchor_text": scored.candidate.anchor_text,
                "suggested_category": scored.best_category,
                "score": round(scored.best_score, 2),
            }
        )

    categories = list(config.category_keywords.keys())

    system_prompt = f"""You are an expert at analyzing website navigation to select the most relevant pages for business research.

Given a list of candidate URLs from a company website, select up to {config.max_total} pages that would be most useful for business development research.

CATEGORIES to consider: {", ".join(categories)}

RULES:
1. Select at most {config.max_per_category} URL per category
2. Select at most {config.max_total} URLs total
3. Only select URLs that appear in the provided candidates list
4. Prefer pages that reveal company information useful for sales/BD
5. Return ONLY valid JSON - no explanation text

OUTPUT FORMAT (strict JSON):
{{
  "selected": [
    {{"category": "<category>", "url": "<exact url from candidates>", "reason": "<brief reason>"}}
  ]
}}"""

    user_prompt = f"""Website: {seed_url}

Candidate URLs to choose from:
{json.dumps(candidate_list, indent=2)}

Select the most valuable pages for business research. Output JSON only:"""

    try:
        # Call LLM
        response = llm.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,  # Low temperature for consistency
        )

        # Parse response
        response_text = response.get("content", "").strip()

        # Try to extract JSON from response
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if not json_match:
            raise ValueError("No JSON found in response")

        parsed = json.loads(json_match.group())
        selected_raw = parsed.get("selected", [])

        # Validate selections
        selections: List[DeepLinkSelection] = []
        categories_used: set = set()

        for item in selected_raw:
            url = item.get("url", "")
            category = item.get("category", "other")
            reason = item.get("reason", "agent selected")

            # Validation: URL must be in candidates
            if url not in valid_urls:
                logger.warning(f"Agent selected invalid URL (not in candidates): {url}")
                continue

            # Validation: Category should be unique if possible
            if category in categories_used and len(categories_used) < len(categories):
                logger.warning(f"Agent selected duplicate category: {category}")
                # Still allow it, just log warning

            # Validation: Max total
            if len(selections) >= config.max_total:
                break

            # Find anchor text from candidate
            anchor_text = None
            for c in top_candidates:
                if c.candidate.url == url:
                    anchor_text = c.candidate.anchor_text
                    break

            selection = DeepLinkSelection(
                category=category,
                url=url,
                reason=reason,
                method="agent",
                anchor_text=anchor_text,
            )
            selections.append(selection)
            categories_used.add(category)

        if selections:
            logger.info(f"Agent selection: {len(selections)} links")
            return selections
        else:
            logger.warning("Agent returned no valid selections, falling back to deterministic")
            return select_deterministic(candidates, config)

    except Exception as e:
        logger.warning(f"Agent selection failed: {e}, falling back to deterministic")
        return select_deterministic(candidates, config)


@dataclass
class DeepLinksAudit:
    """Audit artifact for deep link discovery."""

    seed_url: str
    config_version: str
    config_settings: Dict[str, Any]
    extracted_count: int
    top_ranked_by_category: Dict[str, List[Dict[str, Any]]]
    deterministic_selection: List[Dict[str, Any]]
    agent_selection: Optional[List[Dict[str, Any]]]
    agent_validation_outcomes: Optional[Dict[str, Any]]
    final_selection: List[Dict[str, Any]]
    selection_method: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "seed_url": self.seed_url,
            "config_version": self.config_version,
            "config_settings": self.config_settings,
            "extracted_count": self.extracted_count,
            "top_ranked_by_category": self.top_ranked_by_category,
            "deterministic_selection": self.deterministic_selection,
            "agent_selection": self.agent_selection,
            "agent_validation_outcomes": self.agent_validation_outcomes,
            "final_selection": self.final_selection,
            "selection_method": self.selection_method,
            "timestamp": self.timestamp,
        }

    def save(self, path: Path) -> None:
        """Save audit to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Saved deep links audit to {path}")


def discover_deep_links(
    seed_url: str,
    raw_html: bytes,
    *,
    config: Optional[DeepLinksConfig] = None,
    use_agent: bool = False,
    llm=None,
) -> Tuple[List[DeepLinkSelection], DeepLinksAudit]:
    """Full deep link discovery pipeline.

    Args:
        seed_url: The seed URL being analyzed
        raw_html: Raw HTML content
        config: Configuration (uses default if None)
        use_agent: Whether to use LLM-assisted selection
        llm: LLM client (required if use_agent=True)

    Returns:
        Tuple of (selections, audit)
    """
    if config is None:
        config = DeepLinksConfig.load_default()

    # Step 1: Extract candidates
    candidates = extract_link_candidates(seed_url, raw_html, config=config)

    # Step 2: Score and rank
    ranked = score_and_rank(candidates, config)

    # Step 3: Deterministic selection (always computed for audit)
    deterministic = select_deterministic(ranked, config)

    # Step 4: Agent selection if requested
    agent_selection = None
    agent_validation = None
    final_selection = deterministic
    selection_method = "deterministic"

    if use_agent and llm is not None:
        try:
            agent_selection_raw = select_with_agent(
                ranked, llm=llm, seed_url=seed_url, config=config
            )
            # Check if agent actually returned agent selections
            if agent_selection_raw and agent_selection_raw[0].method == "agent":
                agent_selection = [s.to_dict() for s in agent_selection_raw]
                final_selection = agent_selection_raw
                selection_method = "agent"
                agent_validation = {"status": "success", "valid_count": len(agent_selection_raw)}
            else:
                agent_validation = {
                    "status": "fallback",
                    "reason": "agent returned no valid selections",
                }
        except Exception as e:
            agent_validation = {"status": "error", "reason": str(e)}
            logger.warning(f"Agent selection failed, using deterministic: {e}")

    # Build top ranked by category for audit
    top_by_category: Dict[str, List[Dict[str, Any]]] = {}
    for scored in ranked[:20]:  # Top 20 for audit
        cat = scored.best_category
        if cat not in top_by_category:
            top_by_category[cat] = []
        if len(top_by_category[cat]) < 3:  # Top 3 per category
            top_by_category[cat].append(scored.to_dict())

    # Create audit
    audit = DeepLinksAudit(
        seed_url=seed_url,
        config_version=config.version,
        config_settings={
            "max_per_category": config.max_per_category,
            "max_total": config.max_total,
            "same_domain_only": config.same_domain_only,
        },
        extracted_count=len(candidates),
        top_ranked_by_category=top_by_category,
        deterministic_selection=[s.to_dict() for s in deterministic],
        agent_selection=agent_selection,
        agent_validation_outcomes=agent_validation,
        final_selection=[s.to_dict() for s in final_selection],
        selection_method=selection_method,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    return final_selection, audit


def is_homepage_url(url: str) -> bool:
    """Check if URL appears to be a homepage.

    Args:
        url: URL to check

    Returns:
        True if URL looks like a homepage (path is / or empty)
    """
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return path == "" or path == "/"

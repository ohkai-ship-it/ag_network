"""Tests for M8: Deep Link Discovery and Evidence Snippets.

Tests cover:
- Deep link extraction from HTML
- Deterministic candidate selection
- Agent selection validation (mocked)
- Evidence snippet verification
- Integration smoke test with mocked fetch
"""

import json
from typing import Optional
from unittest.mock import MagicMock

import pytest

from agnetwork.tools.web.deeplinks import (
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

# =============================================================================
# Test Fixtures
# =============================================================================

# Sample HTML with various link types
SAMPLE_HTML = b"""
<!DOCTYPE html>
<html>
<head>
    <title>Test Company GmbH</title>
</head>
<body>
    <header>
        <nav>
            <a href="/">Home</a>
            <a href="/about-us">About Us</a>
            <a href="/services">Our Services</a>
            <a href="/careers">Careers</a>
            <a href="/news">News</a>
            <a href="/contact">Contact</a>
        </nav>
    </header>
    <main>
        <h1>Welcome to Test Company</h1>
        <p>We are a leading provider of solutions.</p>
        <a href="/products">View our Products</a>
        <a href="/case-studies">Case Studies</a>
        <a href="https://external.com/partner">Partner Site</a>
    </main>
    <footer>
        <a href="/impressum">Impressum</a>
        <a href="/datenschutz">Privacy Policy</a>
        <a href="mailto:info@test.com">Email Us</a>
        <a href="tel:+1234567890">Call Us</a>
        <a href="#top">Back to Top</a>
    </footer>
</body>
</html>
"""

SEED_URL = "https://www.testcompany.com/"


@pytest.fixture
def sample_config():
    """Provide a test configuration."""
    return DeepLinksConfig.load_default()


@pytest.fixture
def sample_candidates():
    """Provide pre-extracted candidates for scoring tests."""
    return [
        LinkCandidate(
            url="https://www.testcompany.com/about-us",
            anchor_text="About Us",
            source_location="nav",
        ),
        LinkCandidate(
            url="https://www.testcompany.com/services",
            anchor_text="Our Services",
            source_location="nav",
        ),
        LinkCandidate(
            url="https://www.testcompany.com/careers",
            anchor_text="Careers",
            source_location="nav",
        ),
        LinkCandidate(
            url="https://www.testcompany.com/news",
            anchor_text="News",
            source_location="nav",
        ),
        LinkCandidate(
            url="https://www.testcompany.com/products",
            anchor_text="View our Products",
            source_location="body",
        ),
    ]


# =============================================================================
# Test: Deep Link Extraction
# =============================================================================

class TestExtractLinkCandidates:
    """Tests for extract_link_candidates function."""

    def test_extracts_links_from_html(self, sample_config):
        """Test that links are extracted from HTML."""
        candidates = extract_link_candidates(SEED_URL, SAMPLE_HTML, config=sample_config)

        # Should have extracted multiple candidates
        assert len(candidates) > 0

        # All candidates should be LinkCandidate objects
        assert all(isinstance(c, LinkCandidate) for c in candidates)

    def test_filters_same_host(self, sample_config):
        """Test that external links are filtered when same_domain_only=True."""
        candidates = extract_link_candidates(SEED_URL, SAMPLE_HTML, config=sample_config)

        # All should be same host
        for c in candidates:
            assert c.is_same_host

    def test_filters_blacklisted(self, sample_config):
        """Test that blacklisted pages are excluded."""
        candidates = extract_link_candidates(SEED_URL, SAMPLE_HTML, config=sample_config)

        urls = [c.url for c in candidates]

        # Should not include impressum or datenschutz
        assert not any("impressum" in u.lower() for u in urls)
        assert not any("datenschutz" in u.lower() for u in urls)
        assert not any("privacy" in u.lower() for u in urls)

    def test_filters_non_http_schemes(self, sample_config):
        """Test that mailto, tel, javascript links are excluded."""
        candidates = extract_link_candidates(SEED_URL, SAMPLE_HTML, config=sample_config)

        urls = [c.url for c in candidates]

        # Should not include mailto or tel
        assert not any(u.startswith("mailto:") for u in urls)
        assert not any(u.startswith("tel:") for u in urls)

    def test_filters_fragment_only(self, sample_config):
        """Test that fragment-only links are excluded."""
        candidates = extract_link_candidates(SEED_URL, SAMPLE_HTML, config=sample_config)

        urls = [c.url for c in candidates]

        # Should not include #top
        assert not any(u == "#top" for u in urls)

    def test_captures_anchor_text(self, sample_config):
        """Test that anchor text is captured."""
        candidates = extract_link_candidates(SEED_URL, SAMPLE_HTML, config=sample_config)

        # Find the about link
        about_links = [c for c in candidates if "about" in c.url.lower()]
        assert len(about_links) >= 1
        assert about_links[0].anchor_text == "About Us"

    def test_identifies_source_location(self, sample_config):
        """Test that source location (nav/body) is identified."""
        candidates = extract_link_candidates(SEED_URL, SAMPLE_HTML, config=sample_config)

        # Should have some nav links
        nav_links = [c for c in candidates if c.source_location == "nav"]
        assert len(nav_links) > 0

    def test_normalizes_to_absolute_urls(self, sample_config):
        """Test that relative URLs are normalized to absolute."""
        candidates = extract_link_candidates(SEED_URL, SAMPLE_HTML, config=sample_config)

        # All URLs should be absolute
        for c in candidates:
            assert c.url.startswith("https://")

    def test_deduplicates_urls(self, sample_config):
        """Test that duplicate URLs are removed."""
        candidates = extract_link_candidates(SEED_URL, SAMPLE_HTML, config=sample_config)

        urls = [c.url for c in candidates]
        assert len(urls) == len(set(urls))


# =============================================================================
# Test: Scoring and Ranking
# =============================================================================

class TestScoreAndRank:
    """Tests for score_and_rank function."""

    def test_scores_candidates(self, sample_candidates, sample_config):
        """Test that candidates are scored."""
        scored = score_and_rank(sample_candidates, config=sample_config)

        assert len(scored) == len(sample_candidates)
        assert all(isinstance(s, ScoredCandidate) for s in scored)

    def test_assigns_categories(self, sample_candidates, sample_config):
        """Test that categories are assigned based on keywords."""
        scored = score_and_rank(sample_candidates, config=sample_config)

        # Find the about link
        about = [s for s in scored if "about" in s.candidate.url.lower()][0]
        assert about.best_category == "about"

        # Find careers link
        careers = [s for s in scored if "careers" in s.candidate.url.lower()][0]
        assert careers.best_category == "careers"

    def test_ranks_by_score(self, sample_candidates, sample_config):
        """Test that results are ranked by best_score descending."""
        scored = score_and_rank(sample_candidates, config=sample_config)

        scores = [s.best_score for s in scored]
        assert scores == sorted(scores, reverse=True)

    def test_provides_reasons(self, sample_candidates, sample_config):
        """Test that scoring reasons are provided."""
        scored = score_and_rank(sample_candidates, config=sample_config)

        # High-scoring candidates should have reasons
        top = scored[0]
        if top.best_score > 0:
            assert len(top.reasons) > 0


# =============================================================================
# Test: Deterministic Selection
# =============================================================================

class TestSelectDeterministic:
    """Tests for select_deterministic function."""

    def test_selects_top_per_category(self, sample_candidates, sample_config):
        """Test that top link per category is selected."""
        scored = score_and_rank(sample_candidates, config=sample_config)
        selections = select_deterministic(scored, config=sample_config)

        # Should have selections
        assert len(selections) > 0
        assert len(selections) <= sample_config.max_total

    def test_respects_max_total(self, sample_candidates):
        """Test that max_total is respected."""
        config = DeepLinksConfig.load_default()
        config.max_total = 2

        scored = score_and_rank(sample_candidates, config=config)
        selections = select_deterministic(scored, config=config)

        assert len(selections) <= 2

    def test_respects_max_per_category(self, sample_candidates):
        """Test that max_per_category is respected."""
        config = DeepLinksConfig.load_default()
        config.max_per_category = 1

        scored = score_and_rank(sample_candidates, config=config)
        selections = select_deterministic(scored, config=config)

        # Count categories
        categories = [s.category for s in selections]
        for cat in set(categories):
            assert categories.count(cat) <= 1

    def test_returns_deep_link_selection(self, sample_candidates, sample_config):
        """Test that selections are DeepLinkSelection objects."""
        scored = score_and_rank(sample_candidates, config=sample_config)
        selections = select_deterministic(scored, config=sample_config)

        assert all(isinstance(s, DeepLinkSelection) for s in selections)
        for s in selections:
            assert s.method == "deterministic"
            assert s.url
            assert s.category


# =============================================================================
# Test: Agent Selection (Mocked)
# =============================================================================

class TestSelectWithAgent:
    """Tests for select_with_agent function with mocked LLM."""

    def test_valid_agent_selection(self, sample_candidates, sample_config):
        """Test that valid agent selection is used."""
        scored = score_and_rank(sample_candidates, config=sample_config)

        # Mock LLM that returns valid selection
        mock_llm = MagicMock()
        mock_llm.chat.return_value = {
            "content": json.dumps({
                "selected": [
                    {
                        "category": "about",
                        "url": "https://www.testcompany.com/about-us",
                        "reason": "Company information",
                    },
                    {
                        "category": "services",
                        "url": "https://www.testcompany.com/services",
                        "reason": "Service offerings",
                    },
                ]
            })
        }

        selections = select_with_agent(
            scored,
            llm=mock_llm,
            seed_url=SEED_URL,
            config=sample_config,
        )

        assert len(selections) == 2
        assert all(s.method == "agent" for s in selections)
        assert mock_llm.chat.called

    def test_invalid_url_falls_back(self, sample_candidates, sample_config):
        """Test that invalid URLs fall back to deterministic."""
        scored = score_and_rank(sample_candidates, config=sample_config)

        # Mock LLM that returns invalid URL
        mock_llm = MagicMock()
        mock_llm.chat.return_value = {
            "content": json.dumps({
                "selected": [
                    {
                        "category": "about",
                        "url": "https://www.invalid.com/not-a-candidate",
                        "reason": "Invented URL",
                    },
                ]
            })
        }

        selections = select_with_agent(
            scored,
            llm=mock_llm,
            seed_url=SEED_URL,
            config=sample_config,
        )

        # Should fall back to deterministic (no agent selections valid)
        assert all(s.method == "deterministic" for s in selections)

    def test_llm_error_falls_back(self, sample_candidates, sample_config):
        """Test that LLM errors fall back to deterministic."""
        scored = score_and_rank(sample_candidates, config=sample_config)

        # Mock LLM that raises error
        mock_llm = MagicMock()
        mock_llm.chat.side_effect = Exception("LLM error")

        selections = select_with_agent(
            scored,
            llm=mock_llm,
            seed_url=SEED_URL,
            config=sample_config,
        )

        # Should fall back to deterministic
        assert all(s.method == "deterministic" for s in selections)

    def test_invalid_json_falls_back(self, sample_candidates, sample_config):
        """Test that invalid JSON falls back to deterministic."""
        scored = score_and_rank(sample_candidates, config=sample_config)

        # Mock LLM that returns invalid JSON
        mock_llm = MagicMock()
        mock_llm.chat.return_value = {
            "content": "This is not valid JSON at all"
        }

        selections = select_with_agent(
            scored,
            llm=mock_llm,
            seed_url=SEED_URL,
            config=sample_config,
        )

        # Should fall back to deterministic
        assert all(s.method == "deterministic" for s in selections)


# =============================================================================
# Test: Full Discovery Pipeline
# =============================================================================

class TestDiscoverDeepLinks:
    """Tests for discover_deep_links function."""

    def test_full_pipeline_deterministic(self, sample_config):
        """Test full discovery pipeline in deterministic mode."""
        selections, audit = discover_deep_links(
            SEED_URL,
            SAMPLE_HTML,
            config=sample_config,
            use_agent=False,
        )

        # Should have selections
        assert len(selections) > 0

        # Should have audit
        assert audit.seed_url == SEED_URL
        assert audit.selection_method == "deterministic"
        assert audit.extracted_count > 0
        assert len(audit.final_selection) == len(selections)

    def test_audit_contains_config(self, sample_config):
        """Test that audit contains configuration info."""
        _, audit = discover_deep_links(
            SEED_URL,
            SAMPLE_HTML,
            config=sample_config,
        )

        assert audit.config_version == sample_config.version
        assert "max_total" in audit.config_settings
        assert "same_domain_only" in audit.config_settings

    def test_audit_serializable(self, sample_config):
        """Test that audit can be serialized to JSON."""
        _, audit = discover_deep_links(
            SEED_URL,
            SAMPLE_HTML,
            config=sample_config,
        )

        # Should serialize without error
        audit_dict = audit.to_dict()
        json_str = json.dumps(audit_dict)

        # Should parse back
        parsed = json.loads(json_str)
        assert parsed["seed_url"] == SEED_URL


# =============================================================================
# Test: Homepage Detection
# =============================================================================

class TestIsHomepageUrl:
    """Tests for is_homepage_url function."""

    def test_root_path_is_homepage(self):
        """Test that root path is detected as homepage."""
        assert is_homepage_url("https://example.com/") is True
        assert is_homepage_url("https://example.com") is True

    def test_subpath_is_not_homepage(self):
        """Test that subpaths are not homepage."""
        assert is_homepage_url("https://example.com/about") is False
        assert is_homepage_url("https://example.com/en/") is False

    def test_with_query_params(self):
        """Test homepage with query params."""
        # Root with params - still homepage
        assert is_homepage_url("https://example.com/?lang=en") is True


# =============================================================================
# Test: Evidence Snippet Verification
# =============================================================================

class TestEvidenceVerification:
    """Tests for evidence snippet verification in verifier."""

    def test_quote_exists_passes(self):
        """Test that existing quote passes verification."""
        from agnetwork.eval.verifier import Verifier
        from agnetwork.kernel.contracts import ArtifactKind, ArtifactRef, SkillResult

        # Source text containing the quote
        source_text = "We are a leading provider of enterprise solutions since 1999."

        # Research brief with evidence
        research_brief = {
            "company": "Test Corp",
            "snapshot": "Test company",
            "pains": ["pain1"],
            "triggers": ["trigger1"],
            "competitors": ["comp1"],
            "personalization_angles": [
                {
                    "name": "Experience",
                    "fact": "Long history in enterprise",
                    "is_assumption": False,
                    "source_ids": ["src_test"],
                    "evidence": [
                        {
                            "source_id": "src_test",
                            "quote": "leading provider of enterprise solutions since 1999",
                        }
                    ],
                }
            ],
        }

        # Create skill result
        result = SkillResult(
            output=None,
            artifacts=[
                ArtifactRef(
                    name="research_brief",
                    kind=ArtifactKind.JSON,
                    content=json.dumps(research_brief),
                )
            ],
            claims=[],
            skill_name="research",
            skill_version="1.0",
        )

        # Verifier with source loader
        def load_source(source_id: str) -> Optional[str]:
            if source_id == "src_test":
                return source_text
            return None

        verifier = Verifier(source_loader=load_source)
        issues = verifier.verify_skill_result(result, verify_evidence_quotes=True)

        # Should have no evidence_quotes errors
        evidence_issues = [i for i in issues if i.check == "evidence_quotes"]
        assert len(evidence_issues) == 0

    def test_quote_missing_fails(self):
        """Test that missing quote fails verification."""
        from agnetwork.eval.verifier import Verifier
        from agnetwork.kernel.contracts import ArtifactKind, ArtifactRef, SkillResult

        # Source text that does NOT contain the quote
        source_text = "We are a company that does things."

        # Research brief with evidence (quote not in source)
        research_brief = {
            "company": "Test Corp",
            "snapshot": "Test company",
            "pains": ["pain1"],
            "triggers": ["trigger1"],
            "competitors": ["comp1"],
            "personalization_angles": [
                {
                    "name": "Experience",
                    "fact": "Market leader",
                    "is_assumption": False,
                    "source_ids": ["src_test"],
                    "evidence": [
                        {
                            "source_id": "src_test",
                            "quote": "This quote does not exist in the source text",
                        }
                    ],
                }
            ],
        }

        result = SkillResult(
            output=None,
            artifacts=[
                ArtifactRef(
                    name="research_brief",
                    kind=ArtifactKind.JSON,
                    content=json.dumps(research_brief),
                )
            ],
            claims=[],
            skill_name="research",
            skill_version="1.0",
        )

        def load_source(source_id: str) -> Optional[str]:
            if source_id == "src_test":
                return source_text
            return None

        verifier = Verifier(source_loader=load_source)
        issues = verifier.verify_skill_result(result, verify_evidence_quotes=True)

        # Should have an evidence_quotes error
        evidence_issues = [i for i in issues if i.check == "evidence_quotes"]
        assert len(evidence_issues) > 0
        assert evidence_issues[0].severity.value == "error"

    def test_non_assumption_without_evidence_fails(self):
        """Test that non-assumption without evidence fails."""
        from agnetwork.eval.verifier import Verifier
        from agnetwork.kernel.contracts import ArtifactKind, ArtifactRef, SkillResult

        # Research brief with non-assumption but no evidence
        research_brief = {
            "company": "Test Corp",
            "snapshot": "Test company",
            "pains": ["pain1"],
            "triggers": ["trigger1"],
            "competitors": ["comp1"],
            "personalization_angles": [
                {
                    "name": "Experience",
                    "fact": "Some fact",
                    "is_assumption": False,  # Not an assumption
                    "source_ids": ["src_test"],
                    "evidence": [],  # But no evidence!
                }
            ],
        }

        result = SkillResult(
            output=None,
            artifacts=[
                ArtifactRef(
                    name="research_brief",
                    kind=ArtifactKind.JSON,
                    content=json.dumps(research_brief),
                )
            ],
            claims=[],
            skill_name="research",
            skill_version="1.0",
        )

        verifier = Verifier()
        issues = verifier.verify_skill_result(result, verify_evidence_quotes=True)

        # Should have an evidence_quotes error
        evidence_issues = [i for i in issues if i.check == "evidence_quotes"]
        assert len(evidence_issues) > 0
        assert "no evidence" in evidence_issues[0].message.lower()


# =============================================================================
# Test: Integration Smoke Test
# =============================================================================

class TestIntegrationSmoke:
    """Integration smoke tests with mocked fetch."""

    def test_research_with_deep_links_mocked(self, tmp_path):
        """Test research command with deep links using mocked fetch."""
        from agnetwork.tools.web.deeplinks import discover_deep_links

        # Test that we can run the full pipeline
        selections, audit = discover_deep_links(
            SEED_URL,
            SAMPLE_HTML,
            config=DeepLinksConfig.load_default(),
            use_agent=False,
        )

        # Verify we got selections
        assert len(selections) > 0

        # Save audit to tmp path
        audit_path = tmp_path / "deeplinks.json"
        audit.save(audit_path)

        # Verify audit file exists and is valid JSON
        assert audit_path.exists()
        with open(audit_path) as f:
            audit_data = json.load(f)

        assert "seed_url" in audit_data
        assert "final_selection" in audit_data
        assert len(audit_data["final_selection"]) == len(selections)

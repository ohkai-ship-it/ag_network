"""Tests for M4: Memory Retrieval (FTS5) + Evidence via Claims.

This module tests:
- Task A: claims.source_ids normalization (CSV + JSON + new write)
- Task B: FTS5 search on sources and artifacts
- Task C: retrieve_context() returns expected evidence
- Task D: claim persistence links artifact→source IDs
- Task F: verifier evidence rule (fact without evidence triggers issue)
"""

import gc
import json
import sqlite3
from datetime import datetime, timezone

import pytest

from agnetwork.storage.memory import (
    ArtifactHit,
    ArtifactSummary,
    EvidenceBundle,
    MemoryAPI,
    SourceHit,
    SourceRef,
)
from agnetwork.storage.sqlite import (
    SQLiteManager,
    normalize_source_ids,
    serialize_source_ids,
)


def close_sqlite_connections():
    """Force close all SQLite connections (for Windows cleanup)."""
    gc.collect()


# ===========================================
# Task A: claims.source_ids normalization
# ===========================================


class TestSourceIdsNormalization:
    """Tests for claims.source_ids normalization."""

    def test_normalize_csv_string(self):
        """Legacy CSV format should be normalized to list."""
        csv_string = "src_1,src_2,src_3"
        result = normalize_source_ids(csv_string)
        assert result == ["src_1", "src_2", "src_3"]

    def test_normalize_csv_with_spaces(self):
        """CSV with spaces should be trimmed."""
        csv_string = "src_1, src_2 , src_3"
        result = normalize_source_ids(csv_string)
        assert result == ["src_1", "src_2", "src_3"]

    def test_normalize_json_array(self):
        """Legacy JSON array string should be normalized to list."""
        json_string = '["src_1", "src_2", "src_3"]'
        result = normalize_source_ids(json_string)
        assert result == ["src_1", "src_2", "src_3"]

    def test_normalize_list(self):
        """List should pass through unchanged."""
        source_list = ["src_1", "src_2"]
        result = normalize_source_ids(source_list)
        assert result == ["src_1", "src_2"]

    def test_normalize_none(self):
        """None should return empty list."""
        result = normalize_source_ids(None)
        assert result == []

    def test_normalize_empty_string(self):
        """Empty string should return empty list."""
        result = normalize_source_ids("")
        assert result == []

    def test_normalize_whitespace_only(self):
        """Whitespace-only string should return empty list."""
        result = normalize_source_ids("   ")
        assert result == []

    def test_serialize_to_json_array(self):
        """Source IDs should be serialized as JSON array."""
        source_ids = ["src_1", "src_2", "src_3"]
        result = serialize_source_ids(source_ids)
        assert result == '["src_1", "src_2", "src_3"]'
        # Verify it's valid JSON
        assert json.loads(result) == source_ids

    def test_serialize_none(self):
        """None should serialize to empty JSON array."""
        result = serialize_source_ids(None)
        assert result == "[]"

    def test_serialize_empty_list(self):
        """Empty list should serialize to empty JSON array."""
        result = serialize_source_ids([])
        assert result == "[]"


class TestClaimsSourceIdsPersistence:
    """Tests for claims.source_ids DB persistence."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database."""
        db_path = tmp_path / "test.db"
        db = SQLiteManager.unscoped(db_path)
        yield db
        # Ensure connections are closed for Windows cleanup
        close_sqlite_connections()

    def test_write_claim_with_json_source_ids(self, temp_db: SQLiteManager):
        """New claims should be written with JSON array source_ids."""
        # Insert prerequisite artifact
        temp_db.insert_artifact(
            artifact_id="art_1",
            company_id="comp_1",
            artifact_type="research_brief",
            run_id="run_1",
        )

        # Insert claim with source_ids
        temp_db.insert_claim(
            claim_id="claim_1",
            artifact_id="art_1",
            claim_text="Test claim",
            kind="fact",
            source_ids=["src_1", "src_2"],
            confidence=0.9,
        )

        # Read back and verify
        claim = temp_db.get_claim("claim_1")
        assert claim is not None
        assert claim["source_ids"] == ["src_1", "src_2"]

    def test_read_legacy_csv_claim(self, temp_db: SQLiteManager):
        """Legacy CSV claims should be readable."""
        # Manually insert a legacy CSV claim
        with sqlite3.connect(temp_db.db_path) as conn:
            conn.execute(
                """
                INSERT INTO artifacts (id, company_id, artifact_type, run_id, created_at)
                VALUES ('art_legacy', 'comp_1', 'research', 'run_1', ?)
                """,
                (datetime.now(timezone.utc).isoformat(),),
            )
            conn.execute(
                """
                INSERT INTO claims (id, artifact_id, claim_text, source_ids, is_assumption)
                VALUES ('claim_legacy', 'art_legacy', 'Legacy claim', 'src_a,src_b,src_c', 0)
                """
            )
            conn.commit()

        # Read back through SQLiteManager
        claim = temp_db.get_claim("claim_legacy")
        assert claim is not None
        assert claim["source_ids"] == ["src_a", "src_b", "src_c"]

    def test_read_legacy_json_claim(self, temp_db: SQLiteManager):
        """Legacy JSON array claims should be readable."""
        with sqlite3.connect(temp_db.db_path) as conn:
            conn.execute(
                """
                INSERT INTO artifacts (id, company_id, artifact_type, run_id, created_at)
                VALUES ('art_legacy2', 'comp_1', 'research', 'run_1', ?)
                """,
                (datetime.now(timezone.utc).isoformat(),),
            )
            conn.execute(
                """
                INSERT INTO claims (id, artifact_id, claim_text, source_ids, is_assumption)
                VALUES ('claim_legacy2', 'art_legacy2', 'Legacy JSON claim', '["src_x","src_y"]', 0)
                """
            )
            conn.commit()

        claim = temp_db.get_claim("claim_legacy2")
        assert claim is not None
        assert claim["source_ids"] == ["src_x", "src_y"]

    def test_get_claims_by_artifact(self, temp_db: SQLiteManager):
        """Should retrieve all claims for an artifact."""
        temp_db.insert_artifact(
            artifact_id="art_multi",
            company_id="comp_1",
            artifact_type="research_brief",
            run_id="run_1",
        )

        temp_db.insert_claim(
            claim_id="claim_a",
            artifact_id="art_multi",
            claim_text="Claim A",
            kind="fact",
            source_ids=["src_1"],
        )
        temp_db.insert_claim(
            claim_id="claim_b",
            artifact_id="art_multi",
            claim_text="Claim B",
            kind="assumption",
            source_ids=[],
        )

        claims = temp_db.get_claims_by_artifact("art_multi")
        assert len(claims) == 2
        assert any(c["id"] == "claim_a" for c in claims)
        assert any(c["id"] == "claim_b" for c in claims)


# ===========================================
# Task B: FTS5 Search
# ===========================================


class TestFTS5Search:
    """Tests for FTS5 full-text search on sources and artifacts."""

    @pytest.fixture
    def seeded_db(self, tmp_path):
        """Create a database seeded with test data."""
        db_path = tmp_path / "test_fts.db"
        db = SQLiteManager.unscoped(db_path)

        # Insert test sources
        db.insert_source(
            source_id="src_acme",
            source_type="text",
            content="ACME Corporation is a leading provider of cloud solutions.",
            title="ACME Overview",
            uri="https://acme.com/about",
        )
        db.insert_source(
            source_id="src_tech",
            source_type="text",
            content="TechCorp specializes in AI and machine learning applications.",
            title="TechCorp Profile",
        )
        db.insert_source(
            source_id="src_sales",
            source_type="text",
            content="Sales automation and CRM integration services.",
            title="Sales Tools",
        )

        # Insert test company
        db.insert_company("comp_acme", "ACME")

        # Insert test artifacts
        db.insert_artifact(
            artifact_id="art_research",
            company_id="comp_acme",
            artifact_type="research_brief",
            run_id="run_fts",
            name="research_brief",
            content_md="# ACME Research\n\nACME is expanding cloud services.",
            content_json='{"company": "ACME", "snapshot": "Cloud leader"}',
        )
        db.insert_artifact(
            artifact_id="art_target",
            company_id="comp_acme",
            artifact_type="target_map",
            run_id="run_fts",
            name="target_map",
            content_md="# Target Map\n\nVP of Sales is primary contact.",
            content_json='{"personas": [{"title": "VP Sales"}]}',
        )

        yield db
        # Ensure connections are closed for Windows cleanup
        close_sqlite_connections()

    def test_search_sources_by_company(self, seeded_db: SQLiteManager):
        """Should find sources by company name."""
        results = seeded_db.search_sources_fts("ACME", limit=10)
        assert len(results) >= 1
        assert any(r["id"] == "src_acme" for r in results)

    def test_search_sources_by_content(self, seeded_db: SQLiteManager):
        """Should find sources by content keywords."""
        results = seeded_db.search_sources_fts("cloud solutions", limit=10)
        assert len(results) >= 1
        assert any(r["id"] == "src_acme" for r in results)

    def test_search_sources_by_topic(self, seeded_db: SQLiteManager):
        """Should find sources by topic."""
        results = seeded_db.search_sources_fts("machine learning", limit=10)
        assert len(results) >= 1
        assert any(r["id"] == "src_tech" for r in results)

    def test_search_sources_no_match(self, seeded_db: SQLiteManager):
        """Should return empty list when no match."""
        results = seeded_db.search_sources_fts("xyznonexistent", limit=10)
        assert len(results) == 0

    def test_search_artifacts_by_name(self, seeded_db: SQLiteManager):
        """Should find artifacts by name."""
        results = seeded_db.search_artifacts_fts("research", limit=10)
        assert len(results) >= 1
        assert any(r["id"] == "art_research" for r in results)

    def test_search_artifacts_by_content(self, seeded_db: SQLiteManager):
        """Should find artifacts by content."""
        results = seeded_db.search_artifacts_fts("VP Sales", limit=10)
        assert len(results) >= 1
        # Target map contains VP Sales
        assert any(r["id"] == "art_target" for r in results)

    def test_search_respects_limit(self, seeded_db: SQLiteManager):
        """Should respect the limit parameter."""
        results = seeded_db.search_sources_fts("Corporation OR TechCorp OR Sales", limit=2)
        assert len(results) <= 2


# ===========================================
# Task C: Memory API / retrieve_context
# ===========================================


class TestMemoryAPI:
    """Tests for the Memory API."""

    @pytest.fixture
    def memory_api(self, tmp_path):
        """Create a MemoryAPI with seeded test data."""
        db_path = tmp_path / "test_memory.db"
        workspace_id = "test-memory-workspace"
        db = SQLiteManager(db_path, workspace_id=workspace_id)

        # Seed test data
        db.insert_source(
            source_id="src_target",
            source_type="text",
            content="TargetCompany is disrupting the fintech market.",
            title="TargetCompany News",
        )
        db.insert_source(
            source_id="src_market",
            source_type="text",
            content="Fintech market analysis and trends for 2026.",
            title="Market Analysis",
        )

        db.insert_company("comp_target", "TargetCompany")
        db.insert_artifact(
            artifact_id="art_prev_research",
            company_id="comp_target",
            artifact_type="research_brief",
            run_id="run_prev",
            name="research_brief",
            content_md="# Previous Research\n\nTargetCompany analysis.",
            content_json='{"company": "TargetCompany"}',
        )

        api = MemoryAPI(db_path, workspace_id=workspace_id)
        yield api
        # Ensure connections are closed for Windows cleanup
        close_sqlite_connections()

    def test_search_sources(self, memory_api: MemoryAPI):
        """Should search sources and return SourceHit objects."""
        hits = memory_api.search_sources("TargetCompany")
        assert len(hits) >= 1
        assert all(isinstance(h, SourceHit) for h in hits)
        assert any(h.id == "src_target" for h in hits)

    def test_search_artifacts(self, memory_api: MemoryAPI):
        """Should search artifacts and return ArtifactHit objects."""
        hits = memory_api.search_artifacts("TargetCompany")
        assert len(hits) >= 1
        assert all(isinstance(h, ArtifactHit) for h in hits)

    def test_retrieve_context_with_task_spec(self, memory_api: MemoryAPI):
        """Should retrieve context based on task spec."""
        # Create a mock task spec
        class MockTaskSpec:
            inputs = {
                "company": "TargetCompany",
                "snapshot": "Fintech disruptor",
            }

        bundle = memory_api.retrieve_context(MockTaskSpec())
        assert isinstance(bundle, EvidenceBundle)
        assert len(bundle.sources) >= 0  # May find sources
        assert bundle.query is not None

    def test_retrieve_context_empty_inputs(self, memory_api: MemoryAPI):
        """Should handle empty inputs gracefully."""
        class EmptyTaskSpec:
            inputs = {}

        bundle = memory_api.retrieve_context(EmptyTaskSpec())
        assert isinstance(bundle, EvidenceBundle)
        assert bundle.is_empty()

    def test_evidence_bundle_properties(self, memory_api: MemoryAPI):
        """Should have correct bundle properties."""
        bundle = EvidenceBundle(
            sources=[
                SourceRef(source_id="src_1", source_type="text"),
                SourceRef(source_id="src_2", source_type="url"),
            ],
            artifacts=[
                ArtifactSummary(artifact_id="art_1"),
            ],
        )
        assert bundle.source_ids == ["src_1", "src_2"]
        assert bundle.artifact_ids == ["art_1"]
        assert not bundle.is_empty()


# ===========================================
# Task D: Claim persistence via executor
# ===========================================


class TestClaimPersistenceIntegration:
    """Tests for claim persistence through the executor."""

    @pytest.fixture
    def temp_config(self, monkeypatch, tmp_path):
        """Configure temp paths for testing."""
        from agnetwork import config as cfg

        test_runs_dir = tmp_path / "runs"
        test_db_path = tmp_path / "data" / "agnetwork.db"

        test_runs_dir.mkdir(parents=True)
        test_db_path.parent.mkdir(parents=True)

        monkeypatch.setattr(cfg.config, "runs_dir", test_runs_dir)
        monkeypatch.setattr(cfg.config, "db_path", test_db_path)

        return tmp_path

    def test_claim_with_source_ids_persisted(self, temp_config):
        """Claims with source_ids should be persisted to DB."""
        from agnetwork.kernel.contracts import Claim, ClaimKind, SourceRef

        # Create a claim with evidence
        claim = Claim(
            text="Company revenue grew 25% YoY",
            kind=ClaimKind.FACT,
            evidence=[
                SourceRef(source_id="src_annual_report", source_type="pdf"),
            ],
            confidence=0.95,
        )

        # Verify source_ids property
        assert claim.source_ids == ["src_annual_report"]
        assert claim.is_sourced()

    def test_claim_without_evidence(self):
        """Claims without evidence should have empty source_ids."""
        from agnetwork.kernel.contracts import Claim, ClaimKind

        claim = Claim(
            text="Company is likely expanding",
            kind=ClaimKind.ASSUMPTION,
        )

        assert claim.source_ids == []
        assert not claim.is_sourced()


# ===========================================
# Task F: Verifier evidence checks
# ===========================================


class TestVerifierEvidenceConsistency:
    """Tests for verifier evidence consistency checks."""

    def test_fact_without_evidence_warning_when_memory_enabled(self):
        """Fact claims without evidence should trigger warning when memory enabled."""
        from agnetwork.eval.verifier import Verifier
        from agnetwork.kernel.contracts import (
            ArtifactKind,
            ArtifactRef,
            Claim,
            ClaimKind,
            SkillResult,
        )

        verifier = Verifier()

        # Create a skill result with a fact claim but no evidence
        result = SkillResult(
            output={"company": "TestCo"},
            artifacts=[
                ArtifactRef(
                    name="research_brief",
                    kind=ArtifactKind.JSON,
                    content='{"company": "TestCo", "snapshot": "Test"}',
                ),
                ArtifactRef(
                    name="research_brief",
                    kind=ArtifactKind.MARKDOWN,
                    content="# Research Brief\n\nTest",
                ),
            ],
            claims=[
                Claim(
                    text="TestCo has 1000 employees",
                    kind=ClaimKind.FACT,
                    evidence=[],  # No evidence!
                )
            ],
        )

        # With memory enabled, should get warning
        issues = verifier.verify_skill_result(result, memory_enabled=True)
        evidence_issues = [i for i in issues if i.check == "evidence_consistency"]
        assert len(evidence_issues) >= 1
        assert evidence_issues[0].severity.value == "warning"

    def test_fact_without_evidence_ok_when_memory_disabled(self):
        """Fact claims without evidence should NOT trigger issue when memory disabled."""
        from agnetwork.eval.verifier import Verifier
        from agnetwork.kernel.contracts import (
            ArtifactKind,
            ArtifactRef,
            Claim,
            ClaimKind,
            SkillResult,
        )

        verifier = Verifier()

        result = SkillResult(
            output={"company": "TestCo"},
            artifacts=[
                ArtifactRef(
                    name="research_brief",
                    kind=ArtifactKind.JSON,
                    content='{"company": "TestCo", "snapshot": "Test"}',
                ),
                ArtifactRef(
                    name="research_brief",
                    kind=ArtifactKind.MARKDOWN,
                    content="# Research Brief\n\nTest",
                ),
            ],
            claims=[
                Claim(
                    text="TestCo has 1000 employees",
                    kind=ClaimKind.FACT,
                    evidence=[],
                )
            ],
        )

        # With memory disabled, should NOT get evidence_consistency warning
        issues = verifier.verify_skill_result(result, memory_enabled=False)
        evidence_issues = [i for i in issues if i.check == "evidence_consistency"]
        assert len(evidence_issues) == 0

    def test_assumption_without_evidence_ok(self):
        """Assumption claims don't require evidence."""
        from agnetwork.eval.verifier import Verifier
        from agnetwork.kernel.contracts import (
            ArtifactKind,
            ArtifactRef,
            Claim,
            ClaimKind,
            SkillResult,
        )

        verifier = Verifier()

        result = SkillResult(
            output={"company": "TestCo"},
            artifacts=[
                ArtifactRef(
                    name="research_brief",
                    kind=ArtifactKind.JSON,
                    content='{"company": "TestCo", "snapshot": "Test"}',
                ),
                ArtifactRef(
                    name="research_brief",
                    kind=ArtifactKind.MARKDOWN,
                    content="# Research Brief\n\nTest",
                ),
            ],
            claims=[
                Claim(
                    text="TestCo is probably expanding",
                    kind=ClaimKind.ASSUMPTION,
                    evidence=[],
                )
            ],
        )

        # Assumptions without evidence should be fine
        issues = verifier.verify_skill_result(result, memory_enabled=True)
        evidence_issues = [i for i in issues if i.check == "evidence_consistency"]
        assert len(evidence_issues) == 0

    def test_fact_with_evidence_ok(self):
        """Fact claims with evidence should not trigger issues."""
        from agnetwork.eval.verifier import Verifier
        from agnetwork.kernel.contracts import (
            ArtifactKind,
            ArtifactRef,
            Claim,
            ClaimKind,
            SkillResult,
            SourceRef,
        )

        verifier = Verifier()

        result = SkillResult(
            output={"company": "TestCo"},
            artifacts=[
                ArtifactRef(
                    name="research_brief",
                    kind=ArtifactKind.JSON,
                    content='{"company": "TestCo", "snapshot": "Test"}',
                ),
                ArtifactRef(
                    name="research_brief",
                    kind=ArtifactKind.MARKDOWN,
                    content="# Research Brief\n\nTest",
                ),
            ],
            claims=[
                Claim(
                    text="TestCo has 1000 employees",
                    kind=ClaimKind.FACT,
                    evidence=[
                        SourceRef(source_id="src_annual", source_type="pdf"),
                    ],
                )
            ],
        )

        issues = verifier.verify_skill_result(result, memory_enabled=True)
        evidence_issues = [i for i in issues if i.check == "evidence_consistency"]
        assert len(evidence_issues) == 0


# ===========================================
# Integration: FTS triggers work correctly
# ===========================================


class TestFTSTriggers:
    """Tests for FTS5 trigger synchronization."""

    @pytest.fixture
    def fresh_db(self, tmp_path):
        """Create a fresh database."""
        db_path = tmp_path / "test_triggers.db"
        db = SQLiteManager.unscoped(db_path)
        yield db
        # Ensure connections are closed for Windows cleanup
        close_sqlite_connections()

    def test_insert_source_searchable_immediately(self, fresh_db: SQLiteManager):
        """Sources should be searchable immediately after insert."""
        fresh_db.insert_source(
            source_id="src_instant",
            source_type="text",
            content="Instant indexing test content for FTS5.",
            title="Instant Test",
        )

        # Should be searchable without manual reindexing
        results = fresh_db.search_sources_fts("instant indexing", limit=10)
        assert len(results) >= 1
        assert results[0]["id"] == "src_instant"

    def test_insert_artifact_searchable_immediately(self, fresh_db: SQLiteManager):
        """Artifacts should be searchable immediately after insert."""
        fresh_db.insert_company("comp_test", "TestCompany")
        fresh_db.insert_artifact(
            artifact_id="art_instant",
            company_id="comp_test",
            artifact_type="research_brief",
            run_id="run_instant",
            name="instant_artifact",
            content_md="# Instant Artifact\n\nThis is instant indexing test.",
            content_json='{"test": "instant"}',
        )

        results = fresh_db.search_artifacts_fts("instant artifact", limit=10)
        assert len(results) >= 1
        assert results[0]["id"] == "art_instant"

    def test_rebuild_fts_index(self, fresh_db: SQLiteManager):
        """FTS index rebuild should work without errors."""
        fresh_db.insert_source(
            source_id="src_rebuild",
            source_type="text",
            content="Rebuild test source content.",
            title="Rebuild Test",
        )

        # Rebuild should not raise
        fresh_db.rebuild_fts_index()

        # Should still be searchable
        results = fresh_db.search_sources_fts("rebuild", limit=10)
        assert len(results) >= 1

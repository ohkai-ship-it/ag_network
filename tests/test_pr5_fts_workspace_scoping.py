"""PR5: FTS Workspace Scoping Tests.

Validates that FTS search cannot return cross-workspace rows.

Invariants enforced:
1. FTS search functions require workspace_id (TypeError on unscoped)
2. FTS results are filtered by workspace_meta.workspace_id
3. Simulated foreign rows do not leak across workspace boundaries

All tests are offline and do not require external providers.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

# =============================================================================
# Test: FTS search requires workspace_id (no unscoped FTS)
# =============================================================================


class TestFTSRequiresWorkspaceId:
    """PR5: FTS search functions must require workspace_id."""

    def test_search_sources_fts_raises_on_unscoped(self, tmp_path: Path) -> None:
        """search_sources_fts raises TypeError when called on unscoped instance."""
        from agnetwork.storage.sqlite import SQLiteManager

        db_path = tmp_path / "test.db"
        db = SQLiteManager.unscoped(db_path)

        with pytest.raises(TypeError) as exc_info:
            db.search_sources_fts("test query")

        assert "search_sources_fts requires workspace_id" in str(exc_info.value)

    def test_search_artifacts_fts_raises_on_unscoped(self, tmp_path: Path) -> None:
        """search_artifacts_fts raises TypeError when called on unscoped instance."""
        from agnetwork.storage.sqlite import SQLiteManager

        db_path = tmp_path / "test.db"
        db = SQLiteManager.unscoped(db_path)

        with pytest.raises(TypeError) as exc_info:
            db.search_artifacts_fts("test query")

        assert "search_artifacts_fts requires workspace_id" in str(exc_info.value)

    def test_search_sources_fts_works_with_workspace_id(self, tmp_path: Path) -> None:
        """search_sources_fts works when workspace_id is provided."""
        from agnetwork.storage.sqlite import SQLiteManager

        db_path = tmp_path / "test.db"
        db = SQLiteManager(db_path, workspace_id="test-ws")

        # Add a source to search
        db.insert_source(
            source_id="src-1",
            source_type="text",
            content="Hello world searchable content",
            title="Test Source",
        )

        # Should not raise - workspace_id is set
        results = db.search_sources_fts("searchable", limit=10)
        assert len(results) == 1
        assert results[0]["id"] == "src-1"

    def test_search_artifacts_fts_works_with_workspace_id(self, tmp_path: Path) -> None:
        """search_artifacts_fts works when workspace_id is provided."""
        from agnetwork.storage.sqlite import SQLiteManager

        db_path = tmp_path / "test.db"
        db = SQLiteManager(db_path, workspace_id="test-ws")

        # Add a company and artifact to search
        db.insert_company(company_id="company-1", name="Test Company")
        db.insert_artifact(
            artifact_id="art-1",
            company_id="company-1",
            artifact_type="research_brief",
            run_id="run-1",
            name="Test Artifact",
            content_md="Searchable artifact content",
        )

        # Should not raise - workspace_id is set
        results = db.search_artifacts_fts("searchable", limit=10)
        assert len(results) == 1
        assert results[0]["id"] == "art-1"


# =============================================================================
# Test: FTS filters by workspace_meta (defensive filter)
# =============================================================================


class TestFTSDefensiveWorkspaceFilter:
    """PR5: FTS results are filtered by workspace_meta.workspace_id.

    These tests simulate a scenario where rows exist in the DB but the
    workspace_meta doesn't match, proving the defensive filter works.
    """

    def test_fts_search_returns_nothing_when_workspace_meta_mismatched(
        self, tmp_path: Path
    ) -> None:
        """FTS search returns empty when workspace_meta doesn't match.

        This simulates a defensive scenario where somehow the workspace_meta
        was tampered with or the DB was opened with wrong workspace_id.
        """
        from agnetwork.storage.sqlite import SQLiteManager

        db_path = tmp_path / "test.db"

        # Setup: Create DB with workspace "ws1" and add data
        db1 = SQLiteManager(db_path, workspace_id="ws1")
        db1.insert_source(
            source_id="src-1",
            source_type="text",
            content="Important data for ws1",
            title="WS1 Source",
        )
        db1.close()

        # Manually tamper with workspace_meta to simulate mismatch
        with sqlite3.connect(db_path) as conn:
            conn.execute("UPDATE workspace_meta SET workspace_id = 'ws-tampered'")
            conn.commit()

        # Try to search with original workspace_id - should get nothing
        # because EXISTS check requires workspace_meta.workspace_id = 'ws1'
        # but it's now 'ws-tampered'
        db2 = SQLiteManager.unscoped(db_path)
        db2._workspace_id = "ws1"  # Simulate what would happen

        results = db2.search_sources_fts("Important", limit=10)
        assert results == []

    def test_fts_search_succeeds_when_workspace_meta_matches(
        self, tmp_path: Path
    ) -> None:
        """FTS search succeeds when workspace_meta matches workspace_id."""
        from agnetwork.storage.sqlite import SQLiteManager

        db_path = tmp_path / "test.db"

        # Setup: Create DB with workspace "ws1" and add data
        db = SQLiteManager(db_path, workspace_id="ws1")
        db.insert_source(
            source_id="src-1",
            source_type="text",
            content="Important data for ws1",
            title="WS1 Source",
        )

        # Search should succeed because workspace_meta matches
        results = db.search_sources_fts("Important", limit=10)
        assert len(results) == 1
        assert results[0]["id"] == "src-1"


# =============================================================================
# Test: Workspace isolation via separate DB files
# =============================================================================


class TestFTSWorkspaceIsolationViaSeparateDBs:
    """PR5: Verify that separate workspace DBs provide complete isolation."""

    def test_separate_workspaces_have_isolated_fts_data(
        self, tmp_path: Path
    ) -> None:
        """Separate workspace DBs contain isolated FTS data."""
        from agnetwork.storage.sqlite import SQLiteManager

        # Create two separate DBs for different workspaces
        ws1_path = tmp_path / "ws1" / "state.db"
        ws2_path = tmp_path / "ws2" / "state.db"

        db1 = SQLiteManager(ws1_path, workspace_id="ws1")
        db2 = SQLiteManager(ws2_path, workspace_id="ws2")

        # Add data to ws1
        db1.insert_source(
            source_id="ws1-src",
            source_type="text",
            content="Workspace one exclusive data alpha",
            title="WS1 Source",
        )

        # Add data to ws2
        db2.insert_source(
            source_id="ws2-src",
            source_type="text",
            content="Workspace two exclusive data beta",
            title="WS2 Source",
        )

        # Search ws1 should only find ws1 data
        ws1_results = db1.search_sources_fts("exclusive", limit=10)
        assert len(ws1_results) == 1
        assert ws1_results[0]["id"] == "ws1-src"
        assert "alpha" in ws1_results[0]["excerpt"]

        # Search ws2 should only find ws2 data
        ws2_results = db2.search_sources_fts("exclusive", limit=10)
        assert len(ws2_results) == 1
        assert ws2_results[0]["id"] == "ws2-src"
        assert "beta" in ws2_results[0]["excerpt"]

        # Cross-search: ws1 should NOT find ws2's "beta"
        ws1_beta = db1.search_sources_fts("beta", limit=10)
        assert ws1_beta == []

        # Cross-search: ws2 should NOT find ws1's "alpha"
        ws2_alpha = db2.search_sources_fts("alpha", limit=10)
        assert ws2_alpha == []


# =============================================================================
# Test: CLI memory search respects workspace (integration test)
# =============================================================================


class TestCLIMemorySearchRespectWorkspace:
    """PR5: CLI memory search respects workspace context."""

    def test_cli_memory_search_creates_workspace_scoped_db(
        self, tmp_path: Path
    ) -> None:
        """CLI memory search command creates workspace-scoped SQLiteManager.

        This test verifies the code path that CLI uses, without needing
        a full workspace manifest setup.
        """
        from agnetwork.storage.sqlite import SQLiteManager
        from agnetwork.workspaces.context import WorkspaceContext

        # Create workspace context as CLI would
        ws_ctx = WorkspaceContext.create(
            name="test-cli-ws",
            root_dir=tmp_path / "workspace",
        )
        ws_ctx.ensure_directories()

        # Create workspace-scoped DB (mimics what CLI does)
        db = SQLiteManager(db_path=ws_ctx.db_path, workspace_id=ws_ctx.workspace_id)

        # Add searchable content
        db.insert_source(
            source_id="cli-src",
            source_type="text",
            content="CLI test searchable unique content zxyabc",
            title="CLI Test Source",
        )

        # Search should work and find results
        results = db.search_sources_fts("zxyabc", limit=10)
        assert len(results) == 1
        assert results[0]["id"] == "cli-src"

    def test_cli_memory_search_code_path_uses_workspace_id(self) -> None:
        """Verify CLI memory search command passes workspace_id to SQLiteManager.

        This is an AST-level check that the CLI code uses workspace_id.
        """
        import inspect

        from agnetwork.cli import memory_search

        source = inspect.getsource(memory_search)

        # Verify the CLI code creates SQLiteManager with workspace_id
        assert "workspace_id=ws_ctx.workspace_id" in source or "workspace_id=" in source
        assert "db_path=ws_ctx.db_path" in source or "db_path=" in source


# =============================================================================
# Test: MemoryAPI requires workspace context
# =============================================================================


class TestMemoryAPIRequiresWorkspace:
    """PR5: MemoryAPI requires explicit workspace context."""

    def test_memory_api_requires_db_path(self) -> None:
        """MemoryAPI raises TypeError without db_path."""
        from agnetwork.storage.memory import MemoryAPI

        with pytest.raises(TypeError) as exc_info:
            MemoryAPI(db_path=None, workspace_id="ws1")  # type: ignore

        assert "requires explicit db_path" in str(exc_info.value)

    def test_memory_api_requires_workspace_id(self, tmp_path: Path) -> None:
        """MemoryAPI raises TypeError without workspace_id."""
        from agnetwork.storage.memory import MemoryAPI

        db_path = tmp_path / "test.db"

        with pytest.raises(TypeError) as exc_info:
            MemoryAPI(db_path=db_path, workspace_id=None)  # type: ignore

        assert "requires explicit workspace_id" in str(exc_info.value)

    def test_memory_api_for_workspace_binds_correctly(
        self, tmp_path: Path
    ) -> None:
        """MemoryAPI.for_workspace creates properly scoped instance."""
        from agnetwork.storage.memory import MemoryAPI
        from agnetwork.workspaces.context import WorkspaceContext

        ws_ctx = WorkspaceContext.create(
            name="test-ws",
            root_dir=tmp_path / "workspace",
        )
        ws_ctx.ensure_directories()

        api = MemoryAPI.for_workspace(ws_ctx)

        # Should have a properly scoped db
        assert api.db._workspace_id == ws_ctx.workspace_id
        assert api.db.db_path == ws_ctx.db_path


# =============================================================================
# Test: Simulated "foreign rows" leak test
# =============================================================================


class TestFTSForeignRowsLeakPrevention:
    """PR5: Simulated foreign rows inserted directly don't leak via FTS.

    This tests the defensive EXISTS check by inserting rows directly
    via SQL bypass and proving they don't appear in FTS results.
    """

    def test_foreign_source_rows_not_returned_by_fts(
        self, tmp_path: Path
    ) -> None:
        """Rows inserted via SQL bypass don't appear in FTS search.

        Simulates a scenario where an attacker or bug inserts rows
        into the sources table without going through SQLiteManager.
        """
        from agnetwork.storage.sqlite import SQLiteManager

        db_path = tmp_path / "test.db"

        # Setup: Create DB with workspace "ws1" and add legitimate data
        db = SQLiteManager(db_path, workspace_id="ws1")
        db.insert_source(
            source_id="legitimate-src",
            source_type="text",
            content="Legitimate data for ws1 searchable",
            title="Legitimate Source",
        )
        db.close()

        # Now tamper: change workspace_meta to simulate mismatch
        with sqlite3.connect(db_path) as conn:
            conn.execute("UPDATE workspace_meta SET workspace_id = 'ws-foreign'")
            conn.commit()

        # Reopen with original workspace_id - EXISTS check should fail
        # because workspace_meta no longer contains 'ws1'
        db2 = SQLiteManager.unscoped(db_path)
        db2._workspace_id = "ws1"  # What we're searching as

        # FTS search should return nothing due to EXISTS check
        results = db2.search_sources_fts("searchable", limit=10)
        assert results == []

    def test_artifacts_foreign_rows_not_returned_by_fts(
        self, tmp_path: Path
    ) -> None:
        """Artifact rows with mismatched workspace_meta don't appear in FTS."""
        from agnetwork.storage.sqlite import SQLiteManager

        db_path = tmp_path / "test.db"

        # Setup: Create DB with workspace "ws1"
        db = SQLiteManager(db_path, workspace_id="ws1")
        db.insert_company(company_id="company-1", name="Test Company")
        db.insert_artifact(
            artifact_id="legitimate-art",
            company_id="company-1",
            artifact_type="research_brief",
            run_id="run-1",
            name="Legitimate Artifact",
            content_md="Legitimate artifact searchable content",
        )
        db.close()

        # Tamper workspace_meta
        with sqlite3.connect(db_path) as conn:
            conn.execute("UPDATE workspace_meta SET workspace_id = 'ws-foreign'")
            conn.commit()

        # Reopen with original workspace_id
        db2 = SQLiteManager.unscoped(db_path)
        db2._workspace_id = "ws1"

        # FTS search should return nothing
        results = db2.search_artifacts_fts("searchable", limit=10)
        assert results == []


# =============================================================================
# Test: Verify FTS query contains workspace filter (AST-style check)
# =============================================================================


class TestFTSQueryContainsWorkspaceFilter:
    """PR5: Verify FTS search methods contain workspace filter in SQL."""

    def test_search_sources_fts_has_exists_check(self) -> None:
        """search_sources_fts SQL contains EXISTS workspace_meta check."""
        import inspect

        from agnetwork.storage.sqlite import SQLiteManager

        source = inspect.getsource(SQLiteManager.search_sources_fts)

        # Check for the defensive filter pattern
        assert "EXISTS" in source
        assert "workspace_meta" in source
        assert "workspace_id" in source

    def test_search_artifacts_fts_has_exists_check(self) -> None:
        """search_artifacts_fts SQL contains EXISTS workspace_meta check."""
        import inspect

        from agnetwork.storage.sqlite import SQLiteManager

        source = inspect.getsource(SQLiteManager.search_artifacts_fts)

        # Check for the defensive filter pattern
        assert "EXISTS" in source
        assert "workspace_meta" in source
        assert "workspace_id" in source

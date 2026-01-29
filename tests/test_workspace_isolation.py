"""Workspace isolation tests.

Tests that enforce workspace boundaries and prevent cross-workspace access.
"""

import json

import pytest

from agnetwork.orchestrator import RunManager
from agnetwork.storage.sqlite import SQLiteManager
from agnetwork.workspaces import (
    WorkspaceContext,
    WorkspaceMismatchError,
    WorkspaceRegistry,
)


@pytest.fixture
def temp_registry_root(tmp_path):
    """Create temporary registry root."""
    registry_root = tmp_path / "workspaces"
    registry_root.mkdir()
    return registry_root


@pytest.fixture
def registry(temp_registry_root):
    """Create workspace registry."""
    return WorkspaceRegistry(registry_root=temp_registry_root)


def create_test_workspace(registry: WorkspaceRegistry, name: str) -> WorkspaceContext:
    """Helper to create and initialize a test workspace.

    Args:
        registry: WorkspaceRegistry instance
        name: Workspace name

    Returns:
        Initialized WorkspaceContext
    """
    context = registry.create_workspace(name=name)
    context.ensure_directories()

    # Initialize database (use unscoped for initial setup, then init metadata)
    db = SQLiteManager.unscoped(db_path=context.db_path)
    db.init_workspace_metadata(context.workspace_id)
    db.close()

    return context


class TestWorkspaceIsolation:
    """Test suite for workspace isolation."""

    def test_runs_isolation(self, registry):
        """Test that runs are isolated to workspace."""
        # Create two workspaces
        alpha = create_test_workspace(registry, "alpha")
        beta = create_test_workspace(registry, "beta")

        # Run command in alpha
        run_alpha = RunManager(command="test", slug="company1", workspace=alpha)
        run_alpha.save_inputs({"test": "alpha_data"})

        # Verify alpha output exists
        assert run_alpha.run_dir.exists()
        assert run_alpha.run_dir.parent == alpha.runs_dir
        inputs_file = run_alpha.run_dir / "inputs.json"
        assert inputs_file.exists()

        # Verify beta runs dir is empty
        assert not any(beta.runs_dir.iterdir())

        # Run in beta
        run_beta = RunManager(command="test", slug="company2", workspace=beta)
        run_beta.save_inputs({"test": "beta_data"})

        # Verify both exist in their respective workspaces
        assert run_alpha.run_dir.parent == alpha.runs_dir
        assert run_beta.run_dir.parent == beta.runs_dir

        # Verify they're different
        assert run_alpha.run_dir != run_beta.run_dir

    def test_db_isolation(self, registry):
        """Test that databases are isolated."""
        # Create two workspaces
        alpha = create_test_workspace(registry, "alpha")
        beta = create_test_workspace(registry, "beta")

        # Add source to alpha (use for_workspace for proper isolation)
        db_alpha = SQLiteManager.for_workspace(alpha)
        db_alpha.insert_source(
            source_id="src_alpha_1",
            source_type="text",
            content="Alpha source content",
            title="Alpha Source",
        )
        db_alpha.close()

        # Verify beta DB is empty (no sources)
        db_beta = SQLiteManager.for_workspace(beta)
        sources = db_beta.get_sources()
        assert len(sources) == 0
        db_beta.close()

        # Verify alpha has the source
        db_alpha = SQLiteManager.for_workspace(alpha)
        sources = db_alpha.get_sources()
        assert len(sources) == 1
        assert sources[0]["id"] == "src_alpha_1"
        db_alpha.close()

    def test_fts_isolation(self, registry):
        """Test that FTS search is isolated."""
        # Create two workspaces
        alpha = create_test_workspace(registry, "alpha")
        beta = create_test_workspace(registry, "beta")

        # Add unique source to alpha (use for_workspace for proper isolation)
        db_alpha = SQLiteManager.for_workspace(alpha)
        db_alpha.insert_source(
            source_id="src_alpha_unique",
            source_type="text",
            content="This is a unique alpha source with searchable content",
            title="Unique Alpha",
        )

        # Search in alpha - should find it
        results = db_alpha.search_sources_fts("unique alpha")
        assert len(results) > 0
        db_alpha.close()

        # Search in beta - should be empty
        db_beta = SQLiteManager.for_workspace(beta)
        results = db_beta.search_sources_fts("unique alpha")
        assert len(results) == 0
        db_beta.close()

    def test_workspace_mismatch_guard(self, registry):
        """Test that workspace ID mismatch is detected."""
        # Create workspace
        alpha = create_test_workspace(registry, "alpha")
        beta = create_test_workspace(registry, "beta")

        # Try to open alpha DB with beta workspace ID - use unscoped to bypass
        # auto-verification, then manually verify with wrong ID to trigger error
        db = SQLiteManager.unscoped(db_path=alpha.db_path)

        with pytest.raises(WorkspaceMismatchError) as exc_info:
            db.verify_workspace_id(beta.workspace_id)

        assert alpha.workspace_id in str(exc_info.value)
        assert beta.workspace_id in str(exc_info.value)
        db.close()

    def test_workspace_mismatch_prevents_operations(self, registry):
        """Test that mismatched workspace prevents DB operations."""
        # Create workspaces
        alpha = create_test_workspace(registry, "alpha")
        beta = create_test_workspace(registry, "beta")

        # Initialize alpha DB properly
        db_alpha = SQLiteManager.for_workspace(alpha)
        db_alpha.insert_source(
            source_id="src_test",
            source_type="text",
            content="Test content",
        )
        db_alpha.close()

        # Now try to access alpha DB with beta context - use unscoped to
        # bypass auto-verification, then manually verify with wrong ID
        db = SQLiteManager.unscoped(db_path=alpha.db_path)

        # This should fail
        with pytest.raises(WorkspaceMismatchError):
            db.verify_workspace_id(beta.workspace_id)

        db.close()

    def test_exports_isolation(self, registry, tmp_path):
        """Test that exports are scoped to workspace."""
        # Create two workspaces
        alpha = create_test_workspace(registry, "alpha")
        beta = create_test_workspace(registry, "beta")

        # Create export in alpha
        export_file_alpha = alpha.exports_dir / "export_alpha.json"
        export_file_alpha.write_text(json.dumps({"workspace": "alpha"}))

        # Create export in beta
        export_file_beta = beta.exports_dir / "export_beta.json"
        export_file_beta.write_text(json.dumps({"workspace": "beta"}))

        # Verify isolation
        assert export_file_alpha.exists()
        assert export_file_beta.exists()
        assert export_file_alpha.parent == alpha.exports_dir
        assert export_file_beta.parent == beta.exports_dir
        assert alpha.exports_dir != beta.exports_dir

        # Verify contents
        alpha_data = json.loads(export_file_alpha.read_text())
        beta_data = json.loads(export_file_beta.read_text())
        assert alpha_data["workspace"] == "alpha"
        assert beta_data["workspace"] == "beta"

    def test_workspace_initialization(self, registry):
        """Test workspace creation and initialization."""
        # Create workspace
        context = registry.create_workspace("test_workspace")

        # Verify structure
        assert context.root_dir.exists()
        assert (context.root_dir / "workspace.toml").exists()

        # Initialize DB (use unscoped for initial setup)
        db = SQLiteManager.unscoped(db_path=context.db_path)
        db.init_workspace_metadata(context.workspace_id)

        # Verify workspace_meta exists
        ws_id = db.get_workspace_id()
        assert ws_id == context.workspace_id
        db.close()

    def test_cannot_reuse_workspace_name(self, registry):
        """Test that workspace names must be unique."""
        # Create first workspace
        registry.create_workspace("duplicate")

        # Try to create again - should fail
        with pytest.raises(ValueError, match="already exists"):
            registry.create_workspace("duplicate")

    def test_workspace_list(self, registry):
        """Test workspace listing."""
        # Create multiple workspaces
        registry.create_workspace("workspace1")
        registry.create_workspace("workspace2")
        registry.create_workspace("workspace3")

        # List workspaces
        workspaces = registry.list_workspaces()
        assert len(workspaces) == 3
        assert "workspace1" in workspaces
        assert "workspace2" in workspaces
        assert "workspace3" in workspaces

    def test_default_workspace(self, registry):
        """Test default workspace management."""
        # No default initially
        assert registry.get_default_workspace() is None

        # Create and set default
        registry.create_workspace("default_ws", set_as_default=True)
        assert registry.get_default_workspace() == "default_ws"

        # Change default
        registry.create_workspace("new_default")
        registry.set_default_workspace("new_default")
        assert registry.get_default_workspace() == "new_default"

    def test_workspace_doctor(self, registry):
        """Test workspace health checks."""
        # Create workspace
        context = create_test_workspace(registry, "health_check")

        # All paths should exist
        checks = context.verify_paths()
        assert all(checks.values())

        # Verify DB has correct workspace_id (use for_workspace for proper isolation)
        db = SQLiteManager.for_workspace(context)
        assert db.get_workspace_id() == context.workspace_id
        db.close()

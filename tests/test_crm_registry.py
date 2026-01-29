"""Tests for CRM adapter registry (M6.1 Task C).

Tests cover:
- CRMAdapterRegistry registration/lookup
- CRMAdapterFactory environment-based creation
- Factory pattern consistency
"""

import os
from unittest.mock import patch

import pytest

from agnetwork.crm.adapters import FileCRMAdapter
from agnetwork.crm.registry import (
    CRMAdapterFactory,
    CRMAdapterRegistry,
)


class TestCRMAdapterRegistry:
    """Tests for CRMAdapterRegistry."""

    def test_file_adapter_registered(self):
        """FileCRMAdapter is registered by default."""
        assert CRMAdapterRegistry.is_registered("file")

    def test_get_file_adapter(self):
        """Can retrieve FileCRMAdapter class."""
        cls = CRMAdapterRegistry.get("file")
        assert cls is FileCRMAdapter

    def test_get_case_insensitive(self):
        """get() is case-insensitive."""
        assert CRMAdapterRegistry.get("FILE") is FileCRMAdapter
        assert CRMAdapterRegistry.get("File") is FileCRMAdapter

    def test_get_unknown_returns_none(self):
        """get() returns None for unknown adapters."""
        assert CRMAdapterRegistry.get("nonexistent") is None

    def test_list_adapters(self):
        """list_adapters() returns registered names."""
        adapters = CRMAdapterRegistry.list_adapters()
        assert "file" in adapters

    def test_register_and_unregister(self):
        """Can register and unregister adapters."""
        # Create a dummy adapter class
        class TestAdapter:
            pass

        # Register
        CRMAdapterRegistry.register("test_temp", TestAdapter)
        assert CRMAdapterRegistry.is_registered("test_temp")
        assert CRMAdapterRegistry.get("test_temp") is TestAdapter

        # Unregister
        CRMAdapterRegistry.unregister("test_temp")
        assert not CRMAdapterRegistry.is_registered("test_temp")
        assert CRMAdapterRegistry.get("test_temp") is None


class TestCRMAdapterFactory:
    """Tests for CRMAdapterFactory."""

    def test_create_file_adapter(self, tmp_path):
        """create() instantiates FileCRMAdapter with workspace context."""
        from agnetwork.workspaces.context import WorkspaceContext

        ws_ctx = WorkspaceContext.create(name="test_ws", root_dir=tmp_path)
        ws_ctx.ensure_directories()
        adapter = CRMAdapterFactory.create("file", ws_ctx=ws_ctx)
        assert isinstance(adapter, FileCRMAdapter)

    def test_create_case_insensitive(self, tmp_path):
        """create() is case-insensitive."""
        from agnetwork.workspaces.context import WorkspaceContext

        ws_ctx = WorkspaceContext.create(name="test_ws", root_dir=tmp_path)
        ws_ctx.ensure_directories()
        adapter = CRMAdapterFactory.create("FILE", ws_ctx=ws_ctx)
        assert isinstance(adapter, FileCRMAdapter)

    def test_create_unknown_raises(self):
        """create() raises ValueError for unknown adapter."""
        with pytest.raises(ValueError, match="Unknown CRM adapter"):
            CRMAdapterFactory.create("nonexistent")

    def test_create_file_requires_workspace_context(self):
        """create('file') without workspace context raises TypeError."""
        with pytest.raises(TypeError, match="requires workspace context"):
            CRMAdapterFactory.create("file")

    def test_from_env_requires_path_and_workspace_id(self):
        """from_env() for file adapter requires AG_CRM_PATH and AG_CRM_WORKSPACE_ID."""
        with patch.dict(os.environ, {}, clear=True):
            # Without AG_CRM_PATH and AG_CRM_WORKSPACE_ID, should raise
            with pytest.raises(TypeError, match="Dev-only"):
                CRMAdapterFactory.from_env()

    def test_from_env_rejects_file_path(self, tmp_path):
        """from_env() rejects AG_CRM_PATH that points to a file."""
        # Create a file (not a directory)
        file_path = tmp_path / "crm.db"
        file_path.touch()

        with patch.dict(os.environ, {
            "AG_CRM_ADAPTER": "file",
            "AG_CRM_PATH": str(file_path),
            "AG_CRM_WORKSPACE_ID": "test-workspace",
        }):
            with pytest.raises(TypeError, match="must be a directory"):
                CRMAdapterFactory.from_env()

    def test_from_env_accepts_directory(self, tmp_path):
        """from_env() with AG_CRM_PATH + AG_CRM_WORKSPACE_ID creates file adapter."""
        exports_dir = tmp_path / "exports"
        exports_dir.mkdir()

        with patch.dict(os.environ, {
            "AG_CRM_ADAPTER": "file",
            "AG_CRM_PATH": str(exports_dir),
            "AG_CRM_WORKSPACE_ID": "test-workspace",
        }):
            adapter = CRMAdapterFactory.from_env()
            assert isinstance(adapter, FileCRMAdapter)
            # Storage db should be inside the exports dir
            assert adapter.storage.db_path == exports_dir / "crm.db"

    def test_from_env_creates_directory_if_missing(self, tmp_path):
        """from_env() creates AG_CRM_PATH directory if it doesn't exist."""
        exports_dir = tmp_path / "new_exports"
        assert not exports_dir.exists()

        with patch.dict(os.environ, {
            "AG_CRM_ADAPTER": "file",
            "AG_CRM_PATH": str(exports_dir),
            "AG_CRM_WORKSPACE_ID": "test-workspace",
        }):
            adapter = CRMAdapterFactory.from_env()
            assert isinstance(adapter, FileCRMAdapter)
            assert exports_dir.exists()

    def test_from_env_unknown_raises(self):
        """from_env() raises for unknown adapter type."""
        with patch.dict(os.environ, {
            "AG_CRM_ADAPTER": "unknown_adapter",
        }):
            with pytest.raises(ValueError, match="Unknown CRM adapter"):
                CRMAdapterFactory.from_env()


class TestFactoryIntegration:
    """Integration tests for factory pattern."""

    def test_factory_creates_working_adapter(self, tmp_path):
        """Factory-created adapter is fully functional."""
        from agnetwork.workspaces.context import WorkspaceContext

        ws_ctx = WorkspaceContext.create(name="test_ws", root_dir=tmp_path)
        ws_ctx.ensure_directories()
        adapter = CRMAdapterFactory.create("file", ws_ctx=ws_ctx)

        # Should be able to use the adapter
        # (basic operation - specific tests in test_crm_adapters.py)
        assert adapter is not None
        assert hasattr(adapter, "export_data")

    def test_multiple_factory_calls_independent(self, tmp_path):
        """Multiple factory calls create independent adapters."""
        from agnetwork.workspaces.context import WorkspaceContext

        ws1 = WorkspaceContext.create(name="ws1", root_dir=tmp_path / "ws1")
        ws2 = WorkspaceContext.create(name="ws2", root_dir=tmp_path / "ws2")
        ws1.ensure_directories()
        ws2.ensure_directories()

        adapter1 = CRMAdapterFactory.create("file", ws_ctx=ws1)
        adapter2 = CRMAdapterFactory.create("file", ws_ctx=ws2)

        assert adapter1 is not adapter2

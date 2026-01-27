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
        """create() instantiates FileCRMAdapter."""
        adapter = CRMAdapterFactory.create("file", base_path=tmp_path)
        assert isinstance(adapter, FileCRMAdapter)

    def test_create_case_insensitive(self, tmp_path):
        """create() is case-insensitive."""
        adapter = CRMAdapterFactory.create("FILE", base_path=tmp_path)
        assert isinstance(adapter, FileCRMAdapter)

    def test_create_unknown_raises(self):
        """create() raises ValueError for unknown adapter."""
        with pytest.raises(ValueError, match="Unknown CRM adapter"):
            CRMAdapterFactory.create("nonexistent")

    def test_from_env_default(self, tmp_path):
        """from_env() defaults to file adapter."""
        # Clear any existing env vars
        with patch.dict(os.environ, {}, clear=True):
            # Set just the path
            os.environ["AG_CRM_PATH"] = str(tmp_path)

            adapter = CRMAdapterFactory.from_env()
            assert isinstance(adapter, FileCRMAdapter)

    def test_from_env_explicit_file(self, tmp_path):
        """from_env() respects AG_CRM_ADAPTER=file."""
        with patch.dict(os.environ, {
            "AG_CRM_ADAPTER": "file",
            "AG_CRM_PATH": str(tmp_path),
        }):
            adapter = CRMAdapterFactory.from_env()
            assert isinstance(adapter, FileCRMAdapter)

    def test_from_env_unknown_raises(self):
        """from_env() raises for unknown adapter type."""
        with patch.dict(os.environ, {
            "AG_CRM_ADAPTER": "unknown_adapter",
        }):
            with pytest.raises(ValueError, match="Unknown CRM adapter"):
                CRMAdapterFactory.from_env()

    def test_from_env_default_path(self, tmp_path, monkeypatch):
        """from_env() uses default path if AG_CRM_PATH not set."""
        # This tests that the factory handles missing path gracefully
        # The default path is in data/crm_exports/crm.db
        with patch.dict(os.environ, {"AG_CRM_ADAPTER": "file"}, clear=True):
            # Remove AG_CRM_PATH if it exists
            os.environ.pop("AG_CRM_PATH", None)

            # Should not raise, uses default path
            adapter = CRMAdapterFactory.from_env()
            assert isinstance(adapter, FileCRMAdapter)


class TestFactoryIntegration:
    """Integration tests for factory pattern."""

    def test_factory_creates_working_adapter(self, tmp_path):
        """Factory-created adapter is fully functional."""
        adapter = CRMAdapterFactory.create("file", base_path=tmp_path)

        # Should be able to use the adapter
        # (basic operation - specific tests in test_crm_adapters.py)
        assert adapter is not None
        assert hasattr(adapter, "export_data")

    def test_multiple_factory_calls_independent(self, tmp_path):
        """Multiple factory calls create independent adapters."""
        path1 = tmp_path / "crm1"
        path2 = tmp_path / "crm2"
        path1.mkdir()
        path2.mkdir()

        adapter1 = CRMAdapterFactory.create("file", base_path=path1)
        adapter2 = CRMAdapterFactory.create("file", base_path=path2)

        assert adapter1 is not adapter2

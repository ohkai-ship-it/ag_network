"""CRM Adapter Registry and Factory (M6.1).

Provides a config-driven registry for CRM adapters similar to the LLM factory pattern.

Usage:
    # Get adapter from environment
    adapter = CRMAdapterFactory.from_env()

    # Or explicit name
    adapter = CRMAdapterFactory.create("file")

Environment:
    AG_CRM_ADAPTER=file (default)
    AG_CRM_PATH=/path/to/exports (optional)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Dict, Optional, Type

if TYPE_CHECKING:
    from agnetwork.crm.adapters.base import BaseCRMAdapter, CRMAdapter


class CRMAdapterRegistryError(ValueError):
    """Error raised by the CRM adapter registry."""

    pass


class CRMAdapterRegistry:
    """Registry of available CRM adapters.

    Adapters register themselves at import time.
    New vendor adapters can be added by:
    1. Implementing BaseCRMAdapter
    2. Calling CRMAdapterRegistry.register("name", AdapterClass)

    M6.1: File adapter is registered by default.
    Future adapters (HubSpot, Salesforce, Pipedrive) register similarly.
    """

    _adapters: Dict[str, Type[BaseCRMAdapter]] = {}

    @classmethod
    def register(cls, name: str, adapter_class: Type[BaseCRMAdapter]) -> None:
        """Register an adapter class.

        Args:
            name: Adapter name (e.g., "file", "hubspot", "salesforce")
            adapter_class: Class implementing BaseCRMAdapter
        """
        cls._adapters[name.lower()] = adapter_class

    @classmethod
    def unregister(cls, name: str) -> None:
        """Unregister an adapter (mainly for testing).

        Args:
            name: Adapter name to remove
        """
        cls._adapters.pop(name.lower(), None)

    @classmethod
    def get(cls, name: str) -> Optional[Type[BaseCRMAdapter]]:
        """Get an adapter class by name.

        Args:
            name: Adapter name

        Returns:
            Adapter class or None if not found
        """
        return cls._adapters.get(name.lower())

    @classmethod
    def list_adapters(cls) -> list[str]:
        """List all registered adapter names.

        Returns:
            List of adapter names
        """
        return list(cls._adapters.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if an adapter is registered.

        Args:
            name: Adapter name

        Returns:
            True if registered
        """
        return name.lower() in cls._adapters


class CRMAdapterFactory:
    """Factory for creating CRM adapter instances from environment config.

    Similar to LLMFactory, this reads configuration from environment
    variables and creates the appropriate adapter.

    Environment Variables:
        AG_CRM_ADAPTER: Adapter name (default: "file")
        AG_CRM_PATH: Base path for file adapter exports (optional)
    """

    DEFAULT_ADAPTER = "file"

    @classmethod
    def from_env(cls, **kwargs: Any) -> "CRMAdapter":
        """Create an adapter instance from environment configuration.

        Args:
            **kwargs: Additional arguments passed to adapter constructor

        Returns:
            Configured CRMAdapter instance

        Raises:
            ValueError: If adapter not found
        """
        adapter_name = os.getenv("AG_CRM_ADAPTER", cls.DEFAULT_ADAPTER)
        return cls.create(adapter_name, **kwargs)

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> "CRMAdapter":
        """Create an adapter instance by name.

        Args:
            name: Adapter name
            **kwargs: Additional arguments passed to adapter constructor.
                For "file" adapter, if 'storage' is not provided,
                one will be created using base_path or AG_CRM_PATH.

        Returns:
            CRMAdapter instance

        Raises:
            ValueError: If adapter not found
        """
        from pathlib import Path

        from agnetwork.crm.storage import CRMStorage

        adapter_class = CRMAdapterRegistry.get(name)

        if adapter_class is None:
            available = CRMAdapterRegistry.list_adapters()
            raise ValueError(
                f"Unknown CRM adapter: '{name}'. Available: {available}"
            )

        # For file adapter, ensure storage is provided
        if name.lower() == "file" and "storage" not in kwargs:
            # Create storage from base_path or environment
            base_path = kwargs.get("base_path")
            if base_path is None:
                base_path = os.getenv("AG_CRM_PATH")
            if base_path is not None:
                db_path = Path(base_path) / "crm.db"
            else:
                # Use default path under data/crm_exports
                from agnetwork.config import config

                db_path = config.project_root / "data" / "crm_exports" / "crm.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            kwargs["storage"] = CRMStorage(db_path=db_path)

        return adapter_class(**kwargs)

    @classmethod
    def get_configured_adapter_name(cls) -> str:
        """Get the currently configured adapter name from environment.

        Returns:
            Adapter name string
        """
        return os.getenv("AG_CRM_ADAPTER", cls.DEFAULT_ADAPTER)


# =============================================================================
# Auto-register built-in adapters on import
# =============================================================================


def _register_builtin_adapters() -> None:
    """Register built-in adapters.

    Called at module import to ensure File adapter is always available.
    """
    from agnetwork.crm.adapters.file_adapter import FileCRMAdapter

    CRMAdapterRegistry.register("file", FileCRMAdapter)


# Register on import
_register_builtin_adapters()

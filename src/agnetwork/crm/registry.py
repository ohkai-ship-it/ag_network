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
        AG_CRM_PATH: Export/import DIRECTORY for file adapter (dev override only)
        AG_CRM_WORKSPACE_ID: Workspace ID for dev override (required with AG_CRM_PATH)
    """

    DEFAULT_ADAPTER = "file"

    @classmethod
    def from_env(cls, **kwargs: Any) -> "CRMAdapter":
        """Create an adapter instance from environment configuration.

        For file adapter, AG_CRM_PATH and AG_CRM_WORKSPACE_ID must be set.
        This is a dev-only override; stable deployments should use
        workspace-scoped CRM via ws_ctx.

        Args:
            **kwargs: Additional arguments passed to adapter constructor

        Returns:
            Configured CRMAdapter instance

        Raises:
            ValueError: If adapter not found
            TypeError: If file adapter and AG_CRM_PATH/AG_CRM_WORKSPACE_ID missing or invalid
        """
        import logging
        from pathlib import Path

        logger = logging.getLogger(__name__)
        adapter_name = os.getenv("AG_CRM_ADAPTER", cls.DEFAULT_ADAPTER)

        # For file adapter, enforce AG_CRM_PATH + AG_CRM_WORKSPACE_ID
        if adapter_name.lower() == "file" and "storage" not in kwargs and "ws_ctx" not in kwargs:
            env_path = os.getenv("AG_CRM_PATH")
            env_workspace_id = os.getenv("AG_CRM_WORKSPACE_ID")

            if not env_path or not env_workspace_id:
                raise TypeError(
                    "Dev-only: set AG_CRM_PATH (directory) AND AG_CRM_WORKSPACE_ID, "
                    "or use workspace-scoped CRM via ws_ctx. "
                    "Example: AG_CRM_PATH=/path/to/exports AG_CRM_WORKSPACE_ID=dev-workspace"
                )

            path = Path(env_path)

            # Check if path exists and is a file (not allowed)
            if path.exists() and path.is_file():
                raise TypeError(
                    f"AG_CRM_PATH must be a directory, not a file: {env_path}\n"
                    "Set AG_CRM_PATH to an export/import directory, "
                    "or use workspace-scoped CRM via ws_ctx."
                )

            # Log dev override warning
            logger.debug(
                "AG_CRM_PATH is a dev override; stable deployments should use "
                "workspace exports via ws_ctx."
            )

            # Pass as base_path (directory for exports) + workspace_id
            kwargs["base_path"] = path
            kwargs["workspace_id"] = env_workspace_id

        return cls.create(adapter_name, **kwargs)

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> "CRMAdapter":
        """Create an adapter instance by name.

        Args:
            name: Adapter name
            **kwargs: Additional arguments passed to adapter constructor.
                For "file" adapter, must provide one of:
                - storage: Pre-configured CRMStorage instance
                - ws_ctx: WorkspaceContext (creates workspace-scoped storage)
                - base_path + workspace_id: Directory for exports + workspace ID

        Returns:
            CRMAdapter instance

        Raises:
            ValueError: If adapter not found
            TypeError: If "file" adapter called without required workspace context
        """
        from pathlib import Path

        from agnetwork.crm.storage import CRMStorage

        adapter_class = CRMAdapterRegistry.get(name)

        if adapter_class is None:
            available = CRMAdapterRegistry.list_adapters()
            raise ValueError(f"Unknown CRM adapter: '{name}'. Available: {available}")

        # For file adapter, ensure storage is provided with workspace scope
        if name.lower() == "file" and "storage" not in kwargs:
            ws_ctx = kwargs.pop("ws_ctx", None)
            workspace_id = kwargs.pop("workspace_id", None)
            base_path = kwargs.get("base_path")  # Keep in kwargs for adapter

            if ws_ctx is not None:
                # Preferred: use workspace context
                kwargs["storage"] = CRMStorage.for_workspace(ws_ctx)
            elif base_path is not None and workspace_id is not None:
                # Dev override: AG_CRM_PATH directory + workspace_id
                base_path = Path(base_path)
                base_path.mkdir(parents=True, exist_ok=True)
                crm_db_path = base_path / "crm.db"
                kwargs["storage"] = CRMStorage(db_path=crm_db_path, workspace_id=workspace_id)
            elif base_path is not None:
                # base_path without workspace_id - fail
                raise TypeError(
                    "CRMAdapterFactory.create('file') with base_path requires workspace_id. "
                    "Pass workspace_id=..., or use ws_ctx=WorkspaceContext(...)."
                )
            else:
                # No workspace context - fail loudly
                raise TypeError(
                    "CRMAdapterFactory.create('file') requires workspace context. "
                    "Pass storage=CRMStorage(...), or ws_ctx=WorkspaceContext(...), "
                    "or base_path=Path(...) + workspace_id=str(...). "
                    "Global fallbacks are not allowed."
                )

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

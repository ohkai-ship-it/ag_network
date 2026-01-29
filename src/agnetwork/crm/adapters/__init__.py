"""CRM Adapters module.

Provides the adapter interface (Protocol) and reference implementations
for CRM data import/export.

M6: FileCRMAdapter is the reference implementation (CSV/JSON to local disk).
M6.1: CRMAdapterRegistry and CRMAdapterFactory for config-driven adapter selection.
Future adapters (HubSpot, Salesforce, etc.) plug in here.
"""

from agnetwork.crm.adapters.base import (
    CRMAdapter,
    CRMAdapterError,
    ExportResult,
    ImportResult,
    SideEffectCategory,
    requires_approval,
)
from agnetwork.crm.adapters.file_adapter import FileCRMAdapter


# Lazy import to avoid circular dependency
def __getattr__(name):
    """Lazy imports for registry components."""
    if name in ("CRMAdapterRegistry", "CRMAdapterFactory"):
        from agnetwork.crm.registry import CRMAdapterFactory, CRMAdapterRegistry

        if name == "CRMAdapterRegistry":
            return CRMAdapterRegistry
        return CRMAdapterFactory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CRMAdapter",
    "CRMAdapterError",
    "ExportResult",
    "ImportResult",
    "SideEffectCategory",
    "FileCRMAdapter",
    "requires_approval",
    "CRMAdapterRegistry",
    "CRMAdapterFactory",
]

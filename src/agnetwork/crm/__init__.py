"""CRM module for vendor-agnostic CRM integration.

This module provides:
- Canonical CRM domain models (Account, Contact, Activity)
- Deterministic ID generation (M6.1)
- CRM adapter interface (Protocol)
- FileCRMAdapter reference implementation
- Mapping layer to convert BD artifacts to CRM objects
- Export/import packages for CRM data

M6: CRM-neutral core with adapters pattern.
M6.1: Deterministic IDs, evidence scoping, registry factory.
No vendor-specific dependencies.
Export-only by default (no API writes).
"""

from agnetwork.crm.ids import (
    make_account_id,
    make_activity_id,
    make_contact_id,
)
from agnetwork.crm.models import (
    Account,
    Activity,
    ActivityDirection,
    ActivityType,
    Contact,
    ExternalRef,
)

__all__ = [
    "Account",
    "Contact",
    "Activity",
    "ActivityType",
    "ActivityDirection",
    "ExternalRef",
    "make_account_id",
    "make_contact_id",
    "make_activity_id",
]

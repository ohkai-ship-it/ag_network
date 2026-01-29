"""Approval gate infrastructure for side-effect operations.

This module provides the gating mechanism for operations that could
have external side effects (e.g., pushing data to external CRMs).

M6 Statuses:
- Infrastructure is in place
- No actual CRM writes are performed (export-only)
- FileCRMAdapter is exempt (local file writes only)

How to add a vendor adapter (e.g., HubSpot):

1. Create a new adapter file: agnetwork/crm/adapters/hubspot_adapter.py

2. Implement the CRMAdapter protocol:
   ```python
   from agnetwork.crm.adapters.base import (
       BaseCRMAdapter,
       AdapterRegistry,
       requires_approval,
       SideEffectCategory,
       ApprovalToken,
   )

   class HubSpotAdapter(BaseCRMAdapter):
       adapter_name = "hubspot"
       supports_push = True

       @requires_approval(SideEffectCategory.CRM_WRITE)
       def push_accounts(self, accounts, approval_token=None):
           # Token is validated by decorator
           # Safe to proceed with API call
           ...
   ```

3. Register the adapter:
   ```python
   AdapterRegistry.register("hubspot", HubSpotAdapter)
   ```

4. Use with approval token:
   ```python
   adapter = get_adapter("hubspot")
   token = create_approval_token("crm_write", granted_by="user")
   result = adapter.push_accounts(accounts, approval_token=token)
   ```

The approval gate makes it impossible to accidentally add push
operations without explicit authorization through the token mechanism.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from agnetwork.crm.adapters.base import (
    ApprovalRequiredError,
    ApprovalToken,
    SideEffectCategory,
)


def create_approval_token(
    side_effect: str,
    granted_by: str = "system",
    ttl_seconds: Optional[int] = 3600,
) -> ApprovalToken:
    """Create an approval token for a side-effect operation.

    Args:
        side_effect: Side effect category ("crm_read", "crm_write", "file_write")
        granted_by: Who/what granted this approval (user, system, test)
        ttl_seconds: Time-to-live in seconds. None for no expiration.

    Returns:
        ApprovalToken that can be passed to adapter methods

    Example:
        token = create_approval_token("crm_write", granted_by="user", ttl_seconds=300)
        adapter.push_accounts(accounts, approval_token=token)
    """
    expires_at = None
    if ttl_seconds is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

    return ApprovalToken(
        token_id=str(uuid.uuid4()),
        side_effect=SideEffectCategory(side_effect),
        granted_by=granted_by,
        granted_at=datetime.now(timezone.utc),
        expires_at=expires_at,
    )


def validate_approval_token(
    token: Optional[ApprovalToken],
    required_side_effect: SideEffectCategory,
    operation_name: str = "operation",
) -> bool:
    """Validate an approval token for a specific operation.

    Args:
        token: ApprovalToken to validate (can be None)
        required_side_effect: The side effect category required
        operation_name: Name of the operation (for error messages)

    Returns:
        True if valid

    Raises:
        ApprovalRequiredError: If token is missing, expired, or wrong type
    """
    if token is None:
        raise ApprovalRequiredError(operation_name, required_side_effect)

    if not token.is_valid():
        raise ApprovalRequiredError(f"{operation_name} (token expired)", required_side_effect)

    if token.side_effect != required_side_effect:
        raise ApprovalRequiredError(
            f"{operation_name} (wrong side effect: {token.side_effect.value})",
            required_side_effect,
        )

    return True


# Export for convenience
__all__ = [
    "ApprovalToken",
    "ApprovalRequiredError",
    "SideEffectCategory",
    "create_approval_token",
    "validate_approval_token",
]

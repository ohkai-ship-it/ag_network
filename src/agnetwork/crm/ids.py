"""Deterministic ID generation for CRM entities.

Provides stable, reproducible IDs based on natural keys:
- Accounts: domain (preferred) or name + location
- Contacts: email (preferred) or account_id + full_name + role_title
- Activities: run_id + artifact_ref + type or run_id + type + subject_hash

M6.1: IDs are deterministic to enable idempotent imports (dedupe).
Mapping the same run twice produces identical IDs.
"""

import hashlib
from typing import Optional


def _hash_components(*components: Optional[str], prefix: str, length: int = 12) -> str:
    """Create a deterministic hash from components.

    Args:
        *components: String components to hash (None values are skipped)
        prefix: ID prefix (e.g., "acc", "con", "act")
        length: Length of hash suffix (default 12 chars)

    Returns:
        Deterministic ID like "acc_a1b2c3d4e5f6"
    """
    # Filter out None and empty strings, normalize to lowercase
    normalized = [str(c).lower().strip() for c in components if c]

    if not normalized:
        raise ValueError("At least one non-empty component required for ID generation")

    # Join with pipe separator for uniqueness
    combined = "|".join(normalized)

    # SHA256 hash, take first N hex chars
    hash_bytes = hashlib.sha256(combined.encode("utf-8")).hexdigest()[:length]

    return f"{prefix}_{hash_bytes}"


def make_account_id(
    domain: Optional[str] = None,
    name: Optional[str] = None,
    location: Optional[str] = None,
) -> str:
    """Generate a deterministic account ID.

    Priority:
    1. Domain (if present) - most reliable natural key
    2. Name + location (fallback for accounts without domain)

    Args:
        domain: Company domain (e.g., "acme.com")
        name: Company name (e.g., "Acme Corp")
        location: Company location/HQ (e.g., "San Francisco, CA")

    Returns:
        Deterministic account ID like "acc_a1b2c3d4e5f6"

    Raises:
        ValueError: If neither domain nor name is provided
    """
    if domain:
        # Domain is the strongest natural key
        # Normalize: remove protocol, www, trailing slashes
        clean_domain = domain.lower().strip()
        clean_domain = clean_domain.replace("https://", "").replace("http://", "")
        clean_domain = clean_domain.replace("www.", "")
        clean_domain = clean_domain.rstrip("/")
        return _hash_components(clean_domain, prefix="acc")

    if name:
        # Fallback to name + location
        return _hash_components(name, location, prefix="acc")

    raise ValueError("Account ID requires either domain or name")


def make_contact_id(
    email: Optional[str] = None,
    account_id: Optional[str] = None,
    full_name: Optional[str] = None,
    role_title: Optional[str] = None,
) -> str:
    """Generate a deterministic contact ID.

    Priority:
    1. Email (if present) - most reliable natural key
    2. Account ID + full name + role title (fallback)

    Args:
        email: Contact email address
        account_id: Associated account ID
        full_name: Contact's full name
        role_title: Contact's job title/role

    Returns:
        Deterministic contact ID like "con_a1b2c3d4e5f6"

    Raises:
        ValueError: If neither email nor (account_id + full_name) is provided
    """
    if email:
        # Email is the strongest natural key
        clean_email = email.lower().strip()
        return _hash_components(clean_email, prefix="con")

    if account_id and full_name:
        # Fallback to account + name + role
        return _hash_components(account_id, full_name, role_title, prefix="con")

    raise ValueError("Contact ID requires either email or (account_id + full_name)")


def make_activity_id(
    run_id: str,
    artifact_ref: Optional[str] = None,
    activity_type: Optional[str] = None,
    subject: Optional[str] = None,
) -> str:
    """Generate a deterministic activity ID.

    Priority:
    1. Run ID + artifact ref + type (for artifact-linked activities)
    2. Run ID + type + subject hash (for other activities)

    Args:
        run_id: Pipeline run ID
        artifact_ref: Path/name of source artifact (e.g., "outreach")
        activity_type: Activity type (e.g., "email", "note")
        subject: Activity subject line (used for hashing if no artifact_ref)

    Returns:
        Deterministic activity ID like "act_a1b2c3d4e5f6"

    Raises:
        ValueError: If run_id is not provided
    """
    if not run_id:
        raise ValueError("Activity ID requires run_id")

    if artifact_ref:
        # Artifact-linked activity (most common case)
        # Normalize artifact_ref to just the name (e.g., "outreach" from path)
        clean_ref = artifact_ref.lower().strip()
        if "/" in clean_ref or "\\" in clean_ref:
            # Extract filename without extension
            import os

            clean_ref = os.path.splitext(os.path.basename(clean_ref))[0]
        return _hash_components(run_id, clean_ref, activity_type, prefix="act")

    if activity_type and subject:
        # Fallback to type + subject hash
        return _hash_components(run_id, activity_type, subject, prefix="act")

    # Minimal fallback: just run_id + type
    if activity_type:
        return _hash_components(run_id, activity_type, prefix="act")

    raise ValueError("Activity ID requires run_id + (artifact_ref or activity_type)")


def make_sequence_activity_id(
    sequence_id: str,
    step_number: int,
) -> str:
    """Generate a deterministic sequence activity ID.

    Args:
        sequence_id: Sequence plan ID
        step_number: Step number in the sequence

    Returns:
        Deterministic activity ID like "seq_a1b2c3d4e5f6"
    """
    return _hash_components(sequence_id, str(step_number), prefix="seq")


# =============================================================================
# Natural Key Extraction Helpers
# =============================================================================


def extract_domain_from_email(email: str) -> Optional[str]:
    """Extract domain from email address.

    Args:
        email: Email address

    Returns:
        Domain part or None if invalid
    """
    if "@" in email:
        return email.split("@")[-1].lower().strip()
    return None


def normalize_domain(url_or_domain: str) -> str:
    """Normalize a URL or domain to a clean domain.

    Args:
        url_or_domain: URL, domain, or email domain

    Returns:
        Clean domain (e.g., "example.com")
    """
    s = url_or_domain.lower().strip()
    # Remove protocol
    s = s.replace("https://", "").replace("http://", "")
    # Remove www
    s = s.replace("www.", "")
    # Remove path
    if "/" in s:
        s = s.split("/")[0]
    return s

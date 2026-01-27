"""Canonical CRM domain models (vendor-agnostic).

These models represent the core CRM entities in a vendor-neutral way.
Each model includes an `external_refs` field for future CRM integration,
allowing mapping to/from external systems (HubSpot, Salesforce, etc.)
without any vendor-specific fields in the canonical model.

M6: Export-only, no API writes. Models are Pydantic and serializable.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ActivityType(str, Enum):
    """Type of CRM activity."""

    EMAIL = "email"
    LINKEDIN = "linkedin"
    CALL = "call"
    MEETING = "meeting"
    NOTE = "note"
    TASK = "task"


class ActivityDirection(str, Enum):
    """Direction of communication activity."""

    OUTBOUND = "outbound"
    INBOUND = "inbound"


class ExternalRef(BaseModel):
    """Reference to an external CRM system.

    This pattern allows linking canonical objects to external systems
    without polluting the canonical model with vendor-specific fields.
    """

    provider: str  # e.g., "hubspot", "salesforce", "pipedrive"
    external_id: str  # ID in the external system
    last_synced_at: Optional[datetime] = None
    sync_hash: Optional[str] = None  # Hash of last synced state for change detection

    model_config = ConfigDict(ser_json_timedelta="iso8601")

    @field_serializer("last_synced_at")
    def serialize_datetime(self, v: Optional[datetime]) -> Optional[str]:
        """Serialize datetime to ISO format."""
        return v.isoformat() if v else None


class Account(BaseModel):
    """Canonical CRM Account (Company).

    Represents a company/organization in the CRM.
    Vendor-agnostic: no HubSpot/Salesforce-specific fields.
    """

    account_id: str = Field(..., description="Internal unique identifier")
    name: str = Field(..., description="Company name")
    domain: Optional[str] = Field(None, description="Company domain (e.g., example.com)")
    industry: Optional[str] = Field(None, description="Industry classification")
    location: Optional[str] = Field(None, description="Primary location/HQ")
    description: Optional[str] = Field(None, description="Company description/snapshot")
    employee_count: Optional[int] = Field(None, description="Estimated employee count")
    tags: List[str] = Field(default_factory=list, description="Tags/labels")

    # External references for CRM integration
    external_refs: List[ExternalRef] = Field(
        default_factory=list,
        description="References to external CRM systems",
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this record was created",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this record was last updated",
    )

    # Optional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(ser_json_timedelta="iso8601")

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, v: datetime) -> str:
        """Serialize datetime to ISO format."""
        return v.isoformat()

    def get_external_id(self, provider: str) -> Optional[str]:
        """Get the external ID for a specific provider."""
        for ref in self.external_refs:
            if ref.provider == provider:
                return ref.external_id
        return None


class Contact(BaseModel):
    """Canonical CRM Contact (Person).

    Represents an individual contact associated with an account.
    Vendor-agnostic: no HubSpot/Salesforce-specific fields.
    """

    contact_id: str = Field(..., description="Internal unique identifier")
    account_id: Optional[str] = Field(None, description="Associated account ID")
    full_name: str = Field(..., description="Contact's full name")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    role_title: Optional[str] = Field(None, description="Job title/role")
    department: Optional[str] = Field(None, description="Department")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    tags: List[str] = Field(default_factory=list, description="Tags/labels")

    # For BD: persona type (champion, economic_buyer, blocker, etc.)
    persona_type: Optional[str] = Field(None, description="BD persona classification")
    hypothesis: Optional[str] = Field(None, description="BD hypothesis about this contact")

    # External references for CRM integration
    external_refs: List[ExternalRef] = Field(
        default_factory=list,
        description="References to external CRM systems",
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this record was created",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this record was last updated",
    )

    # Optional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(ser_json_timedelta="iso8601")

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, v: datetime) -> str:
        """Serialize datetime to ISO format."""
        return v.isoformat()

    def get_external_id(self, provider: str) -> Optional[str]:
        """Get the external ID for a specific provider."""
        for ref in self.external_refs:
            if ref.provider == provider:
                return ref.external_id
        return None


class Activity(BaseModel):
    """Canonical CRM Activity.

    Represents a touchpoint or interaction (email, call, meeting, note).
    Links back to the BD run system for traceability.
    """

    activity_id: str = Field(..., description="Internal unique identifier")
    account_id: str = Field(..., description="Associated account ID")
    contact_id: Optional[str] = Field(None, description="Associated contact ID")

    # Activity details
    activity_type: ActivityType = Field(..., description="Type of activity")
    subject: str = Field(..., description="Subject/title of the activity")
    body: str = Field("", description="Body/content of the activity")
    direction: ActivityDirection = Field(
        ActivityDirection.OUTBOUND,
        description="Direction of communication",
    )
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this activity occurred/was created",
    )

    # Scheduling (for planned activities)
    is_planned: bool = Field(False, description="Whether this is a planned/scheduled activity")
    scheduled_for: Optional[datetime] = Field(None, description="Scheduled date/time")
    sequence_step: Optional[int] = Field(None, description="Step number in outreach sequence")
    sequence_name: Optional[str] = Field(None, description="Name of the outreach sequence")

    # BD traceability (links to run system)
    run_id: Optional[str] = Field(None, description="Run ID that generated this activity")
    artifact_refs: List[str] = Field(
        default_factory=list,
        description="References to artifact files (paths or IDs)",
    )
    source_ids: List[str] = Field(
        default_factory=list,
        description="Source IDs from evidence (deduped, stable-ordered)",
    )

    # External references for CRM integration
    external_refs: List[ExternalRef] = Field(
        default_factory=list,
        description="References to external CRM systems",
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this record was created",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this record was last updated",
    )

    # Optional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(ser_json_timedelta="iso8601")

    @field_serializer("created_at", "updated_at", "occurred_at", "scheduled_for")
    def serialize_datetime(self, v: Optional[datetime]) -> Optional[str]:
        """Serialize datetime to ISO format."""
        return v.isoformat() if v else None

    def get_external_id(self, provider: str) -> Optional[str]:
        """Get the external ID for a specific provider."""
        for ref in self.external_refs:
            if ref.provider == provider:
                return ref.external_id
        return None


# =============================================================================
# Optional Future Models (Interface Definitions)
# =============================================================================


class OpportunityStage(str, Enum):
    """Stage of a sales opportunity/deal."""

    PROSPECTING = "prospecting"
    QUALIFICATION = "qualification"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class Opportunity(BaseModel):
    """Canonical CRM Opportunity/Deal (Interface definition).

    Note: This is defined for future use but not fully implemented in M6.
    """

    opportunity_id: str = Field(..., description="Internal unique identifier")
    account_id: str = Field(..., description="Associated account ID")
    name: str = Field(..., description="Opportunity name")
    stage: OpportunityStage = Field(
        OpportunityStage.PROSPECTING, description="Current stage"
    )
    amount: Optional[float] = Field(None, description="Deal amount")
    currency: str = Field("USD", description="Currency code")
    close_date: Optional[datetime] = Field(None, description="Expected close date")
    probability: Optional[float] = Field(None, description="Win probability (0-1)")

    # External references
    external_refs: List[ExternalRef] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(ser_json_timedelta="iso8601")

    @field_serializer("created_at", "updated_at", "close_date")
    def serialize_datetime(self, v: Optional[datetime]) -> Optional[str]:
        """Serialize datetime to ISO format."""
        return v.isoformat() if v else None


# =============================================================================
# Export Package Models
# =============================================================================


class CRMExportManifest(BaseModel):
    """Manifest for a CRM export package.

    Tracks what was exported and provides traceability back to the run system.

    M6.1: Added run_source_ids for run-level evidence union.
    Activities carry artifact-scoped evidence; manifest has the full union.
    """

    # Export metadata
    export_id: str = Field(..., description="Unique export identifier")
    crm_export_version: str = Field("1.0", description="Export schema version")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this export was created",
    )

    # Source run information
    run_id: Optional[str] = Field(None, description="Source run ID")
    company: Optional[str] = Field(None, description="Company name")

    # Content summary
    account_count: int = Field(0, description="Number of accounts exported")
    contact_count: int = Field(0, description="Number of contacts exported")
    activity_count: int = Field(0, description="Number of activities exported")

    # Traceability
    artifact_refs: List[str] = Field(
        default_factory=list, description="Artifact files included"
    )
    source_count: int = Field(0, description="Total unique sources referenced")
    claim_count: int = Field(0, description="Total claims referenced")

    # M6.1: Run-level evidence (union of all sources across all activities)
    run_source_ids: List[str] = Field(
        default_factory=list,
        description="Union of all source_ids across the run (run-level evidence)",
    )

    # Files in export
    files: List[str] = Field(default_factory=list, description="Files in export package")

    model_config = ConfigDict(ser_json_timedelta="iso8601")

    @field_serializer("created_at")
    def serialize_datetime(self, v: datetime) -> str:
        """Serialize datetime to ISO format."""
        return v.isoformat()


class CRMExportPackage(BaseModel):
    """Complete CRM export package.

    Contains all data for a CRM export, including manifest and entities.
    """

    manifest: CRMExportManifest
    accounts: List[Account] = Field(default_factory=list)
    contacts: List[Contact] = Field(default_factory=list)
    activities: List[Activity] = Field(default_factory=list)

    model_config = ConfigDict(ser_json_timedelta="iso8601")

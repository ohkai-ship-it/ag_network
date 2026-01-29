"""Core data models for AG Network."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Source(BaseModel):
    """Represents a source of information."""

    id: str
    source_type: str  # "url", "pasted_text", "file"
    content: str
    title: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FactCheck(BaseModel):
    """Tracks whether a claim is sourced or assumed."""

    claim: str
    is_assumption: Optional[bool] = None
    source_ids: List[str] = Field(default_factory=list)
    confidence: Optional[float] = None  # 0.0 to 1.0


class EvidenceSnippet(BaseModel):
    """M8: A verbatim quote from a source supporting a fact.

    Used to cite specific evidence for non-assumption facts.
    """

    source_id: str
    url: Optional[str] = None
    quote: str  # Verbatim quote from source (<=220 chars recommended)
    start_char: Optional[int] = None  # Optional: position in source text
    end_char: Optional[int] = None  # Optional: end position in source text

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_id": self.source_id,
            "url": self.url,
            "quote": self.quote,
            "start_char": self.start_char,
            "end_char": self.end_char,
        }


class PersonalizationAngle(BaseModel):
    """M8: Enhanced personalization angle with evidence support.

    Used in research brief to track sourced vs assumed facts.
    """

    name: str
    fact: str
    is_assumption: bool = True
    source_ids: List[str] = Field(default_factory=list)
    evidence: List[EvidenceSnippet] = Field(
        default_factory=list
    )  # M8: Required if is_assumption=false

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "fact": self.fact,
            "is_assumption": self.is_assumption,
            "source_ids": self.source_ids,
            "evidence": [e.to_dict() for e in self.evidence],
        }


class ResearchBrief(BaseModel):
    """Output model for account research."""

    company: str
    snapshot: str
    pains: List[str]
    triggers: List[str]
    competitors: List[str]
    personalization_angles: List[
        Dict[str, Any]
    ]  # {"angle": "...", "fact": "...", "is_assumption": bool, "evidence": [...]}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TargetMap(BaseModel):
    """Output model for prospect target map."""

    company: str
    personas: List[Dict[str, Any]]  # Role, title, hypotheses
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OutreachVariant(BaseModel):
    """A single outreach message variant."""

    channel: str  # "email" or "linkedin"
    subject_or_hook: Optional[str] = None
    body: str
    personalization_notes: Optional[str] = None


class OutreachDraft(BaseModel):
    """Output model for outreach drafts."""

    company: str
    persona: str
    variants: List[OutreachVariant]
    sequence_steps: List[str]
    objection_responses: Dict[str, str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MeetingPrepPack(BaseModel):
    """Output model for meeting preparation."""

    company: str
    meeting_type: str  # "discovery", "demo", "negotiation"
    agenda: List[str]
    questions: List[str]
    stakeholder_map: Dict[str, str]
    listen_for_signals: List[str]
    close_plan: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FollowUpSummary(BaseModel):
    """Output model for post-meeting follow-up."""

    company: str
    meeting_date: datetime
    summary: str
    next_steps: List[str]
    tasks: List[Dict[str, Any]]
    crm_notes: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

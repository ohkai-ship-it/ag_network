"""Sequence builder for BD workflow automation.

Generates multi-step outreach sequences from pipeline artifacts.
Sequences are exported as planned activities in the CRM export package.

A SequencePlan represents a series of touchpoints over time:
- Day 0: Initial outreach
- Day 3: Follow-up if no response
- Day 7: Value-add content share
- Day 14: Final attempt with different angle

M6: No sending. Sequences are exported as planned activities
(is_planned=True, scheduled_for=<date>) in the CRM package.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from agnetwork.crm.models import (
    Activity,
    ActivityDirection,
    ActivityType,
)


@dataclass
class SequenceStep:
    """A single step in an outreach sequence."""

    step_number: int
    day_offset: int  # Days from sequence start
    activity_type: ActivityType
    subject_template: str
    body_template: str
    notes: str = ""

    def render(
        self,
        company: str,
        persona: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, str]:
        """Render the subject and body with variables.

        Args:
            company: Company name
            persona: Target persona
            variables: Additional template variables

        Returns:
            Tuple of (rendered_subject, rendered_body)
        """
        vars = {
            "company": company,
            "persona": persona,
            **(variables or {}),
        }

        subject = self.subject_template.format(**vars)
        body = self.body_template.format(**vars)

        return subject, body


@dataclass
class SequencePlan:
    """A complete outreach sequence plan.

    Contains multiple steps with timing information.
    Can be generated from outreach artifacts or manually configured.
    """

    sequence_id: str
    name: str
    company: str
    persona: str
    account_id: str
    contact_id: Optional[str] = None
    steps: List[SequenceStep] = field(default_factory=list)
    start_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    channel: str = "email"
    run_id: Optional[str] = None
    source_ids: List[str] = field(default_factory=list)
    artifact_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_scheduled_date(self, step: SequenceStep) -> datetime:
        """Calculate the scheduled date for a step.

        Args:
            step: The sequence step

        Returns:
            Scheduled datetime
        """
        return self.start_date + timedelta(days=step.day_offset)

    def to_activities(self) -> List[Activity]:
        """Convert sequence plan to planned Activity objects.

        Returns:
            List of Activity objects with is_planned=True
        """
        activities = []

        for step in self.steps:
            subject, body = step.render(
                company=self.company,
                persona=self.persona,
                variables=self.metadata.get("variables", {}),
            )

            activity_type = (
                ActivityType.EMAIL if self.channel == "email"
                else ActivityType.LINKEDIN
            )

            activities.append(
                Activity(
                    activity_id=f"seq_{self.sequence_id}_step{step.step_number}",
                    account_id=self.account_id,
                    contact_id=self.contact_id,
                    activity_type=activity_type,
                    subject=subject,
                    body=body,
                    direction=ActivityDirection.OUTBOUND,
                    is_planned=True,
                    scheduled_for=self.get_scheduled_date(step),
                    sequence_step=step.step_number,
                    sequence_name=self.name,
                    run_id=self.run_id,
                    artifact_refs=self.artifact_refs,
                    source_ids=self.source_ids,
                    metadata={
                        "sequence_id": self.sequence_id,
                        "day_offset": step.day_offset,
                        "step_notes": step.notes,
                    },
                )
            )

        return activities


# =============================================================================
# Template Loading System (M6.1)
# =============================================================================

import json
from pathlib import Path
from typing import Dict


class SequenceTemplateLoader:
    """Loads sequence templates from JSON files.

    M6.1: Templates are editable without code changes.
    Falls back to built-in defaults if file not found.
    """

    DEFAULT_TEMPLATES_PATH = Path(__file__).parent.parent / "resources" / "sequence_templates.json"

    def __init__(self, templates_path: Optional[Path] = None):
        """Initialize the template loader.

        Args:
            templates_path: Path to templates JSON file. Defaults to built-in.
        """
        self.templates_path = templates_path or self.DEFAULT_TEMPLATES_PATH
        self._templates_cache: Optional[Dict[str, Any]] = None

    def _load_templates(self) -> Dict[str, Any]:
        """Load templates from JSON file with caching."""
        if self._templates_cache is not None:
            return self._templates_cache

        if self.templates_path.exists():
            with open(self.templates_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._templates_cache = data.get("templates", {})
        else:
            # Return empty - will fall back to defaults
            self._templates_cache = {}

        return self._templates_cache

    def list_templates(self) -> List[str]:
        """List all available template names.

        Returns:
            List of template names
        """
        templates = self._load_templates()
        return list(templates.keys())

    def get_template(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a template by name.

        Args:
            name: Template name (e.g., "email_standard")

        Returns:
            Template dict or None if not found
        """
        templates = self._load_templates()
        return templates.get(name)

    def get_steps(self, name: str) -> List[SequenceStep]:
        """Get sequence steps for a template.

        Args:
            name: Template name

        Returns:
            List of SequenceStep objects
        """
        template = self.get_template(name)
        if not template:
            return []

        steps = []
        channel = template.get("channel", "email")
        activity_type = (
            ActivityType.LINKEDIN if channel == "linkedin"
            else ActivityType.EMAIL
        )

        for step_data in template.get("steps", []):
            steps.append(
                SequenceStep(
                    step_number=step_data["step_number"],
                    day_offset=step_data["offset_days"],
                    activity_type=activity_type,
                    subject_template=step_data["subject_pattern"],
                    body_template=step_data["body_template"],
                    notes=step_data.get("notes", ""),
                )
            )

        return steps

    def get_default_template_for_channel(self, channel: str) -> str:
        """Get the default template name for a channel.

        Args:
            channel: "email" or "linkedin"

        Returns:
            Template name
        """
        if channel == "linkedin":
            return "linkedin_connection"
        return "email_standard"


# Global template loader instance
_template_loader = SequenceTemplateLoader()


def get_template_loader() -> SequenceTemplateLoader:
    """Get the global template loader instance."""
    return _template_loader


# =============================================================================
# Default Sequence Templates (Fallback)
# =============================================================================

DEFAULT_SEQUENCE_STEPS = [
    SequenceStep(
        step_number=1,
        day_offset=0,
        activity_type=ActivityType.EMAIL,
        subject_template="Partnership opportunity with {company}",
        body_template="""Hi {persona},

I've been following {company}'s growth and believe there's a strong opportunity for collaboration.

We've helped similar companies achieve significant improvements in their processes.

Would you be open to a brief conversation to explore how we might help {company}?

Best regards""",
        notes="Initial outreach - focus on value proposition",
    ),
    SequenceStep(
        step_number=2,
        day_offset=3,
        activity_type=ActivityType.EMAIL,
        subject_template="Re: Partnership opportunity with {company}",
        body_template="""Hi {persona},

I wanted to follow up on my previous message about a potential partnership.

I understand you're busy, but I believe this could be valuable for {company}.

Would a 15-minute call work for you this week?

Best regards""",
        notes="Follow-up - gentle nudge",
    ),
    SequenceStep(
        step_number=3,
        day_offset=7,
        activity_type=ActivityType.EMAIL,
        subject_template="Quick thought for {company}",
        body_template="""Hi {persona},

I came across an article that reminded me of some challenges companies like {company} often face.

[Thought leadership content placeholder]

If you'd like to discuss how this applies to your situation, I'm happy to chat.

Best regards""",
        notes="Value-add content share - build credibility",
    ),
    SequenceStep(
        step_number=4,
        day_offset=14,
        activity_type=ActivityType.EMAIL,
        subject_template="Closing the loop - {company}",
        body_template="""Hi {persona},

I've reached out a few times about exploring a partnership with {company}.

I don't want to fill your inbox if the timing isn't right.

If you're open to a conversation in the future, feel free to reach out. Otherwise, I'll assume now isn't the best time.

Best of luck with everything at {company}!

Best regards""",
        notes="Final attempt - graceful exit with open door",
    ),
]

LINKEDIN_SEQUENCE_STEPS = [
    SequenceStep(
        step_number=1,
        day_offset=0,
        activity_type=ActivityType.LINKEDIN,
        subject_template="Connection request",
        body_template="""Hi {persona}, I noticed your work at {company} and would love to connect. I help companies like yours achieve better results. Let's connect!""",
        notes="LinkedIn connection request",
    ),
    SequenceStep(
        step_number=2,
        day_offset=2,
        activity_type=ActivityType.LINKEDIN,
        subject_template="Thanks for connecting",
        body_template="""Thanks for connecting, {persona}! I'd love to learn more about what {company} is working on. Would you be open to a quick chat?""",
        notes="Post-connection follow-up",
    ),
    SequenceStep(
        step_number=3,
        day_offset=7,
        activity_type=ActivityType.LINKEDIN,
        subject_template="Value-add share",
        body_template="""Hi {persona}, I thought you might find this interesting: [content]. Let me know if you'd like to discuss how this applies to {company}.""",
        notes="Value-add content share",
    ),
]


class SequenceBuilder:
    """Builds outreach sequences from pipeline artifacts.

    Can generate sequences in two modes:
    - manual: Uses templates (deterministic)
    - llm: Uses LLM to generate personalized sequences (future)

    M6.1: Templates loaded from JSON file by default.
    """

    def __init__(self, mode: str = "manual", template_name: Optional[str] = None):
        """Initialize the sequence builder.

        Args:
            mode: Generation mode ("manual" or "llm")
            template_name: Specific template to use (e.g., "email_standard")
        """
        self.mode = mode
        self.template_name = template_name
        self._loader = get_template_loader()

    def _get_steps_for_channel(self, channel: str) -> List[SequenceStep]:
        """Get sequence steps for a channel.

        M6.1: Tries to load from JSON templates first, falls back to built-in.
        """
        # Use specified template or default for channel
        template_name = self.template_name or self._loader.get_default_template_for_channel(channel)

        # Try loading from JSON templates
        steps = self._loader.get_steps(template_name)
        if steps:
            return steps

        # Fallback to built-in defaults
        if channel == "linkedin":
            return LINKEDIN_SEQUENCE_STEPS
        return DEFAULT_SEQUENCE_STEPS

    def build_from_outreach(
        self,
        outreach_artifact: Dict[str, Any],
        account_id: str,
        contact_id: Optional[str] = None,
        run_id: Optional[str] = None,
        source_ids: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        template_name: Optional[str] = None,
    ) -> SequencePlan:
        """Build a sequence plan from an outreach artifact.

        Uses the outreach artifact's sequence_steps if present,
        otherwise uses templates from JSON file.

        Args:
            outreach_artifact: Outreach artifact JSON data
            account_id: Account ID
            contact_id: Contact ID (optional)
            run_id: Run ID for traceability
            source_ids: Source IDs for traceability
            start_date: Sequence start date (defaults to now)
            template_name: Override template name (M6.1)

        Returns:
            SequencePlan ready for export
        """
        company = outreach_artifact.get("company", "Company")
        persona = outreach_artifact.get("persona", "")
        channel = outreach_artifact.get("channel", "email")

        # Generate sequence ID
        sequence_id = str(uuid.uuid4())[:8]

        # Check if outreach has sequence_steps
        artifact_steps = outreach_artifact.get("sequence_steps", [])

        if artifact_steps and self.mode == "manual":
            # Use artifact-defined steps as a base, map to our format
            steps = self._convert_artifact_steps(artifact_steps, channel)
        elif template_name:
            # M6.1: Use specified template
            steps = self._loader.get_steps(template_name)
            if not steps:
                steps = self._get_steps_for_channel(channel)
        else:
            # M6.1: Use default template for channel (from JSON or fallback)
            steps = self._get_steps_for_channel(channel)

        return SequencePlan(
            sequence_id=sequence_id,
            name=f"{company} Outreach Sequence",
            company=company,
            persona=persona,
            account_id=account_id,
            contact_id=contact_id,
            steps=steps,
            start_date=start_date or datetime.now(timezone.utc),
            channel=channel,
            run_id=run_id,
            source_ids=source_ids or [],
            artifact_refs=[],
            metadata={
                "initial_subject": outreach_artifact.get("subject_or_hook", ""),
                "initial_body": outreach_artifact.get("body", ""),
                "personalization_notes": outreach_artifact.get("personalization_notes", ""),
                "objection_responses": outreach_artifact.get("objection_responses", {}),
            },
        )

    def _convert_artifact_steps(
        self,
        artifact_steps: List[str],
        channel: str,
    ) -> List[SequenceStep]:
        """Convert artifact sequence_steps strings to SequenceStep objects.

        Args:
            artifact_steps: List of step descriptions from artifact
            channel: Channel type (email/linkedin)

        Returns:
            List of SequenceStep objects
        """
        steps = []
        activity_type = (
            ActivityType.LINKEDIN if channel == "linkedin"
            else ActivityType.EMAIL
        )

        # Parse step descriptions like "Initial outreach (Day 0)"
        day_patterns = {
            "day 0": 0,
            "day 3": 3,
            "day 7": 7,
            "day 14": 14,
        }

        for i, step_desc in enumerate(artifact_steps):
            step_lower = step_desc.lower()

            # Extract day offset
            day_offset = 0
            for pattern, offset in day_patterns.items():
                if pattern in step_lower:
                    day_offset = offset
                    break

            steps.append(
                SequenceStep(
                    step_number=i + 1,
                    day_offset=day_offset,
                    activity_type=activity_type,
                    subject_template=f"Step {i+1}: {{company}}",
                    body_template=f"[{step_desc}]\n\nHi {{persona}},\n\n[Content for this step]",
                    notes=step_desc,
                )
            )

        return steps

    def build_custom(
        self,
        company: str,
        persona: str,
        account_id: str,
        contact_id: Optional[str] = None,
        channel: str = "email",
        steps: Optional[List[SequenceStep]] = None,
        start_date: Optional[datetime] = None,
        template_name: Optional[str] = None,
    ) -> SequencePlan:
        """Build a custom sequence plan.

        Args:
            company: Company name
            persona: Target persona
            account_id: Account ID
            contact_id: Contact ID (optional)
            channel: Channel type
            steps: Custom sequence steps (uses templates if not provided)
            start_date: Sequence start date
            template_name: Template name to use (M6.1)

        Returns:
            SequencePlan
        """
        sequence_id = str(uuid.uuid4())[:8]

        if steps is None:
            if template_name:
                steps = self._loader.get_steps(template_name)
            if not steps:
                steps = self._get_steps_for_channel(channel)

        return SequencePlan(
            sequence_id=sequence_id,
            name=f"{company} Outreach Sequence",
            company=company,
            persona=persona,
            account_id=account_id,
            contact_id=contact_id,
            steps=steps,
            start_date=start_date or datetime.now(timezone.utc),
            channel=channel,
        )

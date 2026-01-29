"""Outreach message generation skill."""

import json
from typing import Any, Dict

from jinja2 import Template

from agnetwork.kernel.contracts import (
    ArtifactKind,
    ArtifactRef,
    Claim,
    ClaimKind,
    SkillContext,
    SkillResult,
)
from agnetwork.kernel.executor import register_skill
from agnetwork.models.core import OutreachDraft, OutreachVariant


@register_skill("outreach")
class OutreachSkill:
    """Generates outreach message drafts.

    This skill produces outreach artifacts containing:
    - Email or LinkedIn message drafts
    - Personalization notes
    - Follow-up sequence suggestions
    """

    name = "outreach"
    version = "1.0"

    def __init__(self):
        """Initialize the skill."""
        self.email_template = self._get_email_template()
        self.linkedin_template = self._get_linkedin_template()

    def _get_email_template(self) -> Template:
        """Get email template."""
        return Template("""# Outreach: {{ company }}

## Email Draft

**To**: {{ persona }}
**Subject**: {{ subject }}

---

{{ body }}

---

### Personalization Notes
{{ personalization_notes }}

### Follow-up Sequence
{% for step in sequence_steps %}
{{ loop.index }}. {{ step }}
{% endfor %}
""")

    def _get_linkedin_template(self) -> Template:
        """Get LinkedIn template."""
        return Template("""# Outreach: {{ company }}

## LinkedIn Message

**To**: {{ persona }}
**Hook**: {{ hook }}

---

{{ body }}

---

### Personalization Notes
{{ personalization_notes }}
""")

    def run(self, inputs: Dict[str, Any], context: SkillContext) -> SkillResult:
        """Execute the skill with the standard contract.

        Args:
            inputs: Dict containing company, persona, channel, etc.
            context: Runtime context

        Returns:
            SkillResult with output model, artifacts, and claims
        """
        company = inputs.get("company", "Unknown")
        persona = inputs.get("persona", "Decision Maker")
        channel = inputs.get("channel", "email")

        # Generate content (deterministic for M2)
        if channel == "email":
            subject = f"Partnership opportunity with {company}"
            body = f"""Hi {persona},

I've been following {company}'s growth and believe there's a strong opportunity for collaboration.

We've helped similar companies in your industry achieve significant improvements in their sales processes.

Would you be open to a brief conversation to explore how we might help {company}?

Best regards"""
            hook = None
            personalization_notes = f"Research {company}'s recent announcements for personalization."
        else:  # LinkedIn
            subject = None
            hook = f"Saw {company}'s impressive growth - congrats!"
            body = f"""Hi {persona},

I noticed your profile and was impressed by your work at {company}.

I'd love to connect and share some insights that have helped similar leaders in your space.

Looking forward to connecting!"""
            personalization_notes = "Reference a recent post or shared connection."

        sequence_steps = [
            "Initial outreach (Day 0)",
            "Follow-up if no response (Day 3)",
            "Value-add content share (Day 7)",
            "Final attempt with different angle (Day 14)",
        ]

        objection_responses = {
            "no_budget": "I understand budget constraints. Let me share a quick ROI analysis...",
            "no_time": "I appreciate you're busy. How about a 15-min call at your convenience?",
            "using_competitor": "That's great you have a solution. May I ask what's working well?",
        }

        # Generate markdown
        if channel == "email":
            markdown = self.email_template.render(
                company=company,
                persona=persona,
                subject=subject,
                body=body,
                personalization_notes=personalization_notes,
                sequence_steps=sequence_steps,
            )
        else:
            markdown = self.linkedin_template.render(
                company=company,
                persona=persona,
                hook=hook,
                body=body,
                personalization_notes=personalization_notes,
            )

        # Create JSON data (must include all required fields for schema validation)
        json_data = {
            "company": company,
            "persona": persona,
            "channel": channel,
            "variants": [
                {
                    "channel": channel,
                    "subject_or_hook": subject or hook,
                    "body": body,
                    "personalization_notes": personalization_notes,
                }
            ],
            "sequence_steps": sequence_steps,
            "objection_responses": objection_responses,
        }

        # Create output model
        variant = OutreachVariant(
            channel=channel,
            subject_or_hook=subject or hook,
            body=body,
            personalization_notes=personalization_notes,
        )

        output = OutreachDraft(
            company=company,
            persona=persona,
            variants=[variant],
            sequence_steps=sequence_steps,
            objection_responses=objection_responses,
        )

        # Create claims
        claims = [
            Claim(
                text=f"Outreach strategy for {persona} at {company}",
                kind=ClaimKind.INFERENCE,
                evidence=[],
            ),
        ]

        # Create artifacts
        artifacts = [
            ArtifactRef(
                name="outreach",
                kind=ArtifactKind.MARKDOWN,
                content=markdown,
            ),
            ArtifactRef(
                name="outreach",
                kind=ArtifactKind.JSON,
                content=json.dumps(json_data),
            ),
        ]

        return SkillResult(
            output=output,
            artifacts=artifacts,
            claims=claims,
            skill_name=self.name,
            skill_version=self.version,
        )

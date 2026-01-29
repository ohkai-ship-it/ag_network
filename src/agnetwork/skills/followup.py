"""Follow-up generation skill."""

import json
from datetime import datetime, timezone
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
from agnetwork.models.core import FollowUpSummary


@register_skill("followup")
class FollowupSkill:
    """Generates post-meeting follow-up summaries.

    This skill produces follow-up artifacts containing:
    - Meeting summary
    - Action items and next steps
    - Task assignments
    - CRM notes
    """

    name = "followup"
    version = "1.0"

    def __init__(self):
        """Initialize the skill."""
        self.template = self._get_template()

    def _get_template(self) -> Template:
        """Get the Jinja2 template for follow-ups."""
        template_str = """# Follow-up: {{ company }}

## Meeting Summary
{{ summary }}

## Next Steps
{% for step in next_steps %}
{{ loop.index }}. {{ step }}
{% endfor %}

## Action Items
{% for task in tasks %}
- **{{ task.task }}** - Owner: {{ task.owner }} - Due: {{ task.due }}
{% endfor %}

## CRM Notes
```
{{ crm_notes }}
```
"""
        return Template(template_str)

    def run(self, inputs: Dict[str, Any], context: SkillContext) -> SkillResult:
        """Execute the skill with the standard contract.

        Args:
            inputs: Dict containing company, notes, etc.
            context: Runtime context

        Returns:
            SkillResult with output model, artifacts, and claims
        """
        company = inputs.get("company", "Unknown")
        notes = inputs.get("notes", "Meeting completed successfully")

        # Generate content (deterministic for M2)
        summary = f"""Good initial conversation with {company}. Key points discussed:
- Current challenges and pain points identified
- Interest expressed in our solution
- Next steps agreed upon
- {notes}"""

        next_steps = [
            "Send follow-up email with meeting summary",
            "Share relevant case study or resource",
            "Schedule next meeting or demo",
            "Follow up in 1 week if no response",
        ]

        tasks = [
            {"task": "Send meeting summary email", "owner": "sales", "due": "Today"},
            {"task": "Prepare proposal/demo", "owner": "sales", "due": "3 days"},
            {"task": "Schedule follow-up call", "owner": "sales", "due": "1 week"},
        ]

        crm_notes = f"""Company: {company}
Meeting Date: {datetime.now(timezone.utc).strftime("%Y-%m-%d")}
Status: Active Opportunity
Next Action: Send follow-up email
Notes: {notes}"""

        # Generate markdown
        markdown = self.template.render(
            company=company,
            summary=summary,
            next_steps=next_steps,
            tasks=tasks,
            crm_notes=crm_notes,
        )

        # Create JSON data
        json_data = {
            "company": company,
            "summary": summary,
            "next_steps": next_steps,
            "tasks": tasks,
            "crm_notes": crm_notes,
        }

        # Create output model
        output = FollowUpSummary(
            company=company,
            meeting_date=datetime.now(timezone.utc),
            summary=summary,
            next_steps=next_steps,
            tasks=tasks,
            crm_notes=crm_notes,
        )

        # Create claims
        claims = [
            Claim(
                text=f"Follow-up summary for meeting with {company}",
                kind=ClaimKind.INFERENCE,
                evidence=[],
            ),
        ]

        # Create artifacts
        artifacts = [
            ArtifactRef(
                name="followup",
                kind=ArtifactKind.MARKDOWN,
                content=markdown,
            ),
            ArtifactRef(
                name="followup",
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

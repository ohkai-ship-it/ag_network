"""Meeting preparation skill."""

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
from agnetwork.models.core import MeetingPrepPack


@register_skill("meeting_prep")
class MeetingPrepSkill:
    """Generates meeting preparation packs.

    This skill produces meeting prep artifacts containing:
    - Meeting agenda
    - Discovery questions
    - Stakeholder map
    - Listen-for signals
    - Close plan
    """

    name = "meeting_prep"
    version = "1.0"

    def __init__(self):
        """Initialize the skill."""
        self.template = self._get_template()

    def _get_template(self) -> Template:
        """Get the Jinja2 template for meeting prep."""
        template_str = """# Meeting Prep: {{ company }}

## Meeting Type: {{ meeting_type | title }}

## Agenda
{% for item in agenda %}
{{ loop.index }}. {{ item }}
{% endfor %}

## Discovery Questions
{% for question in questions %}
- {{ question }}
{% endfor %}

## Stakeholder Map
{% for title, role in stakeholder_map.items() %}
- **{{ title }}**: {{ role }}
{% endfor %}

## Listen For
{% for signal in listen_for_signals %}
- {{ signal }}
{% endfor %}

## Close Plan
{{ close_plan }}
"""
        return Template(template_str)

    def run(self, inputs: Dict[str, Any], context: SkillContext) -> SkillResult:
        """Execute the skill with the standard contract.

        Args:
            inputs: Dict containing company, meeting_type, etc.
            context: Runtime context

        Returns:
            SkillResult with output model, artifacts, and claims
        """
        company = inputs.get("company", "Unknown")
        meeting_type = inputs.get("meeting_type", "discovery")

        # Generate content based on meeting type (deterministic for M2)
        if meeting_type == "discovery":
            agenda = [
                "Introductions and rapport building (5 min)",
                "Current state and challenges (15 min)",
                "Ideal future state discussion (10 min)",
                "Solution overview if appropriate (10 min)",
                "Next steps and timeline (5 min)",
            ]
            questions = [
                "What are your current top priorities for this quarter?",
                "How are you currently addressing this challenge?",
                "What would success look like for you?",
                "Who else is involved in this decision?",
                "What's your timeline for making a change?",
            ]
            close_plan = "Propose a follow-up demo with technical team if interest is confirmed."
        elif meeting_type == "demo":
            agenda = [
                "Quick recap of previous discussion (5 min)",
                "Live product demonstration (20 min)",
                "Q&A and objection handling (15 min)",
                "Pricing and proposal discussion (10 min)",
                "Next steps (5 min)",
            ]
            questions = [
                "Does this address the challenges we discussed?",
                "What features would be most valuable to your team?",
                "Any concerns about implementation?",
                "What's the decision-making process from here?",
            ]
            close_plan = "Send proposal within 24 hours; schedule decision call."
        else:  # negotiation
            agenda = [
                "Relationship check-in (5 min)",
                "Proposal review and value recap (10 min)",
                "Negotiation and terms discussion (20 min)",
                "Agreement on modified terms (10 min)",
                "Contract and timeline confirmation (10 min)",
            ]
            questions = [
                "What aspects of the proposal work well for you?",
                "Are there specific terms you'd like to discuss?",
                "What would help you move forward today?",
                "Is there anything preventing a decision?",
            ]
            close_plan = "Get verbal commitment; send contract same day."

        stakeholder_map = {
            "VP Sales": "Economic buyer",
            "Sales Manager": "Champion",
            "IT Director": "Technical evaluator",
        }

        listen_for_signals = [
            "Budget allocation or fiscal year timing",
            "Competitive mentions or evaluations",
            "Internal politics or resistance",
            "Urgency indicators or compelling events",
        ]

        # Generate markdown
        markdown = self.template.render(
            company=company,
            meeting_type=meeting_type,
            agenda=agenda,
            questions=questions,
            stakeholder_map=stakeholder_map,
            listen_for_signals=listen_for_signals,
            close_plan=close_plan,
        )

        # Create JSON data
        json_data = {
            "company": company,
            "meeting_type": meeting_type,
            "agenda": agenda,
            "questions": questions,
            "stakeholder_map": stakeholder_map,
            "listen_for_signals": listen_for_signals,
            "close_plan": close_plan,
        }

        # Create output model
        output = MeetingPrepPack(
            company=company,
            meeting_type=meeting_type,
            agenda=agenda,
            questions=questions,
            stakeholder_map=stakeholder_map,
            listen_for_signals=listen_for_signals,
            close_plan=close_plan,
        )

        # Create claims
        claims = [
            Claim(
                text=f"Meeting prep strategy for {meeting_type} with {company}",
                kind=ClaimKind.INFERENCE,
                evidence=[],
            ),
        ]

        # Create artifacts
        artifacts = [
            ArtifactRef(
                name="meeting_prep",
                kind=ArtifactKind.MARKDOWN,
                content=markdown,
            ),
            ArtifactRef(
                name="meeting_prep",
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

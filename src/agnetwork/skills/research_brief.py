"""Research brief generation skill."""

import json
from typing import Any, Dict, List

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
from agnetwork.models.core import ResearchBrief


@register_skill("research_brief")
class ResearchBriefSkill:
    """Generates account research briefs.

    This skill produces a research brief artifact containing:
    - Company snapshot
    - Key pains and triggers
    - Competitor analysis
    - Personalization angles

    It follows the standard Skill contract and returns a SkillResult.
    """

    name = "research_brief"
    version = "1.0"

    def __init__(self):
        """Initialize the skill."""
        self.template = self._get_template()

    def _get_template(self) -> Template:
        """Get the Jinja2 template for research briefs."""
        template_str = """# Account Research Brief: {{ company }}

## Snapshot
{{ snapshot }}

## Key Pains
{% for pain in pains %}
- {{ pain }}
{% endfor %}

## Triggers
{% for trigger in triggers %}
- {{ trigger }}
{% endfor %}

## Competitors
{% for competitor in competitors %}
- {{ competitor }}
{% endfor %}

## Personalization Angles

{% for angle in personalization_angles %}
### Angle: {{ angle.name }}
- **Fact**: {{ angle.fact }} {% if angle.is_assumption %}(ASSUMPTION){% endif %}

{% endfor %}
"""
        return Template(template_str)

    def run(self, inputs: Dict[str, Any], context: SkillContext) -> SkillResult:
        """Execute the skill with the standard contract.

        Args:
            inputs: Dict containing company, snapshot, pains, triggers, etc.
            context: Runtime context with run_id, workspace, etc.

        Returns:
            SkillResult with output model, artifacts, and claims
        """
        # Extract inputs
        company = inputs.get("company", "Unknown")
        snapshot = inputs.get("snapshot", "")
        pains = inputs.get("pains", [])
        triggers = inputs.get("triggers", [])
        competitors = inputs.get("competitors", [])
        personalization_angles = inputs.get("personalization_angles", [])

        # Generate default angles if not provided
        if not personalization_angles:
            personalization_angles = [
                {
                    "name": "Market Expansion",
                    "fact": f"{company} is expanding into new markets",
                    "is_assumption": True,
                    "source_ids": [],
                },
                {
                    "name": "Cost Optimization",
                    "fact": f"{company} seeks to optimize operational costs",
                    "is_assumption": True,
                    "source_ids": [],
                },
                {
                    "name": "Digital Transformation",
                    "fact": f"{company} is undergoing digital transformation",
                    "is_assumption": True,
                    "source_ids": [],
                },
            ]

        # Generate markdown and JSON
        markdown, json_data = self.generate(
            company=company,
            snapshot=snapshot,
            pains=pains,
            triggers=triggers,
            competitors=competitors,
            personalization_angles=personalization_angles,
        )

        # Create output model
        output = ResearchBrief(
            company=company,
            snapshot=snapshot,
            pains=pains,
            triggers=triggers,
            competitors=competitors,
            personalization_angles=personalization_angles,
        )

        # Create claims for traceability
        claims = self._extract_claims(personalization_angles, company)

        # Create artifacts
        artifacts = [
            ArtifactRef(
                name="research_brief",
                kind=ArtifactKind.MARKDOWN,
                content=markdown,
            ),
            ArtifactRef(
                name="research_brief",
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

    def _extract_claims(
        self, personalization_angles: List[Dict[str, Any]], company: str
    ) -> List[Claim]:
        """Extract claims from personalization angles.

        Args:
            personalization_angles: List of angle dicts
            company: Company name for context

        Returns:
            List of Claim objects
        """
        from agnetwork.kernel.contracts import SourceRef

        claims = []
        for angle in personalization_angles:
            fact = angle.get("fact", "")
            is_assumption = angle.get("is_assumption", True)
            source_ids = angle.get("source_ids", [])

            # M5: Convert source_ids strings to SourceRef objects
            evidence = [
                SourceRef(source_id=sid, source_type="url")
                for sid in source_ids
            ]

            claim = Claim(
                text=fact,
                kind=ClaimKind.ASSUMPTION if is_assumption else ClaimKind.FACT,
                evidence=evidence,
            )
            claims.append(claim)
        return claims

    def generate(
        self,
        company: str,
        snapshot: str,
        pains: List[str],
        triggers: List[str],
        competitors: List[str],
        personalization_angles: List[Dict[str, Any]],
    ) -> tuple[str, Dict[str, Any]]:
        """Generate research brief markdown and JSON data.

        This method is kept for backward compatibility with existing
        CLI commands that call it directly.
        """
        # Generate markdown from template
        markdown = self.template.render(
            company=company,
            snapshot=snapshot,
            pains=pains,
            triggers=triggers,
            competitors=competitors,
            personalization_angles=personalization_angles,
        )

        # Create JSON data model
        json_data = {
            "company": company,
            "snapshot": snapshot,
            "pains": pains,
            "triggers": triggers,
            "competitors": competitors,
            "personalization_angles": personalization_angles,
        }

        return markdown, json_data

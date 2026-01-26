"""Target map generation skill."""

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
from agnetwork.models.core import TargetMap


@register_skill("target_map")
class TargetMapSkill:
    """Generates prospect target maps.

    This skill produces a target map artifact containing:
    - Key personas to target
    - Role classification (economic buyer, champion, blocker)
    - Engagement hypotheses
    """

    name = "target_map"
    version = "1.0"

    def __init__(self):
        """Initialize the skill."""
        self.template = self._get_template()

    def _get_template(self) -> Template:
        """Get the Jinja2 template for target maps."""
        template_str = """# Target Map: {{ company }}

## Personas

{% for persona in personas %}
### {{ persona.title }}
- **Role**: {{ persona.role }}
- **Hypothesis**: {{ persona.hypothesis }}
{% if persona.is_assumption %}- _(Assumption)_{% endif %}

{% endfor %}
"""
        return Template(template_str)

    def run(self, inputs: Dict[str, Any], context: SkillContext) -> SkillResult:
        """Execute the skill with the standard contract.

        Args:
            inputs: Dict containing company, persona, etc.
            context: Runtime context

        Returns:
            SkillResult with output model, artifacts, and claims
        """
        company = inputs.get("company", "Unknown")
        persona = inputs.get("persona")

        # Generate personas (deterministic for M2)
        personas = [
            {
                "title": "VP Sales",
                "role": "economic_buyer",
                "hypothesis": "Controls budget and final decision",
                "is_assumption": True,
                "source_ids": [],
            },
            {
                "title": "Sales Manager",
                "role": "champion",
                "hypothesis": "Advocates internally and drives adoption",
                "is_assumption": True,
                "source_ids": [],
            },
            {
                "title": "IT Director",
                "role": "blocker",
                "hypothesis": "Has technical and security concerns",
                "is_assumption": True,
                "source_ids": [],
            },
        ]

        # Filter if persona specified
        if persona:
            personas = [p for p in personas if p["title"].lower() == persona.lower()] or personas

        # Generate markdown
        markdown = self.template.render(company=company, personas=personas)

        # Create JSON data
        json_data = {
            "company": company,
            "personas": personas,
        }

        # Create output model
        output = TargetMap(company=company, personas=personas)

        # Create claims with M5 source_ids support
        from agnetwork.kernel.contracts import SourceRef

        claims = []
        for p in personas:
            source_ids = p.get("source_ids", [])
            evidence = [
                SourceRef(source_id=sid, source_type="url")
                for sid in source_ids
            ]
            claims.append(
                Claim(
                    text=p["hypothesis"],
                    kind=ClaimKind.ASSUMPTION if p.get("is_assumption", True) else ClaimKind.FACT,
                    evidence=evidence,
                )
            )

        # Create artifacts
        artifacts = [
            ArtifactRef(
                name="target_map",
                kind=ArtifactKind.MARKDOWN,
                content=markdown,
            ),
            ArtifactRef(
                name="target_map",
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

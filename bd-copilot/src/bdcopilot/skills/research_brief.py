"""Research brief generation skill."""

from typing import Any, Dict, List

from jinja2 import Template


class ResearchBriefSkill:
    """Generates account research briefs."""

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

    def generate(
        self,
        company: str,
        snapshot: str,
        pains: List[str],
        triggers: List[str],
        competitors: List[str],
        personalization_angles: List[Dict[str, Any]],
    ) -> tuple[str, Dict[str, Any]]:
        """Generate research brief markdown and JSON data."""
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

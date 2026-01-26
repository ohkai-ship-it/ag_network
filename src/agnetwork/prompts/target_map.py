"""Prompt builder for target map generation."""

from typing import Any, Dict, Tuple


def build_target_map_prompt(
    company: str,
    industry: str | None = None,
    company_size: str | None = None,
    research_context: Dict[str, Any] | None = None,
) -> Tuple[str, str]:
    """Build system and user prompts for target map generation.

    Args:
        company: Company name
        industry: Optional industry context
        company_size: Optional company size (startup, mid-market, enterprise)
        research_context: Optional context from research brief

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    system_prompt = """You are an expert B2B sales strategist specializing in account mapping. Your task is to create a target map identifying key personas to engage at a prospect company.

OUTPUT FORMAT:
You must output ONLY valid JSON matching this exact schema:
{
  "company": string (required),
  "personas": [
    {
      "title": string (job title, e.g., "VP Sales"),
      "role": string (one of: "economic_buyer", "champion", "technical_evaluator", "blocker", "influencer", "end_user"),
      "hypothesis": string (why this persona matters and how to approach them),
      "is_assumption": boolean (true if not verified from sources),
      "source_ids": [string] (list of source IDs used, empty if assumption)
    }
  ] (required, list of 3-6 personas)
}

PERSONA ROLES:
- economic_buyer: Controls budget and final decision
- champion: Internal advocate who drives adoption
- technical_evaluator: Assesses technical fit and integration
- blocker: May resist or delay the deal
- influencer: Shapes opinions but doesn't decide
- end_user: Will use the product day-to-day

EVIDENCE RULES:
1. If a persona is known from sources, set is_assumption: false and list source_ids
2. If persona is inferred (not confirmed), set is_assumption: true and source_ids: []

GENERAL RULES:
1. Output ONLY valid JSON - no markdown, no explanations, no code fences
2. Include at least one economic_buyer and one champion
3. Provide actionable hypotheses for engaging each persona
4. Consider the company size and industry when selecting titles
5. Focus on B2B SaaS sales context"""

    # Build user prompt
    user_parts = [f"Create a target map for: {company}"]

    if industry:
        user_parts.append(f"\nIndustry: {industry}")

    if company_size:
        user_parts.append(f"\nCompany size: {company_size}")

    if research_context:
        if research_context.get("pains"):
            user_parts.append(f"\nKnown pains: {', '.join(research_context['pains'][:3])}")
        if research_context.get("snapshot"):
            user_parts.append(f"\nContext: {research_context['snapshot'][:200]}")

    user_parts.append("\n\nOutput the target map as JSON:")

    user_prompt = "".join(user_parts)

    return system_prompt, user_prompt


# JSON schema for documentation
TARGET_MAP_SCHEMA = {
    "type": "object",
    "required": ["company", "personas"],
    "properties": {
        "company": {"type": "string"},
        "personas": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "role", "hypothesis", "is_assumption", "source_ids"],
                "properties": {
                    "title": {"type": "string"},
                    "role": {
                        "type": "string",
                        "enum": ["economic_buyer", "champion", "technical_evaluator", "blocker", "influencer", "end_user"],
                    },
                    "hypothesis": {"type": "string"},
                    "is_assumption": {"type": "boolean"},
                    "source_ids": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}

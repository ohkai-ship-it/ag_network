"""Prompt builder for research brief generation."""

from typing import Any, Dict, List, Tuple


def build_research_brief_prompt(
    company: str,
    snapshot: str,
    pains: List[str],
    triggers: List[str],
    competitors: List[str],
    sources: List[Dict[str, Any]] | None = None,
) -> Tuple[str, str]:
    """Build system and user prompts for research brief generation.

    Args:
        company: Company name
        snapshot: Company description/snapshot
        pains: List of known pain points
        triggers: List of trigger events
        competitors: List of competitors
        sources: Optional list of source documents

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    system_prompt = """You are an expert B2B sales research analyst. Your task is to generate a comprehensive account research brief for sales teams.

OUTPUT FORMAT:
You must output ONLY valid JSON matching this exact schema:
{
  "company": string (required),
  "snapshot": string (required, 2-3 sentences about the company),
  "pains": [string] (required, list of 3-5 key pain points),
  "triggers": [string] (required, list of 2-4 trigger events),
  "competitors": [string] (required, list of 2-5 competitors),
  "personalization_angles": [
    {
      "name": string (short name for the angle),
      "fact": string (the insight or fact),
      "is_assumption": boolean (true if not from sources),
      "source_ids": [string] (list of source IDs used, empty if assumption)
    }
  ] (required, list of 2-5 angles)
}

EVIDENCE RULES:
1. If a fact comes from one of the provided sources, set is_assumption: false and list source IDs in source_ids
2. If no source supports the fact, set is_assumption: true and source_ids: []
3. ONLY reference source IDs that were provided to you (e.g., [1], [2])
4. Do NOT invent specific statistics, quotes, or citations

GENERAL RULES:
1. Output ONLY valid JSON - no markdown, no explanations, no code fences
2. Use professional B2B sales language
3. Focus on actionable insights for sales conversations
4. If no sources are provided, ALL personalization facts are assumptions"""

    # Build user prompt with available context
    user_parts = [
        f"Generate a research brief for: {company}",
        f"\nCompany snapshot: {snapshot}" if snapshot else "",
    ]

    if pains:
        user_parts.append(f"\nKnown pain points: {', '.join(pains)}")

    if triggers:
        user_parts.append(f"\nTrigger events: {', '.join(triggers)}")

    if competitors:
        user_parts.append(f"\nCompetitors: {', '.join(competitors)}")

    if sources:
        user_parts.append("\n\nSOURCES (use these source IDs when citing facts):")
        for i, source in enumerate(sources, 1):
            source_id = source.get("id", f"src_{i}")
            title = source.get("title", f"Source {i}")
            content = source.get("content", "")[:500]
            user_parts.append(f"\n[{source_id}] {title}:\n{content}")
    else:
        user_parts.append("\n\nNo sources provided - ALL insights will be assumptions. Set is_assumption: true and source_ids: [] for all angles.")

    user_parts.append("\n\nOutput the research brief as JSON:")

    user_prompt = "".join(user_parts)

    return system_prompt, user_prompt


# JSON schema for documentation
RESEARCH_BRIEF_SCHEMA = {
    "type": "object",
    "required": ["company", "snapshot", "pains", "triggers", "competitors", "personalization_angles"],
    "properties": {
        "company": {"type": "string"},
        "snapshot": {"type": "string"},
        "pains": {"type": "array", "items": {"type": "string"}},
        "triggers": {"type": "array", "items": {"type": "string"}},
        "competitors": {"type": "array", "items": {"type": "string"}},
        "personalization_angles": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "fact", "is_assumption", "source_ids"],
                "properties": {
                    "name": {"type": "string"},
                    "fact": {"type": "string"},
                    "is_assumption": {"type": "boolean"},
                    "source_ids": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}

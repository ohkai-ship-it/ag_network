"""Prompt builder for outreach message generation."""

from typing import Any, Dict, List, Tuple


def build_outreach_prompt(
    company: str,
    persona: str,
    channel: str,
    research_context: Dict[str, Any] | None = None,
    personalization_angles: List[Dict[str, Any]] | None = None,
) -> Tuple[str, str]:
    """Build system and user prompts for outreach message generation.

    Args:
        company: Company name
        persona: Target persona (e.g., "VP Sales")
        channel: Channel type ("email" or "linkedin")
        research_context: Optional context from research brief
        personalization_angles: Optional angles for personalization

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    system_prompt = """You are an expert B2B sales copywriter. Your task is to create compelling outreach messages that start conversations with prospects.

OUTPUT FORMAT:
You must output ONLY valid JSON matching this exact schema:
{
  "company": string (required),
  "persona": string (required, target persona title),
  "channel": string (required, "email" or "linkedin"),
  "variants": [
    {
      "channel": string ("email" or "linkedin"),
      "subject_or_hook": string or null (subject line for email, opening hook for linkedin),
      "body": string (the message body),
      "personalization_notes": string or null (notes for the sender)
    }
  ] (required, 1-3 variants),
  "sequence_steps": [string] (required, 3-5 follow-up sequence steps),
  "objection_responses": {
    "no_budget": string,
    "no_time": string,
    "using_competitor": string
  } (required, responses to common objections)
}

RULES:
1. Output ONLY valid JSON - no markdown, no explanations, no code fences
2. Keep emails under 150 words, LinkedIn messages under 100 words
3. Use a conversational, peer-to-peer tone - not salesy
4. Include a clear but soft call-to-action
5. Reference specific context when available (but mark assumptions)
6. NO fake statistics, quotes, or fabricated details
7. Subject lines should be curiosity-driven, not clickbait"""

    # Build user prompt
    user_parts = [
        f"Create outreach for {persona} at {company}",
        f"\nChannel: {channel}",
    ]

    if research_context:
        if research_context.get("snapshot"):
            user_parts.append(f"\nCompany context: {research_context['snapshot'][:200]}")
        if research_context.get("pains"):
            user_parts.append(f"\nKnown challenges: {', '.join(research_context['pains'][:3])}")

    if personalization_angles:
        user_parts.append("\nPersonalization angles:")
        for angle in personalization_angles[:3]:
            assumption_tag = " (ASSUMPTION)" if angle.get("is_assumption") else ""
            user_parts.append(
                f"  - {angle.get('name', 'Angle')}: {angle.get('fact', '')}{assumption_tag}"
            )

    user_parts.append("\n\nOutput the outreach package as JSON:")

    user_prompt = "".join(user_parts)

    return system_prompt, user_prompt


# JSON schema for documentation
OUTREACH_SCHEMA = {
    "type": "object",
    "required": [
        "company",
        "persona",
        "channel",
        "variants",
        "sequence_steps",
        "objection_responses",
    ],
    "properties": {
        "company": {"type": "string"},
        "persona": {"type": "string"},
        "channel": {"type": "string", "enum": ["email", "linkedin"]},
        "variants": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["channel", "body"],
                "properties": {
                    "channel": {"type": "string"},
                    "subject_or_hook": {"type": ["string", "null"]},
                    "body": {"type": "string"},
                    "personalization_notes": {"type": ["string", "null"]},
                },
            },
        },
        "sequence_steps": {"type": "array", "items": {"type": "string"}},
        "objection_responses": {
            "type": "object",
            "properties": {
                "no_budget": {"type": "string"},
                "no_time": {"type": "string"},
                "using_competitor": {"type": "string"},
            },
        },
    },
}

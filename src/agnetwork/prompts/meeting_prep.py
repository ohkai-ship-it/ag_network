"""Prompt builder for meeting preparation generation."""

from typing import Any, Dict, List, Tuple


def build_meeting_prep_prompt(
    company: str,
    meeting_type: str,
    research_context: Dict[str, Any] | None = None,
    target_personas: List[Dict[str, Any]] | None = None,
) -> Tuple[str, str]:
    """Build system and user prompts for meeting prep generation.

    Args:
        company: Company name
        meeting_type: Type of meeting ("discovery", "demo", "negotiation")
        research_context: Optional context from research brief
        target_personas: Optional personas from target map

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    system_prompt = """You are an expert B2B sales strategist. Your task is to create a comprehensive meeting preparation pack for sales meetings.

OUTPUT FORMAT:
You must output ONLY valid JSON matching this exact schema:
{
  "company": string (required),
  "meeting_type": string (required, "discovery", "demo", or "negotiation"),
  "agenda": [string] (required, 4-6 agenda items with time estimates),
  "questions": [string] (required, 4-6 discovery/qualifying questions),
  "stakeholder_map": {
    "Title": "Role description"
  } (required, key stakeholders and their roles),
  "listen_for_signals": [string] (required, 3-5 buying signals to watch for),
  "close_plan": string (required, specific next step to propose)
}

MEETING TYPE GUIDANCE:
- discovery: Focus on understanding problems, building rapport, qualifying
- demo: Focus on showing value, handling objections, technical validation
- negotiation: Focus on value justification, terms discussion, closing

RULES:
1. Output ONLY valid JSON - no markdown, no explanations, no code fences
2. Tailor questions and agenda to the specific meeting type
3. Include realistic time estimates for agenda items
4. Questions should be open-ended and discovery-focused
5. Close plan should be specific and appropriate to meeting stage
6. Listen-for signals should be actionable and observable"""

    # Build user prompt
    user_parts = [
        f"Create meeting prep for {meeting_type} meeting with {company}",
    ]

    if research_context:
        if research_context.get("snapshot"):
            user_parts.append(f"\nCompany: {research_context['snapshot'][:200]}")
        if research_context.get("pains"):
            user_parts.append(f"\nKnown challenges: {', '.join(research_context['pains'][:3])}")

    if target_personas:
        user_parts.append("\nExpected attendees:")
        for persona in target_personas[:4]:
            user_parts.append(
                f"  - {persona.get('title', 'Unknown')} ({persona.get('role', 'unknown role')})"
            )

    user_parts.append("\n\nOutput the meeting prep as JSON:")

    user_prompt = "".join(user_parts)

    return system_prompt, user_prompt


# JSON schema for documentation
MEETING_PREP_SCHEMA = {
    "type": "object",
    "required": [
        "company",
        "meeting_type",
        "agenda",
        "questions",
        "stakeholder_map",
        "listen_for_signals",
        "close_plan",
    ],
    "properties": {
        "company": {"type": "string"},
        "meeting_type": {"type": "string", "enum": ["discovery", "demo", "negotiation"]},
        "agenda": {"type": "array", "items": {"type": "string"}},
        "questions": {"type": "array", "items": {"type": "string"}},
        "stakeholder_map": {
            "type": "object",
            "additionalProperties": {"type": "string"},
        },
        "listen_for_signals": {"type": "array", "items": {"type": "string"}},
        "close_plan": {"type": "string"},
    },
}

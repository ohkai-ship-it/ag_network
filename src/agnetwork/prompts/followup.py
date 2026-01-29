"""Prompt builder for follow-up summary generation."""

from datetime import datetime
from typing import Any, Dict, Tuple


def build_followup_prompt(
    company: str,
    notes: str,
    meeting_date: datetime | None = None,
    research_context: Dict[str, Any] | None = None,
    meeting_prep_context: Dict[str, Any] | None = None,
) -> Tuple[str, str]:
    """Build system and user prompts for follow-up generation.

    Args:
        company: Company name
        notes: Meeting notes or summary
        meeting_date: Optional meeting date
        research_context: Optional context from research brief
        meeting_prep_context: Optional context from meeting prep

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    system_prompt = """You are an expert B2B sales operations specialist. Your task is to create a structured post-meeting follow-up summary with actionable next steps.

OUTPUT FORMAT:
You must output ONLY valid JSON matching this exact schema:
{
  "company": string (required),
  "meeting_date": string (required, ISO format date),
  "summary": string (required, 2-4 sentence meeting summary),
  "next_steps": [string] (required, 3-5 specific next steps),
  "tasks": [
    {
      "task": string (the task description),
      "owner": string (who owns it: "sales", "prospect", "technical", "management"),
      "due": string (relative deadline: "Today", "Tomorrow", "This week", "Next week")
    }
  ] (required, 2-5 actionable tasks),
  "crm_notes": string (required, formatted notes for CRM entry)
}

RULES:
1. Output ONLY valid JSON - no markdown, no explanations, no code fences
2. Summary should capture key outcomes and sentiment
3. Next steps should be specific and actionable
4. Tasks should have clear ownership and deadlines
5. CRM notes should be concise and factual
6. Focus on moving the deal forward"""

    # Build user prompt
    meeting_date_str = (meeting_date or datetime.now()).strftime("%Y-%m-%d")

    user_parts = [
        f"Create follow-up summary for meeting with {company}",
        f"\nMeeting date: {meeting_date_str}",
        f"\nMeeting notes:\n{notes}",
    ]

    if research_context:
        if research_context.get("snapshot"):
            user_parts.append(f"\nCompany context: {research_context['snapshot'][:150]}")

    if meeting_prep_context:
        if meeting_prep_context.get("meeting_type"):
            user_parts.append(f"\nMeeting type: {meeting_prep_context['meeting_type']}")
        if meeting_prep_context.get("close_plan"):
            user_parts.append(f"\nPlanned close: {meeting_prep_context['close_plan']}")

    user_parts.append("\n\nOutput the follow-up summary as JSON:")

    user_prompt = "".join(user_parts)

    return system_prompt, user_prompt


# JSON schema for documentation
FOLLOWUP_SCHEMA = {
    "type": "object",
    "required": ["company", "meeting_date", "summary", "next_steps", "tasks", "crm_notes"],
    "properties": {
        "company": {"type": "string"},
        "meeting_date": {"type": "string", "format": "date-time"},
        "summary": {"type": "string"},
        "next_steps": {"type": "array", "items": {"type": "string"}},
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["task", "owner", "due"],
                "properties": {
                    "task": {"type": "string"},
                    "owner": {
                        "type": "string",
                        "enum": ["sales", "prospect", "technical", "management"],
                    },
                    "due": {"type": "string"},
                },
            },
        },
        "crm_notes": {"type": "string"},
    },
}

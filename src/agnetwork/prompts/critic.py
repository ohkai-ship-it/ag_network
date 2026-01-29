"""Critic prompt builder for quality review pass.

The critic reviews LLM-generated outputs and can:
1. Return issues that need human attention
2. Return a patched JSON that fixes identified problems
"""

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class CriticIssue(BaseModel):
    """An issue identified by the critic."""

    severity: str  # "error", "warning", "suggestion"
    category: str  # "unsourced_claim", "missing_field", "tone", "accuracy"
    message: str
    field_path: Optional[str] = None  # JSON path to problematic field
    suggested_fix: Optional[str] = None


class CriticResult(BaseModel):
    """Result from critic review."""

    passed: bool = False
    issues: List[CriticIssue] = Field(default_factory=list)
    patched_json: Optional[Dict[str, Any]] = None  # Fixed version if available

    def has_errors(self) -> bool:
        """Check if there are any error-level issues."""
        return any(i.severity == "error" for i in self.issues)

    def has_warnings(self) -> bool:
        """Check if there are any warning-level issues."""
        return any(i.severity == "warning" for i in self.issues)


def build_critic_prompt(
    output_json: Dict[str, Any],
    artifact_type: str,
    constraints: Dict[str, Any] | None = None,
    evidence_summary: str | None = None,
) -> Tuple[str, str]:
    """Build system and user prompts for critic review.

    Args:
        output_json: The JSON output to review
        artifact_type: Type of artifact ("research_brief", "target_map", etc.)
        constraints: Optional constraints that should be enforced
        evidence_summary: Optional summary of available evidence/sources

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    system_prompt = """You are a critical quality reviewer for B2B sales content. Your task is to review generated content and identify issues or improvements.

OUTPUT FORMAT:
You must output ONLY valid JSON matching this schema:
{
  "passed": boolean (true if content is acceptable),
  "issues": [
    {
      "severity": "error" | "warning" | "suggestion",
      "category": "unsourced_claim" | "missing_field" | "tone" | "accuracy" | "completeness",
      "message": string (description of the issue),
      "field_path": string or null (JSON path like "personalization_angles[0].fact"),
      "suggested_fix": string or null (how to fix it)
    }
  ],
  "patched_json": object or null (the fixed JSON if you can fix all errors)
}

REVIEW CRITERIA:
1. UNSOURCED CLAIMS: Statements presented as facts but not marked as assumptions
2. MISSING FIELDS: Required fields that are empty or missing
3. TONE: Professional B2B language, not overly salesy or casual
4. ACCURACY: No fabricated statistics, quotes, or specific details
5. COMPLETENESS: All sections adequately addressed

SEVERITY LEVELS:
- error: Must be fixed before use (unsourced claims, missing required fields)
- warning: Should be reviewed (tone issues, weak content)
- suggestion: Optional improvements

RULES:
1. Output ONLY valid JSON - no markdown, no explanations
2. If you can fix all errors, include patched_json with the corrected version
3. Be specific about what's wrong and how to fix it
4. Mark passed: true only if there are no errors"""

    # Build user prompt
    import json as json_module
    from datetime import datetime as dt

    def json_serializer(obj):
        """Handle non-serializable types."""
        if isinstance(obj, dt):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    user_parts = [
        f"Review this {artifact_type} output for quality issues:",
        f"\n\n```json\n{json_module.dumps(output_json, indent=2, default=json_serializer)}\n```",
    ]

    if constraints:
        user_parts.append(
            f"\n\nConstraints to enforce:\n{json_module.dumps(constraints, indent=2)}"
        )

    if evidence_summary:
        user_parts.append(f"\n\nAvailable evidence:\n{evidence_summary}")
    else:
        user_parts.append(
            "\n\nNo sources were provided - all specific claims should be marked as assumptions."
        )

    user_parts.append("\n\nOutput your review as JSON:")

    user_prompt = "".join(user_parts)

    return system_prompt, user_prompt


# Constraints templates for each artifact type
ARTIFACT_CONSTRAINTS = {
    "research_brief": {
        "required_fields": [
            "company",
            "snapshot",
            "pains",
            "triggers",
            "competitors",
            "personalization_angles",
        ],
        "min_items": {
            "pains": 2,
            "triggers": 1,
            "competitors": 1,
            "personalization_angles": 2,
        },
        "rules": [
            "All personalization angles without sources must have is_assumption: true",
            "Snapshot should be 2-3 sentences",
            "No fabricated statistics or quotes",
        ],
    },
    "target_map": {
        "required_fields": ["company", "personas"],
        "min_items": {
            "personas": 3,
        },
        "rules": [
            "Must include at least one economic_buyer",
            "Must include at least one champion",
            "All personas without verification must have is_assumption: true",
        ],
    },
    "outreach": {
        "required_fields": [
            "company",
            "persona",
            "channel",
            "variants",
            "sequence_steps",
            "objection_responses",
        ],
        "min_items": {
            "variants": 1,
            "sequence_steps": 3,
        },
        "rules": [
            "Email body should be under 150 words",
            "LinkedIn message should be under 100 words",
            "No clickbait subject lines",
            "Conversational peer-to-peer tone",
        ],
    },
    "meeting_prep": {
        "required_fields": [
            "company",
            "meeting_type",
            "agenda",
            "questions",
            "stakeholder_map",
            "listen_for_signals",
            "close_plan",
        ],
        "min_items": {
            "agenda": 4,
            "questions": 4,
            "listen_for_signals": 3,
        },
        "rules": [
            "Agenda items should include time estimates",
            "Questions should be open-ended",
            "Close plan should be specific and actionable",
        ],
    },
    "followup": {
        "required_fields": [
            "company",
            "meeting_date",
            "summary",
            "next_steps",
            "tasks",
            "crm_notes",
        ],
        "min_items": {
            "next_steps": 3,
            "tasks": 2,
        },
        "rules": [
            "Summary should be 2-4 sentences",
            "Tasks must have owner and due date",
            "Next steps should be specific and actionable",
        ],
    },
}


def get_constraints_for_artifact(artifact_type: str) -> Dict[str, Any]:
    """Get constraints for a specific artifact type.

    Args:
        artifact_type: The artifact type

    Returns:
        Constraints dictionary
    """
    return ARTIFACT_CONSTRAINTS.get(artifact_type, {})

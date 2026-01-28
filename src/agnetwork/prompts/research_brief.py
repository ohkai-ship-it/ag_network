"""Prompt builder for research brief generation."""

from typing import Any, Dict, List, Tuple


def build_research_brief_prompt(
    company: str,
    snapshot: str,
    pains: List[str],
    triggers: List[str],
    competitors: List[str],
    sources: List[Dict[str, Any]] | None = None,
    require_evidence: bool = False,
) -> Tuple[str, str]:
    """Build system and user prompts for research brief generation.

    Args:
        company: Company name
        snapshot: Company description/snapshot
        pains: List of known pain points
        triggers: List of trigger events
        competitors: List of competitors
        sources: Optional list of source documents
        require_evidence: M8 - If True, non-assumptions must include verbatim quotes

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    # M8: Enhanced schema with evidence snippets
    if require_evidence:
        schema_example = """{
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
      "source_ids": [string] (list of source IDs used, empty if assumption),
      "evidence": [
        {
          "source_id": string (must match a provided source ID),
          "quote": string (EXACT verbatim quote copied from source, <=220 chars)
        }
      ] (required if is_assumption=false, empty array if assumption)
    }
  ] (required, list of 2-5 angles)
}"""
        evidence_rules = """EVIDENCE RULES (M8 - CRITICAL - READ CAREFULLY):
1. If a fact comes from sources, set is_assumption: false, list source_ids, AND include evidence quotes
2. QUOTES MUST BE COPIED CHARACTER-FOR-CHARACTER from the source text - do NOT paraphrase or modify
3. Copy the quote EXACTLY as it appears, including German characters (ü, ö, ä, ß) and punctuation
4. If you cannot copy a quote EXACTLY verbatim, mark the fact as is_assumption: true instead
5. NEVER translate, summarize, or rephrase - the quote must be a literal substring of the source
6. Quotes should be <=220 characters, prefer complete sentences
7. If no source supports the fact with an exact quote, set is_assumption: true, source_ids: [], evidence: []
8. ONLY reference source IDs that were provided to you
9. Do NOT invent specific statistics, quotes, or citations

EXAMPLE - If source contains: "Nach fast vier Jahrzehnten am Markt sind wir heute deutscher Marktführer."
CORRECT quote: "Nach fast vier Jahrzehnten am Markt sind wir heute deutscher Marktführer."
WRONG quote: "Nach fast vier Jahren am Markt..." (changed word = INVALID)"""
    else:
        schema_example = """{
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
}"""
        evidence_rules = """EVIDENCE RULES:
1. If a fact comes from one of the provided sources, set is_assumption: false and list source IDs in source_ids
2. If no source supports the fact, set is_assumption: true and source_ids: []
3. ONLY reference source IDs that were provided to you (e.g., [1], [2])
4. Do NOT invent specific statistics, quotes, or citations"""

    system_prompt = f"""You are an expert B2B sales research analyst. Your task is to generate a comprehensive account research brief for sales teams.

OUTPUT FORMAT:
You must output ONLY valid JSON matching this exact schema:
{schema_example}

{evidence_rules}

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
            content = source.get("content", "")[:2000]  # M8: Increased to 2000 chars for evidence extraction
            user_parts.append(f"\n[{source_id}] {title}:\n{content}")

        if require_evidence:
            user_parts.append("\n\nIMPORTANT: For non-assumption facts, include verbatim quotes from sources in the 'evidence' array.")
    else:
        user_parts.append("\n\nNo sources provided - ALL insights will be assumptions. Set is_assumption: true and source_ids: [] for all angles.")

    user_parts.append("\n\nOutput the research brief as JSON:")

    user_prompt = "".join(user_parts)

    return system_prompt, user_prompt


# JSON schema for documentation (M8: Updated with evidence)
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
                    "evidence": {
                        "type": "array",
                        "description": "M8: Required if is_assumption=false",
                        "items": {
                            "type": "object",
                            "required": ["source_id", "quote"],
                            "properties": {
                                "source_id": {"type": "string"},
                                "url": {"type": "string"},
                                "quote": {"type": "string", "maxLength": 220},
                                "start_char": {"type": "integer"},
                                "end_char": {"type": "integer"},
                            },
                        },
                    },
                },
            },
        },
    },
}

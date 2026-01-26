"""Prompt library for LLM-assisted BD artifact generation.

This module provides prompt builders for each BD skill:
- research_brief: Account research
- target_map: Prospect personas
- outreach: Message drafts
- meeting_prep: Meeting preparation
- followup: Post-meeting follow-up
- critic: Quality review pass

Each prompt builder produces a system/user message pair optimized for
generating valid, structured JSON output.
"""

from agnetwork.prompts.critic import CriticResult, build_critic_prompt
from agnetwork.prompts.followup import build_followup_prompt
from agnetwork.prompts.meeting_prep import build_meeting_prep_prompt
from agnetwork.prompts.outreach import build_outreach_prompt
from agnetwork.prompts.research_brief import build_research_brief_prompt
from agnetwork.prompts.target_map import build_target_map_prompt

__all__ = [
    "build_research_brief_prompt",
    "build_target_map_prompt",
    "build_outreach_prompt",
    "build_meeting_prep_prompt",
    "build_followup_prompt",
    "build_critic_prompt",
    "CriticResult",
]

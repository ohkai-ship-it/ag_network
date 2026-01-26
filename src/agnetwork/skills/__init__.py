"""Skills package initialization.

This module imports and registers all available skills.
Skills are auto-registered via the @register_skill decorator.
"""

# Import skills to trigger registration
from agnetwork.skills.followup import FollowupSkill
from agnetwork.skills.meeting_prep import MeetingPrepSkill
from agnetwork.skills.outreach import OutreachSkill
from agnetwork.skills.research_brief import ResearchBriefSkill
from agnetwork.skills.target_map import TargetMapSkill

__all__ = [
    "ResearchBriefSkill",
    "TargetMapSkill",
    "OutreachSkill",
    "MeetingPrepSkill",
    "FollowupSkill",
]

"""Skills package initialization.

This module imports and registers all available skills.
Skills are auto-registered via the @register_skill decorator.
"""

# Import BD skills to trigger registration
from agnetwork.skills.followup import FollowupSkill
from agnetwork.skills.meeting_prep import MeetingPrepSkill
from agnetwork.skills.outreach import OutreachSkill

# Import Personal Ops skills (M7)
from agnetwork.skills.personal_ops import (
    ErrandListSkill,
    TravelOutlineSkill,
    WeeklyPlanSkill,
)
from agnetwork.skills.research_brief import ResearchBriefSkill
from agnetwork.skills.target_map import TargetMapSkill

# Import Work Ops skills (M7)
from agnetwork.skills.work_ops import (
    DecisionLogSkill,
    MeetingSummarySkill,
    StatusUpdateSkill,
)

__all__ = [
    # BD Skills
    "ResearchBriefSkill",
    "TargetMapSkill",
    "OutreachSkill",
    "MeetingPrepSkill",
    "FollowupSkill",
    # Work Ops Skills
    "MeetingSummarySkill",
    "StatusUpdateSkill",
    "DecisionLogSkill",
    # Personal Ops Skills
    "WeeklyPlanSkill",
    "ErrandListSkill",
    "TravelOutlineSkill",
]

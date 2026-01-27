"""Work Ops skill pack for professional productivity.

Skills for meeting summaries, status updates, and decision logs.
"""

from agnetwork.skills.work_ops.decision_log import DecisionLogSkill
from agnetwork.skills.work_ops.meeting_summary import MeetingSummarySkill
from agnetwork.skills.work_ops.status_update import StatusUpdateSkill

__all__ = [
    "MeetingSummarySkill",
    "StatusUpdateSkill",
    "DecisionLogSkill",
]

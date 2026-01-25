"""Tests for data models."""


from bdcopilot.models.core import OutreachDraft, ResearchBrief, TargetMap


def test_research_brief_model():
    """Test ResearchBrief Pydantic model."""
    brief = ResearchBrief(
        company="TechCorp",
        snapshot="Leading SaaS platform",
        pains=["Scalability", "Integration complexity"],
        triggers=["Quarterly earnings call", "New CTO hired"],
        competitors=["CompetitorA", "CompetitorB"],
        personalization_angles=[
            {"name": "Growth", "fact": "Expanding to Europe", "is_assumption": False},
            {"name": "Cost", "fact": "Seeking cost reduction", "is_assumption": True},
        ],
    )

    assert brief.company == "TechCorp"
    assert len(brief.pains) == 2
    assert brief.created_at is not None


def test_target_map_model():
    """Test TargetMap model."""
    target_map = TargetMap(
        company="TechCorp",
        personas=[
            {"title": "VP Sales", "role": "economic_buyer"},
            {"title": "IT Director", "role": "blocker"},
        ],
    )

    assert target_map.company == "TechCorp"
    assert len(target_map.personas) == 2


def test_outreach_draft_model():
    """Test OutreachDraft model."""
    outreach = OutreachDraft(
        company="TechCorp",
        persona="VP Sales",
        variants=[
            {
                "channel": "email",
                "subject_or_hook": "Partnership opportunity",
                "body": "Hi there...",
            }
        ],
        sequence_steps=["Send initial email", "Follow up after 3 days"],
        objection_responses={"No budget": "Let's schedule a conversation..."},
    )

    assert outreach.company == "TechCorp"
    assert len(outreach.variants) == 1
    assert "No budget" in outreach.objection_responses

"""Tests for skills."""

from agnetwork.skills.research_brief import ResearchBriefSkill


def test_research_brief_skill_generation():
    """Test that ResearchBriefSkill generates valid output."""
    skill = ResearchBriefSkill()

    markdown, json_data = skill.generate(
        company="TechCorp",
        snapshot="Leading SaaS provider",
        pains=["Scaling issues", "Integration complexity"],
        triggers=["New funding", "Market expansion"],
        competitors=["CompetitorA", "CompetitorB"],
        personalization_angles=[
            {
                "name": "Growth",
                "fact": "Expanding into APAC",
                "is_assumption": False,
            },
        ],
    )

    # Check markdown output
    assert "# Account Research Brief: TechCorp" in markdown
    assert "Snapshot" in markdown
    assert "Key Pains" in markdown
    assert "Triggers" in markdown
    assert "Competitors" in markdown
    assert "Personalization Angles" in markdown
    assert "Growth" in markdown

    # Check JSON output
    assert json_data["company"] == "TechCorp"
    assert len(json_data["pains"]) == 2
    assert json_data["snapshot"] == "Leading SaaS provider"

    # Check assumptions are marked
    assert any("ASSUMPTION" in line for line in markdown.split("\n")) or not any(
        d["is_assumption"] for d in json_data["personalization_angles"]
    )

"""Tests for sequence builder (Task G).

Verifies that:
- SequencePlan produces deterministic steps
- Sequence steps appear as planned activities
- Sequences integrate with export packages
"""

from datetime import datetime, timedelta, timezone

from agnetwork.crm.models import ActivityType
from agnetwork.crm.sequence import (
    DEFAULT_SEQUENCE_STEPS,
    LINKEDIN_SEQUENCE_STEPS,
    SequenceBuilder,
    SequencePlan,
    SequenceStep,
)


class TestSequenceStep:
    """Tests for SequenceStep."""

    def test_create_step(self):
        """Can create a sequence step."""
        step = SequenceStep(
            step_number=1,
            day_offset=0,
            activity_type=ActivityType.EMAIL,
            subject_template="Test Subject for {company}",
            body_template="Hello {persona}, this is about {company}.",
            notes="Initial outreach",
        )
        assert step.step_number == 1
        assert step.day_offset == 0
        assert step.activity_type == ActivityType.EMAIL

    def test_render_step(self):
        """Step templates render with variables."""
        step = SequenceStep(
            step_number=1,
            day_offset=0,
            activity_type=ActivityType.EMAIL,
            subject_template="Partnership opportunity with {company}",
            body_template="Hi {persona}, I'd like to discuss {company}.",
        )

        subject, body = step.render(company="Acme", persona="John")

        assert "Acme" in subject
        assert "John" in body
        assert "Acme" in body


class TestSequencePlan:
    """Tests for SequencePlan."""

    def test_create_plan(self):
        """Can create a sequence plan."""
        plan = SequencePlan(
            sequence_id="seq_123",
            name="Test Sequence",
            company="TestCorp",
            persona="VP Sales",
            account_id="acc_123",
            steps=DEFAULT_SEQUENCE_STEPS[:2],  # Use first 2 steps
            channel="email",
        )
        assert plan.sequence_id == "seq_123"
        assert len(plan.steps) == 2

    def test_get_scheduled_date(self):
        """Scheduled dates calculated from start_date + offset."""
        start = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        plan = SequencePlan(
            sequence_id="seq_dates",
            name="Date Test",
            company="TestCorp",
            persona="VP",
            account_id="acc_test",
            steps=[
                SequenceStep(1, 0, ActivityType.EMAIL, "Sub1", "Body1"),
                SequenceStep(2, 3, ActivityType.EMAIL, "Sub2", "Body2"),
                SequenceStep(3, 7, ActivityType.EMAIL, "Sub3", "Body3"),
            ],
            start_date=start,
        )

        assert plan.get_scheduled_date(plan.steps[0]) == start
        assert plan.get_scheduled_date(plan.steps[1]) == start + timedelta(days=3)
        assert plan.get_scheduled_date(plan.steps[2]) == start + timedelta(days=7)

    def test_to_activities(self):
        """Plan converts to planned activities."""
        start = datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc)
        plan = SequencePlan(
            sequence_id="seq_act",
            name="Activity Test",
            company="ActCorp",
            persona="CTO",
            account_id="acc_act",
            contact_id="con_act",
            steps=DEFAULT_SEQUENCE_STEPS[:2],
            start_date=start,
            channel="email",
            run_id="test_run_123",
            source_ids=["src_1", "src_2"],
        )

        activities = plan.to_activities()

        assert len(activities) == 2

        # Check first activity
        act1 = activities[0]
        assert act1.is_planned is True
        assert act1.scheduled_for == start
        assert act1.sequence_step == 1
        assert act1.sequence_name == "Activity Test"
        assert act1.account_id == "acc_act"
        assert act1.contact_id == "con_act"
        assert act1.run_id == "test_run_123"
        assert act1.source_ids == ["src_1", "src_2"]

        # Check second activity
        act2 = activities[1]
        assert act2.scheduled_for == start + timedelta(days=3)
        assert act2.sequence_step == 2


class TestSequenceBuilder:
    """Tests for SequenceBuilder."""

    def test_build_from_outreach(self):
        """Builder creates plan from outreach artifact."""
        outreach = {
            "company": "BuildCorp",
            "persona": "VP Engineering",
            "channel": "email",
            "subject_or_hook": "Partnership with BuildCorp",
            "body": "Initial outreach message",
            "sequence_steps": [
                "Initial outreach (Day 0)",
                "Follow-up (Day 3)",
                "Final attempt (Day 7)",
            ],
        }

        builder = SequenceBuilder(mode="manual")
        plan = builder.build_from_outreach(
            outreach_artifact=outreach,
            account_id="acc_build",
            contact_id="con_build",
            run_id="run_build",
        )

        assert plan.company == "BuildCorp"
        assert plan.persona == "VP Engineering"
        assert plan.channel == "email"
        assert len(plan.steps) == 3

    def test_build_from_outreach_uses_defaults(self):
        """Builder uses default steps when artifact has none."""
        outreach = {
            "company": "DefaultCorp",
            "persona": "CEO",
            "channel": "email",
        }

        builder = SequenceBuilder(mode="manual")
        plan = builder.build_from_outreach(
            outreach_artifact=outreach,
            account_id="acc_default",
        )

        # Should use DEFAULT_SEQUENCE_STEPS
        assert len(plan.steps) == len(DEFAULT_SEQUENCE_STEPS)

    def test_build_linkedin_sequence(self):
        """Builder uses LinkedIn steps for linkedin channel."""
        outreach = {
            "company": "LinkedInCorp",
            "persona": "Director",
            "channel": "linkedin",
        }

        builder = SequenceBuilder(mode="manual")
        plan = builder.build_from_outreach(
            outreach_artifact=outreach,
            account_id="acc_li",
        )

        # Should use LINKEDIN_SEQUENCE_STEPS
        assert len(plan.steps) == len(LINKEDIN_SEQUENCE_STEPS)
        assert plan.steps[0].activity_type == ActivityType.LINKEDIN

    def test_build_custom_plan(self):
        """Builder can create custom plans."""
        custom_steps = [
            SequenceStep(1, 0, ActivityType.EMAIL, "Custom 1", "Body 1"),
            SequenceStep(2, 5, ActivityType.EMAIL, "Custom 2", "Body 2"),
        ]

        builder = SequenceBuilder()
        plan = builder.build_custom(
            company="CustomCorp",
            persona="Manager",
            account_id="acc_custom",
            steps=custom_steps,
        )

        assert len(plan.steps) == 2
        assert plan.steps[1].day_offset == 5


class TestSequenceTemplates:
    """Tests for default sequence templates."""

    def test_default_email_sequence_exists(self):
        """Default email sequence template exists."""
        assert len(DEFAULT_SEQUENCE_STEPS) >= 3

        # Check step progression
        days = [s.day_offset for s in DEFAULT_SEQUENCE_STEPS]
        assert days == sorted(days)  # Days should be in order

    def test_linkedin_sequence_exists(self):
        """LinkedIn sequence template exists."""
        assert len(LINKEDIN_SEQUENCE_STEPS) >= 2

        # All steps should be LinkedIn type
        for step in LINKEDIN_SEQUENCE_STEPS:
            assert step.activity_type == ActivityType.LINKEDIN


class TestSequenceDeterminism:
    """Tests for deterministic sequence generation."""

    def test_same_input_same_output(self):
        """Same inputs produce same sequence plan."""
        outreach = {
            "company": "DeterministicCorp",
            "persona": "VP",
            "channel": "email",
        }
        start = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)

        builder = SequenceBuilder(mode="manual")

        plan1 = builder.build_from_outreach(
            outreach_artifact=outreach,
            account_id="acc_det",
            start_date=start,
        )
        plan2 = builder.build_from_outreach(
            outreach_artifact=outreach,
            account_id="acc_det",
            start_date=start,
        )

        # Steps should be identical
        assert len(plan1.steps) == len(plan2.steps)
        for s1, s2 in zip(plan1.steps, plan2.steps):
            assert s1.step_number == s2.step_number
            assert s1.day_offset == s2.day_offset
            assert s1.subject_template == s2.subject_template

    def test_activities_deterministic(self):
        """Generated activities are deterministic."""
        start = datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)

        plan = SequencePlan(
            sequence_id="det_act",
            name="Determinism Test",
            company="DetCorp",
            persona="VP",
            account_id="acc_det",
            steps=DEFAULT_SEQUENCE_STEPS[:2],
            start_date=start,
        )

        activities1 = plan.to_activities()
        activities2 = plan.to_activities()

        assert len(activities1) == len(activities2)
        for a1, a2 in zip(activities1, activities2):
            assert a1.scheduled_for == a2.scheduled_for
            assert a1.sequence_step == a2.sequence_step

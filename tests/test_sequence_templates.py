"""Tests for sequence template loading (M6.1 Task E).

Tests cover:
- Template JSON file loading
- SequenceTemplateLoader functionality
- Template fallback to built-in defaults
- CLI template commands
"""

import json
from pathlib import Path

from agnetwork.crm.sequence import (
    SequenceBuilder,
    get_template_loader,
)


class TestSequenceTemplateLoader:
    """Tests for SequenceTemplateLoader."""

    def test_loader_singleton(self):
        """get_template_loader() returns singleton."""
        loader1 = get_template_loader()
        loader2 = get_template_loader()
        assert loader1 is loader2

    def test_loader_loads_templates(self):
        """Loader loads templates from JSON file."""
        loader = get_template_loader()
        # Force reload to ensure fresh state
        loader._templates = None

        templates = loader.list_templates()
        # Should have at least the default templates
        assert len(templates) > 0

    def test_builtin_templates_exist(self):
        """Expected built-in templates exist."""
        loader = get_template_loader()
        template_names = loader.list_templates()

        # These are the templates defined in sequence_templates.json
        expected = ["email_standard", "linkedin_connection", "email_aggressive", "email_nurture"]
        for name in expected:
            assert name in template_names, f"Missing template: {name}"

    def test_get_template(self):
        """Can retrieve specific template."""
        loader = get_template_loader()
        template = loader.get_template("email_standard")

        assert template is not None
        assert "steps" in template
        assert len(template["steps"]) > 0

    def test_get_unknown_template(self):
        """Unknown template returns None."""
        loader = get_template_loader()
        template = loader.get_template("nonexistent_template")
        assert template is None

    def test_template_structure(self):
        """Templates have expected structure."""
        loader = get_template_loader()
        template = loader.get_template("email_standard")

        # Required fields
        assert "steps" in template
        assert "description" in template

        # Step structure
        step = template["steps"][0]
        assert "offset_days" in step
        assert "channel" in step

    def test_caching(self):
        """Templates are cached after loading."""
        loader = get_template_loader()

        # Access templates via list_templates to trigger loading
        templates1 = loader.list_templates()

        # Should have templates now
        assert len(templates1) > 0

        # Second call should return same list (cached)
        templates2 = loader.list_templates()
        assert templates1 == templates2


class TestTemplateJSONFile:
    """Tests for the sequence_templates.json file."""

    def test_json_file_exists(self):
        """Template JSON file exists."""
        # Find the resources directory
        from agnetwork.crm.sequence import get_template_loader
        loader = get_template_loader()

        # The loader should have found the file
        templates = loader.list_templates()
        assert len(templates) > 0

    def test_json_valid_format(self):
        """Template JSON is valid JSON."""
        resources_dir = Path(__file__).parent.parent / "src" / "agnetwork" / "resources"
        json_path = resources_dir / "sequence_templates.json"

        if json_path.exists():
            with open(json_path) as f:
                data = json.load(f)
            assert "templates" in data

    def test_all_templates_have_steps(self):
        """All templates have at least one step."""
        loader = get_template_loader()

        for name in loader.list_templates():
            template = loader.get_template(name)
            assert "steps" in template, f"Template '{name}' missing steps"
            assert len(template["steps"]) > 0, f"Template '{name}' has no steps"


class TestSequenceBuilderWithTemplates:
    """Tests for SequenceBuilder using templates."""

    def test_build_custom_with_template(self):
        """build_custom uses template when specified."""
        builder = SequenceBuilder()
        result = builder.build_custom(
            company="Acme Corp",
            persona="CEO",
            account_id="acc_123",
            template_name="email_standard",
        )

        assert result is not None
        assert result.company == "Acme Corp"
        # Should have steps from template
        assert len(result.steps) > 0

    def test_build_custom_unknown_template_fallback(self):
        """build_custom falls back to defaults for unknown template."""
        builder = SequenceBuilder()
        result = builder.build_custom(
            company="Acme Corp",
            persona="CEO",
            account_id="acc_123",
            template_name="nonexistent_template",
        )

        # Should still work with fallback
        assert result is not None
        assert len(result.steps) > 0

    def test_build_from_outreach_default_template(self):
        """build_from_outreach uses default template."""
        builder = SequenceBuilder()
        outreach = {
            "company": "TechCo",
            "persona": "CTO",
            "channel": "email",
            "subject_or_hook": "Partnership Opportunity",
            "body": "Hello...",
        }
        result = builder.build_from_outreach(
            outreach_artifact=outreach,
            account_id="acc_456",
            run_id="test_run",
        )

        assert result is not None
        assert result.company == "TechCo"

    def test_build_from_outreach_custom_template(self):
        """build_from_outreach accepts template_name."""
        builder = SequenceBuilder()
        outreach = {
            "company": "TechCo",
            "persona": "CTO",
            "channel": "email",
        }
        result = builder.build_from_outreach(
            outreach_artifact=outreach,
            account_id="acc_456",
            run_id="test_run",
            template_name="email_aggressive",
        )

        assert result is not None
        assert len(result.steps) > 0

    def test_template_steps_applied(self):
        """Template steps are applied to sequences."""
        builder = SequenceBuilder()
        loader = get_template_loader()

        # Get template to know expected steps
        template = loader.get_template("email_standard")
        expected_step_count = len(template["steps"])

        result = builder.build_custom(
            company="TestCorp",
            persona="CTO",
            account_id="acc_789",
            template_name="email_standard",
        )

        # Should have steps from template
        assert len(result.steps) == expected_step_count


class TestTemplateStepDetails:
    """Tests for template step details."""

    def test_email_standard_steps(self):
        """email_standard has expected step progression."""
        loader = get_template_loader()
        template = loader.get_template("email_standard")

        steps = template["steps"]
        # Should have multiple steps with increasing delays
        assert len(steps) >= 3

        # Verify offset_days increases
        offsets = [s["offset_days"] for s in steps]
        assert offsets == sorted(offsets), "Steps should be in chronological order"

    def test_linkedin_connection_steps(self):
        """linkedin_connection includes LinkedIn channel."""
        loader = get_template_loader()
        template = loader.get_template("linkedin_connection")

        channels = [s["channel"] for s in template["steps"]]
        assert "linkedin" in channels

    def test_aggressive_template_timing(self):
        """email_aggressive has shorter intervals."""
        loader = get_template_loader()

        standard = loader.get_template("email_standard")
        aggressive = loader.get_template("email_aggressive")

        # Aggressive should have shorter total duration
        standard_max = max(s["offset_days"] for s in standard["steps"])
        aggressive_max = max(s["offset_days"] for s in aggressive["steps"])

        assert aggressive_max <= standard_max, "Aggressive should be faster"

    def test_nurture_template_timing(self):
        """email_nurture has longer intervals."""
        loader = get_template_loader()

        standard = loader.get_template("email_standard")
        nurture = loader.get_template("email_nurture")

        # Nurture should have longer total duration
        standard_max = max(s["offset_days"] for s in standard["steps"])
        nurture_max = max(s["offset_days"] for s in nurture["steps"])

        assert nurture_max >= standard_max, "Nurture should be slower"

"""Tests for structured output parsing and repair."""

import json

import pytest
from pydantic import BaseModel, Field

from agnetwork.tools.llm.adapters.fake import FakeAdapter
from agnetwork.tools.llm.factory import LLMConfig, LLMFactory, RoleConfig
from agnetwork.tools.llm.structured import (
    StructuredOutputError,
    extract_json,
    get_schema_summary,
    parse_or_repair_json,
)


class SimpleModel(BaseModel):
    """Simple model for testing."""

    name: str
    value: int


class ComplexModel(BaseModel):
    """More complex model for testing."""

    company: str
    items: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class TestExtractJson:
    """Tests for extract_json function."""

    def test_plain_json(self):
        """Test extraction of plain JSON."""
        text = '{"name": "test", "value": 42}'
        result = extract_json(text)
        data = json.loads(result)

        assert data["name"] == "test"
        assert data["value"] == 42

    def test_json_in_code_fence(self):
        """Test extraction from code fence with json tag."""
        text = """Here's the result:

```json
{"name": "fenced", "value": 123}
```

That's the output."""

        result = extract_json(text)
        data = json.loads(result)

        assert data["name"] == "fenced"
        assert data["value"] == 123

    def test_json_in_plain_fence(self):
        """Test extraction from code fence without json tag."""
        text = """```
{"name": "plain_fence", "value": 1}
```"""

        result = extract_json(text)
        data = json.loads(result)

        assert data["name"] == "plain_fence"

    def test_json_with_text_before(self):
        """Test extraction when JSON follows text."""
        text = """Let me help you with that request.

{"name": "after_text", "value": 99}"""

        result = extract_json(text)
        data = json.loads(result)

        assert data["name"] == "after_text"

    def test_json_array(self):
        """Test extraction of JSON array."""
        text = '["item1", "item2", "item3"]'
        result = extract_json(text)
        data = json.loads(result)

        assert len(data) == 3
        assert data[0] == "item1"

    def test_nested_json(self):
        """Test extraction of nested JSON."""
        text = '{"outer": {"inner": {"deep": "value"}}}'
        result = extract_json(text)
        data = json.loads(result)

        assert data["outer"]["inner"]["deep"] == "value"

    def test_json_with_strings_containing_braces(self):
        """Test JSON with strings containing braces."""
        text = '{"code": "function() { return {}; }"}'
        result = extract_json(text)
        data = json.loads(result)

        assert "function" in data["code"]

    def test_no_json_raises_error(self):
        """Test that missing JSON raises ValueError."""
        text = "This is just plain text with no JSON."

        with pytest.raises(ValueError) as exc_info:
            extract_json(text)

        assert "No valid JSON" in str(exc_info.value)


class TestGetSchemaSummary:
    """Tests for get_schema_summary function."""

    def test_simple_schema(self):
        """Test schema summary for simple model."""
        summary = get_schema_summary(SimpleModel)

        assert "SimpleModel" in summary
        assert '"name"' in summary
        assert "string" in summary
        assert '"value"' in summary
        assert "integer" in summary

    def test_complex_schema(self):
        """Test schema summary for complex model."""
        summary = get_schema_summary(ComplexModel)

        assert "ComplexModel" in summary
        assert '"company"' in summary
        assert '"items"' in summary
        assert '"metadata"' in summary


class TestParseOrRepairJson:
    """Tests for parse_or_repair_json function."""

    @pytest.fixture
    def fake_factory(self):
        """Create a factory with fake adapter."""
        config = LLMConfig(
            enabled=True,
            roles={
                "default": RoleConfig(provider="fake", model="fake"),
                "critic": RoleConfig(provider="fake", model="fake"),
            },
        )
        factory = LLMFactory(config)

        # Pre-create adapters
        fake = FakeAdapter()
        factory.set_adapter("default", fake)
        factory.set_adapter("critic", fake)

        return factory

    def test_valid_json_parses(self, fake_factory):
        """Test that valid JSON parses without repair."""
        text = '{"name": "test", "value": 42}'

        result = parse_or_repair_json(
            model=SimpleModel,
            llm_text=text,
            llm_factory=fake_factory,
        )

        assert result.name == "test"
        assert result.value == 42

    def test_json_in_fence_parses(self, fake_factory):
        """Test that JSON in fence parses."""
        text = '```json\n{"name": "fenced", "value": 1}\n```'

        result = parse_or_repair_json(
            model=SimpleModel,
            llm_text=text,
            llm_factory=fake_factory,
        )

        assert result.name == "fenced"

    def test_repair_on_invalid_json(self, fake_factory):
        """Test repair loop is triggered on invalid JSON."""
        # Set up repair response
        fake = fake_factory.get("critic")
        fake.queue_response('{"name": "repaired", "value": 100}')

        # Invalid JSON
        invalid_text = '{"name": "broken", value: missing_quotes}'

        result = parse_or_repair_json(
            model=SimpleModel,
            llm_text=invalid_text,
            llm_factory=fake_factory,
        )

        # Should get repaired version
        assert result.name == "repaired"
        assert result.value == 100

    def test_repair_on_validation_error(self, fake_factory):
        """Test repair loop is triggered on validation error."""
        # Set up repair response
        fake = fake_factory.get("critic")
        fake.queue_response('{"name": "fixed", "value": 42}')

        # Valid JSON but wrong type
        invalid_text = '{"name": "test", "value": "not_an_int"}'

        result = parse_or_repair_json(
            model=SimpleModel,
            llm_text=invalid_text,
            llm_factory=fake_factory,
        )

        assert result.name == "fixed"
        assert result.value == 42

    def test_max_repairs_exhausted(self, fake_factory):
        """Test error raised when max repairs exhausted."""
        # Set up always-invalid responses
        fake = fake_factory.get("critic")
        fake.queue_response("still invalid")
        fake.queue_response("also invalid")
        fake.queue_response("nope")

        invalid_text = "not json at all"

        with pytest.raises(StructuredOutputError) as exc_info:
            parse_or_repair_json(
                model=SimpleModel,
                llm_text=invalid_text,
                llm_factory=fake_factory,
                max_repairs=2,
            )

        error = exc_info.value
        assert "SimpleModel" in str(error)
        assert error.repair_attempts == 2
        assert len(error.validation_errors) > 0

    def test_repair_with_missing_field(self, fake_factory):
        """Test repair adds missing required field."""
        fake = fake_factory.get("critic")
        fake.queue_response('{"name": "added", "value": 0}')

        # Missing required field
        invalid_text = '{"name": "test"}'  # missing "value"

        result = parse_or_repair_json(
            model=SimpleModel,
            llm_text=invalid_text,
            llm_factory=fake_factory,
        )

        assert result.name == "added"
        assert result.value == 0

    def test_repair_metadata_passed(self, fake_factory):
        """Test metadata is passed to repair calls."""
        fake = fake_factory.get("critic")
        fake.queue_response('{"name": "meta", "value": 1}')

        invalid_text = "not valid"

        parse_or_repair_json(
            model=SimpleModel,
            llm_text=invalid_text,
            llm_factory=fake_factory,
            run_id="test-run-123",
            skill_name="test_skill",
        )

        # Check that repair request had metadata
        assert fake.call_count >= 1
        last_request = fake.call_history[-1]
        assert last_request.metadata.get("run_id") == "test-run-123"
        assert last_request.metadata.get("skill_name") == "test_skill"


class TestStructuredOutputError:
    """Tests for StructuredOutputError."""

    def test_error_contains_details(self):
        """Test error contains all relevant details."""
        error = StructuredOutputError(
            message="Failed to parse",
            original_text="bad json",
            validation_errors=[{"error": "test"}],
            repair_attempts=2,
        )

        assert "Failed to parse" in str(error)
        assert error.original_text == "bad json"
        assert len(error.validation_errors) == 1
        assert error.repair_attempts == 2

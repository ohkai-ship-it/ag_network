"""Tests for LLM adapters and factory."""

import os
from unittest.mock import patch

import pytest

from agnetwork.tools.llm.adapters.base import LLMAdapterError
from agnetwork.tools.llm.adapters.fake import (
    FAKE_RESEARCH_BRIEF,
    FAKE_TARGET_MAP,
    FakeAdapter,
)
from agnetwork.tools.llm.factory import LLMConfig, LLMFactory, RoleConfig
from agnetwork.tools.llm.types import LLMMessage, LLMRequest, LLMResponse


class TestLLMTypes:
    """Tests for LLM types."""

    def test_llm_message_creation(self):
        """Test LLMMessage can be created."""
        msg = LLMMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_llm_request_with_metadata(self):
        """Test LLMRequest metadata chaining."""
        request = LLMRequest(
            messages=[LLMMessage(role="user", content="Test")],
            metadata={"run_id": "test123"},
        )

        updated = request.with_metadata(skill="research", step_id="step1")

        assert updated.metadata["run_id"] == "test123"
        assert updated.metadata["skill"] == "research"
        assert updated.metadata["step_id"] == "step1"
        # Original unchanged
        assert "skill" not in request.metadata

    def test_llm_response_to_dict_truncates(self):
        """Test LLMResponse to_dict truncates long text."""
        long_text = "x" * 300
        response = LLMResponse(
            text=long_text,
            model="test-model",
            provider="fake",
        )

        result = response.to_dict()
        assert len(result["text"]) < len(long_text)
        assert result["text"].endswith("...")


class TestFakeAdapter:
    """Tests for FakeAdapter."""

    def test_default_response(self):
        """Test FakeAdapter returns default response."""
        adapter = FakeAdapter()
        request = LLMRequest(messages=[LLMMessage(role="user", content="anything")])

        response = adapter.complete(request)

        assert response.provider == "fake"
        assert response.text == '{"status": "ok"}'

    def test_custom_default_response(self):
        """Test FakeAdapter with custom default."""
        adapter = FakeAdapter(default_response='{"custom": true}')
        request = LLMRequest(messages=[LLMMessage(role="user", content="test")])

        response = adapter.complete(request)
        assert response.text == '{"custom": true}'

    def test_pattern_matching(self):
        """Test FakeAdapter pattern matching."""
        adapter = FakeAdapter()
        adapter.add_response("research", FAKE_RESEARCH_BRIEF)
        adapter.add_response("target", FAKE_TARGET_MAP)

        # Should match "research"
        request1 = LLMRequest(messages=[LLMMessage(role="user", content="Generate research brief")])
        response1 = adapter.complete(request1)
        assert "TestCorp" in response1.text

        # Should match "target"
        request2 = LLMRequest(messages=[LLMMessage(role="user", content="Create target map")])
        response2 = adapter.complete(request2)
        assert "personas" in response2.text

    def test_response_queue(self):
        """Test FakeAdapter FIFO queue."""
        adapter = FakeAdapter()
        adapter.queue_response('{"first": true}')
        adapter.queue_response('{"second": true}')

        request = LLMRequest(messages=[LLMMessage(role="user", content="test")])

        response1 = adapter.complete(request)
        assert "first" in response1.text

        response2 = adapter.complete(request)
        assert "second" in response2.text

    def test_call_tracking(self):
        """Test FakeAdapter tracks calls."""
        adapter = FakeAdapter()
        request1 = LLMRequest(messages=[LLMMessage(role="user", content="first")])
        request2 = LLMRequest(messages=[LLMMessage(role="user", content="second")])

        adapter.complete(request1)
        adapter.complete(request2)

        assert adapter.call_count == 2
        assert len(adapter.call_history) == 2
        assert "first" in adapter.call_history[0].messages[0].content
        assert "second" in adapter.call_history[1].messages[0].content

    def test_configured_failure(self):
        """Test FakeAdapter can be configured to fail."""
        adapter = FakeAdapter()
        adapter.set_should_fail(True, "Test error")

        request = LLMRequest(messages=[LLMMessage(role="user", content="test")])

        with pytest.raises(LLMAdapterError) as exc_info:
            adapter.complete(request)

        assert "Test error" in str(exc_info.value)

    def test_reset(self):
        """Test FakeAdapter reset."""
        adapter = FakeAdapter()
        adapter.add_response("test", '{"added": true}')
        adapter.queue_response('{"queued": true}')
        adapter.complete(LLMRequest(messages=[LLMMessage(role="user", content="x")]))

        adapter.reset()

        assert adapter.call_count == 0
        assert len(adapter.call_history) == 0
        # Pattern should be gone
        request = LLMRequest(messages=[LLMMessage(role="user", content="test")])
        response = adapter.complete(request)
        assert "added" not in response.text

    def test_response_function(self):
        """Test FakeAdapter with response function."""

        def dynamic_response(request: LLMRequest) -> str:
            content = request.messages[0].content
            return f'{{"echo": "{content[:20]}"}}'

        adapter = FakeAdapter()
        adapter.set_response_fn(dynamic_response)

        request = LLMRequest(messages=[LLMMessage(role="user", content="Hello world")])
        response = adapter.complete(request)

        assert "Hello world" in response.text

    def test_usage_stats(self):
        """Test FakeAdapter returns usage stats."""
        adapter = FakeAdapter()
        request = LLMRequest(messages=[LLMMessage(role="user", content="Hello world test")])

        response = adapter.complete(request)

        assert response.usage is not None
        assert response.usage.prompt_tokens > 0
        assert response.usage.completion_tokens > 0


class TestLLMConfig:
    """Tests for LLMConfig."""

    def test_default_values(self):
        """Test LLMConfig has sensible defaults."""
        # Clear env vars that might interfere
        with patch.dict(os.environ, {}, clear=True):
            config = LLMConfig.from_env()

        assert config.enabled is False
        assert config.default_provider == "anthropic"
        assert config.temperature == 0.7
        assert "default" in config.roles
        assert "critic" in config.roles

    def test_env_override(self):
        """Test LLMConfig reads from environment."""
        env = {
            "AG_LLM_ENABLED": "1",
            "AG_LLM_DEFAULT_PROVIDER": "openai",
            "AG_LLM_DEFAULT_MODEL": "gpt-4o",
            "AG_LLM_TEMPERATURE": "0.5",
            "AG_LLM_MAX_TOKENS": "8000",
        }

        with patch.dict(os.environ, env, clear=True):
            config = LLMConfig.from_env()

        assert config.enabled is True
        assert config.default_provider == "openai"
        assert config.default_model == "gpt-4o"
        assert config.temperature == 0.5
        assert config.max_tokens == 8000

    def test_role_config_fallback(self):
        """Test role configs fall back to defaults."""
        with patch.dict(os.environ, {}, clear=True):
            config = LLMConfig.from_env()

        # Critic should fall back to default provider/model
        assert config.roles["critic"].provider == config.default_provider
        assert config.roles["critic"].model == config.default_model


class TestLLMFactory:
    """Tests for LLMFactory."""

    def test_factory_disabled_by_default(self):
        """Test factory reports disabled when env not set."""
        with patch.dict(os.environ, {}, clear=True):
            factory = LLMFactory.from_env()

        assert factory.is_enabled is False

    def test_factory_enabled_with_env(self):
        """Test factory reports enabled when env set."""
        with patch.dict(os.environ, {"AG_LLM_ENABLED": "1"}, clear=True):
            factory = LLMFactory.from_env()

        assert factory.is_enabled is True

    def test_get_fake_adapter(self):
        """Test factory can create fake adapter."""
        config = LLMConfig(
            enabled=True,
            default_provider="fake",
            roles={"default": RoleConfig(provider="fake", model="fake-model")},
        )
        factory = LLMFactory(config)

        adapter = factory.get(role="default")

        assert adapter.provider == "fake"
        assert isinstance(adapter, FakeAdapter)

    def test_defaults_for_role(self):
        """Test factory returns role defaults."""
        config = LLMConfig(
            roles={
                "default": RoleConfig(provider="anthropic", model="claude-3"),
                "critic": RoleConfig(provider="openai", model="gpt-4"),
            }
        )
        factory = LLMFactory(config)

        default_config = factory.defaults_for("default")
        critic_config = factory.defaults_for("critic")

        assert default_config.provider == "anthropic"
        assert critic_config.provider == "openai"

    def test_unknown_role_falls_back(self):
        """Test unknown role falls back to default."""
        config = LLMConfig(
            roles={"default": RoleConfig(provider="fake", model="test")},
        )
        factory = LLMFactory(config)

        # Unknown role should get default config
        unknown_config = factory.defaults_for("extractor")
        assert unknown_config.provider == "fake"

    def test_set_adapter_for_testing(self):
        """Test factory allows setting adapters for testing."""
        factory = LLMFactory(LLMConfig())

        fake = FakeAdapter()
        fake.add_response("test", '{"mocked": true}')
        factory.set_adapter("default", fake)

        adapter = factory.get("default")
        request = LLMRequest(messages=[LLMMessage(role="user", content="test")])
        response = adapter.complete(request)

        # The adapter should return the configured response
        assert "mocked" in response.text or response.text == '{"mocked": true}'

    def test_unsupported_provider_error(self):
        """Test factory raises error for unsupported provider."""
        config = LLMConfig(
            roles={"default": RoleConfig(provider="unsupported", model="x")},
        )
        factory = LLMFactory(config)

        with pytest.raises(LLMAdapterError) as exc_info:
            factory.get("default")

        assert "unsupported" in str(exc_info.value).lower()


class TestRealAdaptersSkipped:
    """Tests for real adapters (skipped without API keys)."""

    @pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set")
    def test_anthropic_adapter_live(self):
        """Test Anthropic adapter with real API (manual run only)."""
        from agnetwork.tools.llm.adapters.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter()
        request = LLMRequest(
            messages=[LLMMessage(role="user", content="Say 'hello' and nothing else.")],
            max_tokens=10,
        )

        response = adapter.complete(request)

        assert "hello" in response.text.lower()
        assert response.provider == "anthropic"

    @pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
    def test_openai_adapter_live(self):
        """Test OpenAI adapter with real API (manual run only)."""
        pytest.importorskip("openai", reason="openai package not installed")
        from agnetwork.tools.llm.adapters.openai import OpenAIAdapter

        adapter = OpenAIAdapter()
        request = LLMRequest(
            messages=[LLMMessage(role="user", content="Say 'hello' and nothing else.")],
            max_tokens=10,
        )

        response = adapter.complete(request)

        assert "hello" in response.text.lower()
        assert response.provider == "openai"

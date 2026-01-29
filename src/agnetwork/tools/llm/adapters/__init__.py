"""LLM adapters for different providers.

Each adapter translates the provider-agnostic LLMRequest to the
provider's specific SDK format and normalizes the response.

Available adapters:
- FakeAdapter: Deterministic responses for testing
- AnthropicAdapter: Anthropic Claude models
- OpenAIAdapter: OpenAI GPT models (optional)
"""

from agnetwork.tools.llm.adapters.base import LLMAdapter
from agnetwork.tools.llm.adapters.fake import FakeAdapter

__all__ = [
    "LLMAdapter",
    "FakeAdapter",
]


# Lazy imports for optional providers
def get_anthropic_adapter():
    """Get AnthropicAdapter (requires anthropic package)."""
    from agnetwork.tools.llm.adapters.anthropic import AnthropicAdapter

    return AnthropicAdapter


def get_openai_adapter():
    """Get OpenAIAdapter (requires openai package)."""
    from agnetwork.tools.llm.adapters.openai import OpenAIAdapter

    return OpenAIAdapter

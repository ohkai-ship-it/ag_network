"""Provider-agnostic LLM request/response types.

This module defines types that are independent of any specific LLM provider,
allowing skills and tools to work with a uniform interface.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Role types for multi-role routing
LLMRole = Literal["default", "draft", "critic", "extractor"]


class LLMMessage(BaseModel):
    """A single message in a conversation.

    Follows the standard system/user/assistant role convention
    used by most LLM providers.
    """

    role: Literal["system", "user", "assistant"]
    content: str


class LLMRequest(BaseModel):
    """Provider-agnostic LLM request.

    Contains all parameters needed to make an LLM API call,
    independent of any specific provider's SDK.
    """

    messages: List[LLMMessage]
    role: LLMRole = "default"  # Logical role for routing
    model: Optional[str] = None  # Override model from config
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout_s: Optional[int] = None
    response_format: Literal["text", "json"] = "text"  # Hint only; adapters may ignore
    metadata: Dict[str, Any] = Field(default_factory=dict)  # run_id, skill, step_id

    def with_metadata(self, **kwargs: Any) -> "LLMRequest":
        """Return a copy with additional metadata."""
        new_metadata = {**self.metadata, **kwargs}
        return self.model_copy(update={"metadata": new_metadata})


class LLMUsage(BaseModel):
    """Token usage statistics from an LLM call.

    All fields are optional as not all providers report usage.
    """

    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class LLMResponse(BaseModel):
    """Provider-agnostic LLM response.

    Normalizes responses from different providers into a standard format.
    """

    text: str  # The generated text content
    model: str  # The model that was used
    provider: str  # The provider name (anthropic, openai, fake, etc.)
    usage: Optional[LLMUsage] = None  # Token usage if available
    raw: Optional[Dict[str, Any]] = None  # Raw provider response for debugging

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "text": self.text[:200] + "..." if len(self.text) > 200 else self.text,
            "model": self.model,
            "provider": self.provider,
            "usage": self.usage.model_dump() if self.usage else None,
        }

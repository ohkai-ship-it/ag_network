"""Base adapter protocol for LLM providers.

This module defines the protocol that all LLM adapters must implement.
Adapters are responsible ONLY for:
1. Translating LLMRequest → provider SDK request
2. Calling the provider API
3. Normalizing the response → LLMResponse

Adapters do NOT:
- Parse or validate JSON content
- Retry on validation failures
- Handle structured output repair
"""

from typing import Dict, Protocol, runtime_checkable

from agnetwork.tools.llm.types import LLMRequest, LLMResponse


@runtime_checkable
class LLMAdapter(Protocol):
    """Protocol for LLM provider adapters.

    All adapters must implement this interface to be usable
    with the LLM factory and structured output tools.
    """

    @property
    def provider(self) -> str:
        """Return the provider name (e.g., 'anthropic', 'openai', 'fake')."""
        ...

    @property
    def capabilities(self) -> Dict[str, bool]:
        """Return adapter capabilities.

        Current capabilities:
        - supports_json_schema: Can use native JSON schema enforcement
        - supports_streaming: Can stream responses
        - supports_tools: Can use function/tool calling

        Keep minimal; extend as needed for future features.
        """
        ...

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request to the provider.

        Args:
            request: Provider-agnostic request

        Returns:
            Normalized response

        Raises:
            LLMAdapterError: On API errors, timeouts, etc.
        """
        ...


class LLMAdapterError(Exception):
    """Base exception for LLM adapter errors."""

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        original_error: Exception | None = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.provider = provider
        self.original_error = original_error
        self.retryable = retryable


class LLMRateLimitError(LLMAdapterError):
    """Rate limit exceeded."""

    def __init__(self, message: str, provider: str, retry_after: int | None = None):
        super().__init__(message, provider, retryable=True)
        self.retry_after = retry_after


class LLMAuthenticationError(LLMAdapterError):
    """Authentication failed (invalid API key)."""

    def __init__(self, message: str, provider: str):
        super().__init__(message, provider, retryable=False)


class LLMTimeoutError(LLMAdapterError):
    """Request timed out."""

    def __init__(self, message: str, provider: str, timeout_s: int):
        super().__init__(message, provider, retryable=True)
        self.timeout_s = timeout_s

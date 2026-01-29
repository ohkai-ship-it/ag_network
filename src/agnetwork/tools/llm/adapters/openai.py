"""OpenAI GPT adapter for LLM integration.

This adapter translates LLMRequest to OpenAI's SDK format
and normalizes responses back to LLMResponse.
"""

import os
from typing import Any, Dict

from agnetwork.tools.llm.adapters.base import (
    LLMAdapterError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from agnetwork.tools.llm.types import LLMRequest, LLMResponse, LLMUsage


class OpenAIAdapter:
    """Adapter for OpenAI GPT models.

    Requires the openai package and OPENAI_API_KEY env var.

    Usage:
        adapter = OpenAIAdapter()
        response = adapter.complete(request)
    """

    DEFAULT_MODEL = "gpt-4o"
    DEFAULT_MAX_TOKENS = 4096

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_s: int = 60,
    ):
        """Initialize OpenAI adapter.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Default model to use
            timeout_s: Default timeout in seconds
        """
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._model = model or self.DEFAULT_MODEL
        self._timeout_s = timeout_s
        self._provider = "openai"
        self._client = None

    @property
    def provider(self) -> str:
        """Return provider name."""
        return self._provider

    @property
    def capabilities(self) -> Dict[str, bool]:
        """Return capabilities."""
        return {
            "supports_json_schema": True,  # OpenAI has JSON mode
            "supports_streaming": True,
            "supports_tools": True,
        }

    def _get_client(self):
        """Get or create OpenAI client (lazy initialization)."""
        if self._client is None:
            try:
                import openai
            except ImportError:
                raise LLMAdapterError(
                    message="openai package not installed. Run: pip install openai",
                    provider=self._provider,
                )

            if not self._api_key:
                raise LLMAuthenticationError(
                    message="OPENAI_API_KEY not set",
                    provider=self._provider,
                )

            self._client = openai.OpenAI(
                api_key=self._api_key,
                timeout=self._timeout_s,
            )
        return self._client

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Send completion request to OpenAI.

        Args:
            request: Provider-agnostic request

        Returns:
            Normalized response

        Raises:
            LLMAdapterError: On API errors
        """
        client = self._get_client()

        # Build OpenAI-specific request
        model = request.model or self._model
        max_tokens = request.max_tokens or self.DEFAULT_MAX_TOKENS

        # Convert messages (OpenAI uses same format)
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]

        # Build request kwargs
        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        if request.temperature is not None:
            kwargs["temperature"] = request.temperature

        # Enable JSON mode if requested
        if request.response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        # Make API call
        try:
            import openai

            response = client.chat.completions.create(**kwargs)

            # Extract text from response
            text = response.choices[0].message.content or ""

            # Build usage stats
            usage = None
            if response.usage:
                usage = LLMUsage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                )

            return LLMResponse(
                text=text,
                model=response.model,
                provider=self._provider,
                usage=usage,
                raw={
                    "id": response.id,
                    "finish_reason": response.choices[0].finish_reason,
                },
            )

        except openai.AuthenticationError as e:
            raise LLMAuthenticationError(
                message=f"OpenAI authentication failed: {e}",
                provider=self._provider,
            )
        except openai.RateLimitError as e:
            raise LLMRateLimitError(
                message=f"OpenAI rate limit exceeded: {e}",
                provider=self._provider,
            )
        except openai.APITimeoutError as e:
            raise LLMTimeoutError(
                message=f"OpenAI request timed out: {e}",
                provider=self._provider,
                timeout_s=self._timeout_s,
            )
        except openai.APIError as e:
            raise LLMAdapterError(
                message=f"OpenAI API error: {e}",
                provider=self._provider,
                original_error=e,
                retryable=getattr(e, "status_code", 500) >= 500,
            )
        except Exception as e:
            raise LLMAdapterError(
                message=f"Unexpected error calling OpenAI: {e}",
                provider=self._provider,
                original_error=e,
            )

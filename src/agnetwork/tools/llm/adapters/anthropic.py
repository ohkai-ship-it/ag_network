"""Anthropic Claude adapter for LLM integration.

This adapter translates LLMRequest to Anthropic's SDK format
and normalizes responses back to LLMResponse.
"""

import os
from typing import Any, Dict, List, Tuple

from agnetwork.tools.llm.adapters.base import (
    LLMAdapterError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from agnetwork.tools.llm.types import LLMRequest, LLMResponse, LLMUsage


class AnthropicAdapter:
    """Adapter for Anthropic Claude models.

    Requires the anthropic package and ANTHROPIC_API_KEY env var.

    Usage:
        adapter = AnthropicAdapter()
        response = adapter.complete(request)
    """

    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    DEFAULT_MAX_TOKENS = 4096

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_s: int = 60,
    ):
        """Initialize Anthropic adapter.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Default model to use
            timeout_s: Default timeout in seconds
        """
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._model = model or self.DEFAULT_MODEL
        self._timeout_s = timeout_s
        self._provider = "anthropic"
        self._client = None

    @property
    def provider(self) -> str:
        """Return provider name."""
        return self._provider

    @property
    def capabilities(self) -> Dict[str, bool]:
        """Return capabilities."""
        return {
            "supports_json_schema": False,  # Anthropic doesn't have native JSON schema
            "supports_streaming": True,
            "supports_tools": True,
        }

    def _get_client(self):
        """Get or create Anthropic client (lazy initialization)."""
        if self._client is None:
            try:
                import anthropic
            except ImportError:
                raise LLMAdapterError(
                    message="anthropic package not installed. Run: pip install anthropic",
                    provider=self._provider,
                )

            if not self._api_key:
                raise LLMAuthenticationError(
                    message="ANTHROPIC_API_KEY not set",
                    provider=self._provider,
                )

            self._client = anthropic.Anthropic(
                api_key=self._api_key,
                timeout=self._timeout_s,
            )
        return self._client

    def _build_request_kwargs(
        self, request: LLMRequest
    ) -> Tuple[Dict[str, Any], str | None]:
        """Build Anthropic-specific request kwargs.

        Returns:
            Tuple of (kwargs dict, system content or None)
        """
        model = request.model or self._model
        max_tokens = request.max_tokens or self.DEFAULT_MAX_TOKENS

        # Extract system message and convert messages
        system_content = None
        messages: List[Dict[str, str]] = []
        for msg in request.messages:
            if msg.role == "system":
                system_content = msg.content
            else:
                messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        if system_content:
            kwargs["system"] = system_content

        if request.temperature is not None:
            kwargs["temperature"] = request.temperature

        return kwargs, system_content

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse Anthropic response to LLMResponse."""
        # Extract text from response
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        # Build usage stats
        usage = None
        if hasattr(response, "usage"):
            usage = LLMUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            )

        return LLMResponse(
            text=text,
            model=response.model,
            provider=self._provider,
            usage=usage,
            raw={
                "id": response.id,
                "stop_reason": response.stop_reason,
            },
        )

    def _handle_api_error(self, e: Exception) -> None:
        """Handle Anthropic API errors by raising appropriate LLMAdapterError."""
        import anthropic

        if isinstance(e, anthropic.AuthenticationError):
            raise LLMAuthenticationError(
                message=f"Anthropic authentication failed: {e}",
                provider=self._provider,
            )
        elif isinstance(e, anthropic.RateLimitError):
            raise LLMRateLimitError(
                message=f"Anthropic rate limit exceeded: {e}",
                provider=self._provider,
            )
        elif isinstance(e, anthropic.APITimeoutError):
            raise LLMTimeoutError(
                message=f"Anthropic request timed out: {e}",
                provider=self._provider,
                timeout_s=self._timeout_s,
            )
        elif isinstance(e, anthropic.APIError):
            raise LLMAdapterError(
                message=f"Anthropic API error: {e}",
                provider=self._provider,
                original_error=e,
                retryable=getattr(e, "status_code", 500) >= 500,
            )
        else:
            raise LLMAdapterError(
                message=f"Unexpected error calling Anthropic: {e}",
                provider=self._provider,
                original_error=e,
            )

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Send completion request to Anthropic.

        Args:
            request: Provider-agnostic request

        Returns:
            Normalized response

        Raises:
            LLMAdapterError: On API errors
        """
        client = self._get_client()
        kwargs, _ = self._build_request_kwargs(request)

        try:
            response = client.messages.create(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            self._handle_api_error(e)

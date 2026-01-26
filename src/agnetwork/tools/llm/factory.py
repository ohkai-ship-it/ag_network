"""LLM Factory with role-based routing.

This module provides:
- LLMConfig: Configuration for LLM providers and roles
- LLMFactory: Factory for creating adapters based on role

Role routing allows different models for different tasks:
- default: General purpose completions
- draft: Content generation (may use cheaper/faster model)
- critic: Quality review (may use more capable model)
- extractor: Structured data extraction
"""

import os
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from agnetwork.tools.llm.adapters.base import LLMAdapter, LLMAdapterError
from agnetwork.tools.llm.adapters.fake import FakeAdapter
from agnetwork.tools.llm.types import LLMRole


class RoleConfig(BaseModel):
    """Configuration for a specific role."""

    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout_s: Optional[int] = None

    def to_adapter_kwargs(self) -> Dict[str, Any]:
        """Convert to adapter initialization kwargs."""
        kwargs: Dict[str, Any] = {"model": self.model}
        if self.timeout_s:
            kwargs["timeout_s"] = self.timeout_s
        return kwargs


class LLMConfig(BaseModel):
    """Global LLM configuration.

    Loaded from environment variables with sensible defaults.
    """

    enabled: bool = False
    default_provider: str = "anthropic"
    default_model: str = "claude-sonnet-4-20250514"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout_s: int = 60

    # Role-specific configurations
    roles: Dict[str, RoleConfig] = Field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load configuration from environment variables.

        Environment variables:
        - AG_LLM_ENABLED: 0 or 1 (default: 0)
        - AG_LLM_DEFAULT_PROVIDER: Provider name (default: anthropic)
        - AG_LLM_DEFAULT_MODEL: Model name
        - AG_LLM_TEMPERATURE: Temperature (default: 0.7)
        - AG_LLM_MAX_TOKENS: Max tokens (default: 4096)
        - AG_LLM_TIMEOUT_S: Timeout in seconds (default: 60)
        - AG_LLM_CRITIC_PROVIDER: Provider for critic role (optional)
        - AG_LLM_CRITIC_MODEL: Model for critic role (optional)
        - AG_LLM_DRAFT_PROVIDER: Provider for draft role (optional)
        - AG_LLM_DRAFT_MODEL: Model for draft role (optional)
        """
        enabled = os.environ.get("AG_LLM_ENABLED", "0") == "1"
        default_provider = os.environ.get("AG_LLM_DEFAULT_PROVIDER", "anthropic")
        default_model = os.environ.get(
            "AG_LLM_DEFAULT_MODEL", "claude-sonnet-4-20250514"
        )
        temperature = float(os.environ.get("AG_LLM_TEMPERATURE", "0.7"))
        max_tokens = int(os.environ.get("AG_LLM_MAX_TOKENS", "4096"))
        timeout_s = int(os.environ.get("AG_LLM_TIMEOUT_S", "60"))

        # Build role configs
        roles: Dict[str, RoleConfig] = {}

        # Default role
        roles["default"] = RoleConfig(
            provider=default_provider,
            model=default_model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )

        # Critic role (falls back to default if not configured)
        critic_provider = os.environ.get("AG_LLM_CRITIC_PROVIDER", default_provider)
        critic_model = os.environ.get("AG_LLM_CRITIC_MODEL", default_model)
        roles["critic"] = RoleConfig(
            provider=critic_provider,
            model=critic_model,
            temperature=0.3,  # Lower temperature for critic
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )

        # Draft role (falls back to default if not configured)
        draft_provider = os.environ.get("AG_LLM_DRAFT_PROVIDER", default_provider)
        draft_model = os.environ.get("AG_LLM_DRAFT_MODEL", default_model)
        roles["draft"] = RoleConfig(
            provider=draft_provider,
            model=draft_model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )

        # Extractor role (reserved for future)
        roles["extractor"] = RoleConfig(
            provider=default_provider,
            model=default_model,
            temperature=0.0,  # Deterministic for extraction
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )

        return cls(
            enabled=enabled,
            default_provider=default_provider,
            default_model=default_model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
            roles=roles,
        )


class LLMFactory:
    """Factory for creating LLM adapters with role-based routing.

    Usage:
        factory = LLMFactory.from_env()

        # Get adapter for default role
        adapter = factory.get()

        # Get adapter for specific role
        critic = factory.get(role="critic")

        # Check if LLM is enabled
        if factory.is_enabled:
            response = adapter.complete(request)
    """

    def __init__(self, config: LLMConfig):
        """Initialize factory with configuration.

        Args:
            config: LLM configuration
        """
        self.config = config
        self._adapters: Dict[str, LLMAdapter] = {}

    @classmethod
    def from_env(cls) -> "LLMFactory":
        """Create factory from environment configuration."""
        config = LLMConfig.from_env()
        return cls(config)

    @property
    def is_enabled(self) -> bool:
        """Check if LLM is enabled."""
        return self.config.enabled

    def defaults_for(self, role: LLMRole = "default") -> RoleConfig:
        """Get default configuration for a role.

        Args:
            role: The role to get defaults for

        Returns:
            RoleConfig for the role (or default if role not configured)
        """
        if role in self.config.roles:
            return self.config.roles[role]
        return self.config.roles.get("default", RoleConfig())

    def get(self, role: LLMRole = "default") -> LLMAdapter:
        """Get an adapter for the specified role.

        Args:
            role: The role to get an adapter for

        Returns:
            LLMAdapter instance

        Raises:
            LLMAdapterError: If provider is not supported or not configured
        """
        # Get role config (fall back to default)
        role_config = self.defaults_for(role)
        provider = role_config.provider

        # Cache key includes role for role-specific configuration
        cache_key = f"{provider}_{role}"

        if cache_key not in self._adapters:
            self._adapters[cache_key] = self._create_adapter(provider, role_config)

        return self._adapters[cache_key]

    def _create_adapter(self, provider: str, role_config: RoleConfig) -> LLMAdapter:
        """Create an adapter for a provider.

        Args:
            provider: Provider name
            role_config: Role configuration

        Returns:
            LLMAdapter instance

        Raises:
            LLMAdapterError: If provider is not supported
        """
        kwargs = role_config.to_adapter_kwargs()

        if provider == "fake":
            return FakeAdapter()

        if provider == "anthropic":
            try:
                from agnetwork.tools.llm.adapters.anthropic import AnthropicAdapter
                return AnthropicAdapter(**kwargs)
            except ImportError:
                raise LLMAdapterError(
                    message="anthropic package not installed. Run: pip install anthropic",
                    provider=provider,
                )

        if provider == "openai":
            try:
                from agnetwork.tools.llm.adapters.openai import OpenAIAdapter
                return OpenAIAdapter(**kwargs)
            except ImportError:
                raise LLMAdapterError(
                    message="openai package not installed. Run: pip install openai",
                    provider=provider,
                )

        raise LLMAdapterError(
            message=f"Unsupported LLM provider: {provider}",
            provider=provider,
        )

    def set_adapter(self, role: LLMRole, adapter: LLMAdapter) -> None:
        """Set a specific adapter for a role (for testing).

        Args:
            role: The role to set adapter for
            adapter: The adapter to use
        """
        # Update the role config provider to match the adapter
        if role in self.config.roles:
            self.config.roles[role] = self.config.roles[role].model_copy(
                update={"provider": adapter.provider}
            )
        else:
            # Create a new role config for this role
            self.config.roles[role] = RoleConfig(provider=adapter.provider)

        # Use consistent cache key
        cache_key = f"{adapter.provider}_{role}"
        self._adapters[cache_key] = adapter

"""LLM tools for AG Network.

This module provides provider-agnostic LLM integration with:
- Adapter-based provider abstraction
- Multi-role routing (default, draft, critic, extractor)
- Structured output enforcement with Pydantic validation
- Repair loop for malformed LLM outputs

Usage:
    from agnetwork.tools.llm import LLMFactory, LLMRequest, LLMResponse

    factory = LLMFactory.from_env()
    adapter = factory.get(role="default")
    response = adapter.complete(request)
"""

from agnetwork.tools.llm.factory import LLMConfig, LLMFactory, RoleConfig
from agnetwork.tools.llm.structured import extract_json, parse_or_repair_json
from agnetwork.tools.llm.types import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMRole,
    LLMUsage,
)

__all__ = [
    # Types
    "LLMRole",
    "LLMMessage",
    "LLMRequest",
    "LLMResponse",
    "LLMUsage",
    # Factory
    "LLMFactory",
    "LLMConfig",
    "RoleConfig",
    # Structured
    "extract_json",
    "parse_or_repair_json",
]

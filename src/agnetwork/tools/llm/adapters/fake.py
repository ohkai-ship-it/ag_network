"""Fake LLM adapter for deterministic testing.

This adapter returns predefined responses for testing purposes.
It supports:
- Predefined responses by prompt substring match
- Queue-based responses for multi-turn scenarios
- Configurable failures for error path testing
"""

import json
from typing import Callable, Dict, List, Optional

from agnetwork.tools.llm.adapters.base import LLMAdapterError
from agnetwork.tools.llm.types import LLMRequest, LLMResponse, LLMUsage


class FakeAdapter:
    """Deterministic LLM adapter for testing.

    Usage:
        adapter = FakeAdapter()

        # Add predefined responses
        adapter.add_response("research", '{"company": "TestCorp", ...}')

        # Or use response queue for sequential calls
        adapter.queue_response('{"valid": true}')
        adapter.queue_response('{"fixed": true}')  # For repair scenario

        # Use in tests
        response = adapter.complete(request)
    """

    def __init__(self, default_response: str | None = None):
        """Initialize fake adapter.

        Args:
            default_response: Response to return if no match found
        """
        self._provider = "fake"
        self._responses: Dict[str, str] = {}
        self._response_queue: List[str] = []
        self._call_count = 0
        self._call_history: List[LLMRequest] = []
        self._default_response = default_response or '{"status": "ok"}'
        self._should_fail: bool = False
        self._fail_message: str = ""
        self._response_fn: Optional[Callable[[LLMRequest], str]] = None

    @property
    def provider(self) -> str:
        """Return provider name."""
        return self._provider

    @property
    def capabilities(self) -> Dict[str, bool]:
        """Return capabilities (all false for fake adapter)."""
        return {
            "supports_json_schema": False,
            "supports_streaming": False,
            "supports_tools": False,
        }

    @property
    def call_count(self) -> int:
        """Return number of calls made."""
        return self._call_count

    @property
    def call_history(self) -> List[LLMRequest]:
        """Return history of requests."""
        return self._call_history

    def add_response(self, prompt_contains: str, response: str) -> "FakeAdapter":
        """Add a response for prompts containing a substring.

        Args:
            prompt_contains: Substring to match in user message
            response: Response to return

        Returns:
            Self for chaining
        """
        self._responses[prompt_contains.lower()] = response
        return self

    def queue_response(self, response: str) -> "FakeAdapter":
        """Add a response to the queue (FIFO).

        Args:
            response: Response to add

        Returns:
            Self for chaining
        """
        self._response_queue.append(response)
        return self

    def set_response_fn(self, fn: Callable[[LLMRequest], str]) -> "FakeAdapter":
        """Set a function to generate responses.

        Args:
            fn: Function that takes request and returns response text

        Returns:
            Self for chaining
        """
        self._response_fn = fn
        return self

    def set_should_fail(self, should_fail: bool, message: str = "Fake error") -> "FakeAdapter":
        """Configure adapter to fail on next call.

        Args:
            should_fail: Whether to fail
            message: Error message

        Returns:
            Self for chaining
        """
        self._should_fail = should_fail
        self._fail_message = message
        return self

    def reset(self) -> "FakeAdapter":
        """Reset all state.

        Returns:
            Self for chaining
        """
        self._responses.clear()
        self._response_queue.clear()
        self._call_count = 0
        self._call_history.clear()
        self._should_fail = False
        self._response_fn = None
        return self

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Return a predefined response.

        Args:
            request: The LLM request

        Returns:
            Fake response

        Raises:
            LLMAdapterError: If configured to fail
        """
        self._call_count += 1
        self._call_history.append(request)

        # Check if should fail
        if self._should_fail:
            raise LLMAdapterError(
                message=self._fail_message,
                provider=self._provider,
                retryable=False,
            )

        # Try response function first
        if self._response_fn:
            text = self._response_fn(request)
            return self._make_response(text, request)

        # Try queue next
        if self._response_queue:
            text = self._response_queue.pop(0)
            return self._make_response(text, request)

        # Try pattern matching
        user_content = self._get_user_content(request)
        for pattern, response in self._responses.items():
            if pattern in user_content.lower():
                return self._make_response(response, request)

        # Return default
        return self._make_response(self._default_response, request)

    def _get_user_content(self, request: LLMRequest) -> str:
        """Extract user message content from request."""
        for msg in reversed(request.messages):
            if msg.role == "user":
                return msg.content
        return ""

    def _make_response(self, text: str, request: LLMRequest) -> LLMResponse:
        """Create a response object."""
        return LLMResponse(
            text=text,
            model=request.model or "fake-model",
            provider=self._provider,
            usage=LLMUsage(
                prompt_tokens=len(self._get_user_content(request).split()),
                completion_tokens=len(text.split()),
                total_tokens=len(self._get_user_content(request).split()) + len(text.split()),
            ),
            raw={"fake": True, "call_count": self._call_count},
        )


# Preset responses for common test scenarios
FAKE_RESEARCH_BRIEF = json.dumps(
    {
        "company": "TestCorp",
        "snapshot": "A technology company focused on AI solutions",
        "pains": ["Scaling challenges", "Customer acquisition costs"],
        "triggers": ["New funding round", "Leadership change"],
        "competitors": ["CompetitorA", "CompetitorB"],
        "personalization_angles": [
            {
                "name": "Growth Focus",
                "fact": "TestCorp recently raised Series B",
                "is_assumption": False,
            },
            {
                "name": "Tech Investment",
                "fact": "TestCorp is investing in AI",
                "is_assumption": True,
            },
        ],
    }
)

FAKE_TARGET_MAP = json.dumps(
    {
        "company": "TestCorp",
        "personas": [
            {
                "title": "VP Sales",
                "role": "economic_buyer",
                "hypothesis": "Controls budget",
                "is_assumption": True,
            },
            {
                "title": "CTO",
                "role": "technical_evaluator",
                "hypothesis": "Evaluates tech fit",
                "is_assumption": True,
            },
        ],
    }
)

FAKE_OUTREACH = json.dumps(
    {
        "company": "TestCorp",
        "persona": "VP Sales",
        "channel": "email",
        "variants": [
            {
                "channel": "email",
                "subject_or_hook": "Partnership opportunity with TestCorp",
                "body": "Hi VP Sales,\n\nI noticed TestCorp's impressive growth...",
                "personalization_notes": "Reference recent funding announcement",
            }
        ],
        "sequence_steps": ["Initial outreach", "Follow-up Day 3", "Value share Day 7"],
        "objection_responses": {"no_budget": "Let me share ROI data..."},
    }
)

FAKE_MEETING_PREP = json.dumps(
    {
        "company": "TestCorp",
        "meeting_type": "discovery",
        "agenda": ["Introductions", "Problem discovery", "Solution overview", "Next steps"],
        "questions": ["What are your priorities?", "How do you currently solve this?"],
        "stakeholder_map": {"VP Sales": "Economic buyer"},
        "listen_for_signals": ["Budget timing", "Competitor mentions"],
        "close_plan": "Propose demo if interest confirmed",
    }
)

FAKE_FOLLOWUP = json.dumps(
    {
        "company": "TestCorp",
        "meeting_date": "2026-01-26T12:00:00Z",
        "summary": "Good initial meeting with TestCorp",
        "next_steps": ["Send summary", "Schedule demo", "Follow up in 1 week"],
        "tasks": [{"task": "Send summary", "owner": "sales", "due": "Today"}],
        "crm_notes": "Active opportunity, strong interest",
    }
)

# Invalid JSON for repair testing
FAKE_INVALID_JSON = "```json\n{this is not valid json}\n```"
FAKE_REPAIRED_JSON = json.dumps({"company": "TestCorp", "status": "repaired"})

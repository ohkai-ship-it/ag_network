"""Structured output enforcement with Pydantic validation.

This module provides:
- extract_json(): Safely extract JSON from LLM text
- parse_or_repair_json(): Parse and validate with repair loop

The repair loop:
1. Try to parse LLM output as JSON
2. Validate against Pydantic model
3. If failed, call critic role to repair
4. Retry up to max_repairs times
5. If still failed, raise StructuredOutputError
"""

import json
import re
from typing import Any, Dict, Type, TypeVar

from pydantic import BaseModel, ValidationError

from agnetwork.tools.llm.adapters.base import LLMAdapterError
from agnetwork.tools.llm.types import LLMMessage, LLMRequest, LLMRole

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(Exception):
    """Failed to parse or repair structured output."""

    def __init__(
        self,
        message: str,
        original_text: str,
        validation_errors: list[Dict[str, Any]] | None = None,
        repair_attempts: int = 0,
    ):
        super().__init__(message)
        self.original_text = original_text
        self.validation_errors = validation_errors or []
        self.repair_attempts = repair_attempts


def extract_json(text: str) -> str:
    """Extract JSON from LLM response text.

    Handles common LLM output patterns:
    - JSON wrapped in ```json ... ``` code fences
    - JSON wrapped in ``` ... ``` code fences
    - Plain JSON starting with { or [
    - Text with JSON embedded

    Args:
        text: Raw LLM response text

    Returns:
        Extracted JSON string

    Raises:
        ValueError: If no JSON found in text
    """
    text = text.strip()

    # Pattern 1: JSON code fence with language tag
    fence_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?```"
    matches = re.findall(fence_pattern, text)
    if matches:
        # Return the first match that looks like JSON
        for match in matches:
            match = match.strip()
            if match.startswith(("{", "[")):
                return match

    # Pattern 2: Direct JSON (starts with { or [)
    if text.startswith(("{", "[")):
        # Find matching closing bracket
        return _extract_balanced_json(text)

    # Pattern 3: Find JSON object/array in text
    # Look for first { or [ and try to extract balanced JSON
    for i, char in enumerate(text):
        if char in "{[":
            try:
                extracted = _extract_balanced_json(text[i:])
                # Validate it's actually JSON
                json.loads(extracted)
                return extracted
            except (ValueError, json.JSONDecodeError):
                continue

    raise ValueError(f"No valid JSON found in text: {text[:200]}...")


def _extract_balanced_json(text: str) -> str:
    """Extract balanced JSON from start of text.

    Args:
        text: Text starting with { or [

    Returns:
        Balanced JSON string
    """
    if not text or text[0] not in "{[":
        raise ValueError("Text must start with { or [")

    open_bracket = text[0]
    close_bracket = "}" if open_bracket == "{" else "]"

    depth = 0
    in_string = False
    escape_next = False

    for i, char in enumerate(text):
        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == open_bracket:
            depth += 1
        elif char == close_bracket:
            depth -= 1
            if depth == 0:
                return text[: i + 1]

    # If we get here, brackets aren't balanced
    # Return what we have and let JSON parser handle the error
    return text


def get_schema_summary(model: Type[BaseModel]) -> str:
    """Get a human-readable schema summary for a Pydantic model.

    Args:
        model: Pydantic model class

    Returns:
        Schema summary string
    """
    schema = model.model_json_schema()

    lines = [f"Schema for {model.__name__}:"]
    lines.append("{")

    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    for name, prop in properties.items():
        prop_type = prop.get("type", "any")
        if "anyOf" in prop:
            # Handle Optional types
            types = [t.get("type", "null") for t in prop["anyOf"]]
            prop_type = " | ".join(t for t in types if t)

        req_marker = " (required)" if name in required else " (optional)"
        lines.append(f'  "{name}": {prop_type}{req_marker}')

    lines.append("}")
    return "\n".join(lines)


def parse_or_repair_json(
    model: Type[T],
    llm_text: str,
    llm_factory: Any,  # LLMFactory - using Any to avoid circular import
    *,
    role: LLMRole = "default",
    max_repairs: int = 2,
    run_id: str | None = None,
    skill_name: str | None = None,
) -> T:
    """Parse LLM output into a Pydantic model with repair loop.

    This function:
    1. Extracts JSON from the LLM text
    2. Attempts to parse and validate against the model
    3. If validation fails, calls the critic role to repair
    4. Retries up to max_repairs times

    Args:
        model: Pydantic model class to validate against
        llm_text: Raw LLM response text
        llm_factory: LLMFactory for repair calls
        role: Role to use for repair (default: critic if available)
        max_repairs: Maximum repair attempts
        run_id: Optional run ID for logging
        skill_name: Optional skill name for logging

    Returns:
        Validated Pydantic model instance

    Raises:
        StructuredOutputError: If parsing/validation fails after max_repairs
    """
    last_errors: list[Dict[str, Any]] = []
    current_text = llm_text

    for attempt in range(max_repairs + 1):
        try:
            # Extract JSON
            json_str = extract_json(current_text)

            # Parse JSON
            data = json.loads(json_str)

            # Validate with Pydantic
            return model.model_validate(data)

        except ValueError as e:
            # JSON extraction failed
            last_errors.append({
                "attempt": attempt,
                "error_type": "extraction",
                "message": str(e),
            })

        except json.JSONDecodeError as e:
            # JSON parsing failed
            last_errors.append({
                "attempt": attempt,
                "error_type": "json_parse",
                "message": str(e),
                "line": e.lineno,
                "column": e.colno,
            })

        except ValidationError as e:
            # Pydantic validation failed
            last_errors.append({
                "attempt": attempt,
                "error_type": "validation",
                "errors": e.errors(),
            })

        # If we haven't exceeded repair attempts, try to repair
        if attempt < max_repairs:
            try:
                current_text = _repair_json(
                    original_text=current_text,
                    model=model,
                    errors=last_errors[-1],
                    llm_factory=llm_factory,
                    role=role,
                    run_id=run_id,
                    skill_name=skill_name,
                )
            except LLMAdapterError as e:
                # LLM call failed, append error and continue
                last_errors.append({
                    "attempt": attempt,
                    "error_type": "repair_failed",
                    "message": str(e),
                })
                break

    # All attempts failed
    raise StructuredOutputError(
        message=f"Failed to parse {model.__name__} after {max_repairs + 1} attempts",
        original_text=llm_text,
        validation_errors=last_errors,
        repair_attempts=max_repairs,
    )


def _repair_json(
    original_text: str,
    model: Type[BaseModel],
    errors: Dict[str, Any],
    llm_factory: Any,
    role: LLMRole,
    run_id: str | None,
    skill_name: str | None,
) -> str:
    """Attempt to repair malformed JSON using LLM.

    Args:
        original_text: The malformed LLM output
        model: Target Pydantic model
        errors: Error details from last attempt
        llm_factory: LLM factory
        role: Role to use (prefers critic)
        run_id: Optional run ID
        skill_name: Optional skill name

    Returns:
        Repaired JSON text
    """
    schema_summary = get_schema_summary(model)

    # Format error message
    if errors.get("error_type") == "validation":
        error_msg = "Validation errors:\n" + json.dumps(errors.get("errors", []), indent=2)
    else:
        error_msg = f"{errors.get('error_type', 'unknown')}: {errors.get('message', 'unknown error')}"

    system_prompt = """You are a JSON repair assistant. Your task is to fix malformed or invalid JSON.

Rules:
1. Output ONLY valid JSON - no explanations, no markdown, no code fences
2. Fix syntax errors (missing quotes, brackets, commas)
3. Fix schema violations (wrong types, missing required fields)
4. Preserve as much original data as possible
5. If a field is missing and required, use a reasonable default value
6. Output must match the provided schema exactly"""

    user_prompt = f"""Fix this JSON to match the schema.

{schema_summary}

Errors found:
{error_msg}

Original output:
{original_text[:2000]}

Output ONLY the fixed JSON:"""

    # Use critic role if available, otherwise specified role
    adapter = llm_factory.get(role="critic")

    request = LLMRequest(
        messages=[
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ],
        role="critic",
        response_format="json",
        metadata={
            "run_id": run_id,
            "skill_name": skill_name,
            "repair_attempt": True,
        },
    )

    response = adapter.complete(request)
    return response.text

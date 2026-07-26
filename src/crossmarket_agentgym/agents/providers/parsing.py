"""Conservative JSON and tool-call response parsing."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from crossmarket_agentgym.agents.providers.models import (
    StructuredOutputError,
    ToolCall,
)


def parse_structured_content(
    content: str,
    response_schema: type[BaseModel] | None,
) -> dict[str, Any] | None:
    """Validate exact JSON content; never infer executable intent from prose."""
    if response_schema is None:
        return None
    try:
        decoded = json.loads(content)
    except json.JSONDecodeError as error:
        raise StructuredOutputError(
            "invalid_json",
            "provider response is not valid JSON",
        ) from error
    if not isinstance(decoded, dict):
        raise StructuredOutputError(
            "invalid_structure",
            "provider response must be a JSON object",
        )
    try:
        validated = response_schema.model_validate(decoded)
    except ValidationError as error:
        raise StructuredOutputError(
            "schema_validation_failed",
            "provider response does not satisfy the response schema",
        ) from error
    return validated.model_dump(mode="json")


def parse_tool_calls(raw_calls: object) -> tuple[ToolCall, ...]:
    """Parse OpenAI-compatible function calls with JSON-object arguments."""
    if raw_calls is None:
        return ()
    if not isinstance(raw_calls, list):
        raise StructuredOutputError("invalid_tool_calls", "tool_calls must be a list")
    parsed: list[ToolCall] = []
    for raw in raw_calls:
        if not isinstance(raw, dict) or not isinstance(raw.get("function"), dict):
            raise StructuredOutputError(
                "invalid_tool_call",
                "tool call does not contain a function object",
            )
        function = raw["function"]
        arguments_text = function.get("arguments", "{}")
        if not isinstance(arguments_text, str):
            raise StructuredOutputError(
                "invalid_tool_arguments",
                "tool arguments must be JSON text",
            )
        try:
            arguments = json.loads(arguments_text)
        except json.JSONDecodeError as error:
            raise StructuredOutputError(
                "invalid_tool_arguments",
                "tool arguments are not valid JSON",
            ) from error
        if not isinstance(arguments, dict):
            raise StructuredOutputError(
                "invalid_tool_arguments",
                "tool arguments must decode to an object",
            )
        parsed.append(
            ToolCall(
                id=str(raw.get("id", "")),
                name=str(function.get("name", "")),
                arguments=arguments,
            )
        )
    return tuple(parsed)

"""Provider protocol and canonical request identity."""

from __future__ import annotations

import hashlib
import json
from typing import Protocol

from pydantic import BaseModel

from crossmarket_agentgym.agents.providers.models import (
    GenerationConfig,
    LLMResponse,
    Message,
)
from crossmarket_agentgym.agents.tools.models import ToolDefinition


class LLMProvider(Protocol):
    """Common synchronous boundary shared by online and offline providers."""

    name: str

    def generate(
        self,
        messages: list[Message],
        response_schema: type[BaseModel] | None,
        tools: list[ToolDefinition] | None,
        generation_config: GenerationConfig,
    ) -> LLMResponse:
        """Generate a schema-validated response or raise a safe ProviderError."""
        ...


def request_fingerprint(
    messages: list[Message],
    response_schema: type[BaseModel] | None,
    tools: list[ToolDefinition] | None,
    generation_config: GenerationConfig,
) -> str:
    """Hash a credential-free canonical provider request."""
    payload = {
        "messages": [message.model_dump(mode="json") for message in messages],
        "response_schema": (
            None if response_schema is None else response_schema.model_json_schema()
        ),
        "tools": (
            None
            if tools is None
            else [tool.model_dump(mode="json") for tool in tools]
        ),
        "generation_config": generation_config.model_dump(mode="json"),
    }
    canonical = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()

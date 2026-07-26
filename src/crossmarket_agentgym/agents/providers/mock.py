"""Deterministic scripted offline provider."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, Field

from crossmarket_agentgym.agents.providers.base import request_fingerprint
from crossmarket_agentgym.agents.providers.models import (
    GenerationConfig,
    LLMResponse,
    Message,
    ProviderError,
    ProviderMetadata,
    StrictProviderModel,
    TokenUsage,
    ToolCall,
)
from crossmarket_agentgym.agents.providers.parsing import parse_structured_content
from crossmarket_agentgym.agents.tools.models import ToolDefinition
from crossmarket_agentgym.config.models import REQUIRED_AGENT_MODEL


class MockTurn(StrictProviderModel):
    """One scripted response or deliberate safe failure."""

    content: str | dict[str, Any] = ""
    tool_calls: tuple[ToolCall, ...] = ()
    usage: TokenUsage = Field(default_factory=TokenUsage)
    error_code: str | None = None
    error_message: str | None = None


class MockProvider:
    """Return deterministic scripted turns without network access."""

    name = "mock"

    def __init__(
        self,
        script: Iterable[MockTurn | dict[str, Any]],
        *,
        model: str = REQUIRED_AGENT_MODEL,
    ) -> None:
        if model != REQUIRED_AGENT_MODEL:
            raise ValueError(f"model must be {REQUIRED_AGENT_MODEL!r}")
        self.model = model
        self._script = [
            turn if isinstance(turn, MockTurn) else MockTurn.model_validate(turn)
            for turn in script
        ]
        self._cursor = 0
        self.request_hashes: list[str] = []

    def generate(
        self,
        messages: list[Message],
        response_schema: type[BaseModel] | None,
        tools: list[ToolDefinition] | None,
        generation_config: GenerationConfig,
    ) -> LLMResponse:
        """Return the next turn and validate final structured output."""
        request_hash = request_fingerprint(
            messages,
            response_schema,
            tools,
            generation_config,
        )
        self.request_hashes.append(request_hash)
        if self._cursor >= len(self._script):
            raise ProviderError("mock_exhausted", "mock provider script is exhausted")
        turn = self._script[self._cursor]
        self._cursor += 1
        if turn.error_code is not None:
            raise ProviderError(
                turn.error_code,
                turn.error_message or "mock provider failure",
            )
        content = (
            turn.content
            if isinstance(turn.content, str)
            else json.dumps(
                turn.content,
                allow_nan=False,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        structured = (
            None
            if turn.tool_calls
            else parse_structured_content(content, response_schema)
        )
        return LLMResponse(
            content=content,
            structured_data=structured,
            tool_calls=turn.tool_calls,
            usage=turn.usage,
            metadata=ProviderMetadata(
                provider=self.name,
                model=self.model,
                attempts=1,
                request_sha256=request_hash,
                structured=response_schema is not None,
            ),
        )

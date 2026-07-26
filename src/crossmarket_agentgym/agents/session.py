"""Bounded Phase 5 provider/tool loop with schema-safe fallback."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from crossmarket_agentgym.agents.providers import (
    GenerationConfig,
    LLMProvider,
    LLMResponse,
    Message,
    ProviderError,
    ReplayJournal,
)
from crossmarket_agentgym.agents.tools import ToolExecutor
from crossmarket_agentgym.audit.agent import AgentAuditWriter

OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass(frozen=True)
class SessionOutcome(Generic[OutputT]):
    """Validated final output or administrator-supplied safe fallback."""

    value: OutputT
    used_fallback: bool
    rounds: int
    error_code: str | None
    final_response: LLMResponse | None


class ProviderToolSession:
    """Run a bounded tool loop without implementing Phase 6 team semantics."""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        tool_executor: ToolExecutor,
        audit: AgentAuditWriter,
        replay_journal: ReplayJournal | None = None,
        max_rounds: int = 3,
    ) -> None:
        if max_rounds < 1:
            raise ValueError("max_rounds must be positive")
        self.provider = provider
        self.tool_executor = tool_executor
        self.audit = audit
        self.replay_journal = replay_journal
        self.max_rounds = max_rounds

    def _fallback(
        self,
        fallback: OutputT,
        *,
        rounds: int,
        code: str,
        message: str,
        response: LLMResponse | None = None,
    ) -> SessionOutcome[OutputT]:
        self.audit.record_fallback(code, message)
        return SessionOutcome(
            value=fallback,
            used_fallback=True,
            rounds=rounds,
            error_code=code,
            final_response=response,
        )

    def run(
        self,
        messages: list[Message],
        *,
        response_schema: type[OutputT],
        fallback: OutputT,
        generation_config: GenerationConfig,
        tool_names: list[str] | None = None,
    ) -> SessionOutcome[OutputT]:
        """Run until valid structured output or a deterministic safe fallback."""
        conversation = list(messages)
        for message in conversation:
            self.audit.record_message("input", message)
        try:
            definitions = self.tool_executor.registry.definitions(tool_names)
        except KeyError as error:
            return self._fallback(
                fallback,
                rounds=0,
                code="unknown_configured_tool",
                message=str(error),
            )
        final_response: LLMResponse | None = None
        for round_index in range(1, self.max_rounds + 1):
            try:
                response = self.provider.generate(
                    conversation,
                    response_schema,
                    definitions,
                    generation_config,
                )
            except ProviderError as error:
                return self._fallback(
                    fallback,
                    rounds=round_index,
                    code=error.code,
                    message=str(error),
                )
            final_response = response
            self.audit.record_provider_response(response)
            assistant_message = Message(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls,
            )
            self.audit.record_message("output", assistant_message)
            if self.replay_journal is not None:
                self.replay_journal.append(
                    response.metadata.request_sha256,
                    response,
                )
            conversation.append(assistant_message)
            if response.tool_calls:
                for call in response.tool_calls:
                    result = self.tool_executor.execute(call.name, call.arguments)
                    self.audit.record_tool_call(call, result)
                    tool_message = Message(
                        role="tool",
                        name=call.name,
                        tool_call_id=call.id,
                        content=json.dumps(
                            result.model_dump(
                                mode="json",
                                exclude={"duration_seconds"},
                            ),
                            allow_nan=False,
                            ensure_ascii=False,
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    )
                    conversation.append(tool_message)
                    self.audit.record_message("tool", tool_message)
                continue
            if response.structured_data is None:
                return self._fallback(
                    fallback,
                    rounds=round_index,
                    code="missing_structured_output",
                    message="provider returned no structured output",
                    response=response,
                )
            try:
                value = response_schema.model_validate(response.structured_data)
            except ValidationError:
                return self._fallback(
                    fallback,
                    rounds=round_index,
                    code="schema_validation_failed",
                    message="provider output failed final schema validation",
                    response=response,
                )
            return SessionOutcome(
                value=value,
                used_fallback=False,
                rounds=round_index,
                error_code=None,
                final_response=response,
            )
        return self._fallback(
            fallback,
            rounds=self.max_rounds,
            code="max_rounds_exceeded",
            message="provider tool loop reached the configured round limit",
            response=final_response,
        )

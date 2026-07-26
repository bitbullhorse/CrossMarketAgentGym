"""Credential-redacted Agent message, tool, provider, and fallback audit."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from crossmarket_agentgym.agents.providers.models import (
    LLMResponse,
    Message,
    ProviderMetadata,
    ToolCall,
)
from crossmarket_agentgym.agents.tools.models import ToolResult
from crossmarket_agentgym.audit.logging import redact_value


def _strict_json(value: Any) -> str:
    return json.dumps(
        redact_value(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


class AgentAuditWriter:
    """Append-only per-run audit artifacts with one monotonic sequence."""

    def __init__(
        self,
        run_dir: str | Path,
        *,
        provider_config: dict[str, Any],
        prompt_version: str,
    ) -> None:
        self.agent_dir = Path(run_dir) / "agent"
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        self.prompt_version = prompt_version
        self._sequence = 0
        self._provider_document: dict[str, Any] = {
            "schema_version": "1.0",
            "prompt_version": prompt_version,
            "config": redact_value(provider_config),
            "responses": [],
        }
        self._write_provider_document()

    def _event(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._sequence += 1
        return {
            "schema_version": "1.0",
            "sequence": self._sequence,
            "timestamp": datetime.now(UTC).isoformat(),
            **payload,
        }

    def _append(self, filename: str, payload: dict[str, Any]) -> None:
        path = self.agent_dir / filename
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(_strict_json(self._event(payload)) + "\n")

    def _write_provider_document(self) -> None:
        path = self.agent_dir / "provider_metadata.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(
                redact_value(self._provider_document),
                allow_nan=False,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    def record_message(self, direction: str, message: Message) -> None:
        """Record an input, assistant, or tool message."""
        self._append(
            "messages.jsonl",
            {
                "direction": direction,
                "message": message.model_dump(mode="json"),
                "prompt_version": self.prompt_version,
            },
        )

    def record_tool_call(self, call: ToolCall, result: ToolResult) -> None:
        """Record validated arguments and normalized result."""
        self._append(
            "tool_calls.jsonl",
            {
                "call": call.model_dump(mode="json"),
                "result": result.model_dump(mode="json"),
            },
        )

    def record_provider_response(self, response: LLMResponse) -> None:
        """Persist credential-free model, usage, request, and retry metadata."""
        metadata: ProviderMetadata = response.metadata
        responses = self._provider_document["responses"]
        assert isinstance(responses, list)
        responses.append(
            {
                **metadata.model_dump(mode="json"),
                "usage": response.usage.model_dump(mode="json"),
            }
        )
        self._write_provider_document()

    def record_fallback(self, error_code: str, error_message: str) -> None:
        """Record a safe fallback without exception bodies or credentials."""
        self._append(
            "fallbacks.jsonl",
            {
                "error_code": error_code,
                "error_message": error_message,
            },
        )

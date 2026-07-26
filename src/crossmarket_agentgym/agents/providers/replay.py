"""Strict offline recording and request-matched replay."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from crossmarket_agentgym.agents.providers.base import request_fingerprint
from crossmarket_agentgym.agents.providers.models import (
    GenerationConfig,
    LLMResponse,
    Message,
    ProviderError,
    StrictProviderModel,
)
from crossmarket_agentgym.agents.tools.models import ToolDefinition
from crossmarket_agentgym.audit.logging import redact_value
from crossmarket_agentgym.config.models import REQUIRED_AGENT_MODEL


class ReplayRecord(StrictProviderModel):
    """One canonical request identity and its credential-free response."""

    schema_version: Literal["1.0"] = "1.0"
    request_sha256: str
    response: LLMResponse


class ReplayJournal:
    """Append responses in strict JSONL format for later offline replay."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, request_sha256: str, response: LLMResponse) -> None:
        """Append one redacted response without storing request headers."""
        record = ReplayRecord(
            request_sha256=request_sha256,
            response=LLMResponse.model_validate(
                redact_value(response.model_dump(mode="json"))
            ),
        )
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(
                json.dumps(
                    record.model_dump(mode="json"),
                    allow_nan=False,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            )


class ReplayProvider:
    """Replay exact request hashes sequentially and never access the network."""

    name = "replay"

    def __init__(
        self,
        path: str | Path,
        *,
        model: str = REQUIRED_AGENT_MODEL,
    ) -> None:
        if model != REQUIRED_AGENT_MODEL:
            raise ValueError(f"model must be {REQUIRED_AGENT_MODEL!r}")
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        self.model = model
        self._records = self._load()
        self._cursor = 0

    def _load(self) -> list[ReplayRecord]:
        records: list[ReplayRecord] = []
        with self.path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(ReplayRecord.model_validate_json(line))
                except ValueError as error:
                    raise ValueError(
                        f"invalid replay record on line {line_number}"
                    ) from error
        if not records:
            raise ValueError("replay journal contains no records")
        return records

    def generate(
        self,
        messages: list[Message],
        response_schema: type[BaseModel] | None,
        tools: list[ToolDefinition] | None,
        generation_config: GenerationConfig,
    ) -> LLMResponse:
        """Return the next response only when the canonical request matches."""
        if self._cursor >= len(self._records):
            raise ProviderError("replay_exhausted", "replay journal is exhausted")
        expected = request_fingerprint(
            messages,
            response_schema,
            tools,
            generation_config,
        )
        record = self._records[self._cursor]
        if record.request_sha256 != expected:
            raise ProviderError(
                "replay_mismatch",
                "replay request does not match the recorded request",
            )
        self._cursor += 1
        metadata = record.response.metadata.model_copy(
            update={
                "provider": self.name,
                "model": self.model,
                "request_sha256": expected,
                "replayed": True,
            }
        )
        return record.response.model_copy(update={"metadata": metadata})

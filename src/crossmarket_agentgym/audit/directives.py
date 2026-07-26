"""Credential-redacted append-only journal for Phase 7 domain directives."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from crossmarket_agentgym.audit.logging import redact_value


class DirectiveRecord(BaseModel):
    """One hash-verified typed-directive audit event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1)
    timestamp: str
    kind: str
    payload: dict[str, Any]
    payload_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def _canonical(value: dict[str, Any]) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


class DirectiveJournal:
    """Persist validated instructions independently of Provider message Replay."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._sequence = 0

    def append(self, kind: str, value: BaseModel | dict[str, Any]) -> DirectiveRecord:
        """Redact, hash, and append one directive or fusion artifact."""
        raw = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
        payload = redact_value(raw)
        if not isinstance(payload, dict):
            raise TypeError("directive journal payload must remain a mapping")
        canonical = _canonical(payload)
        self._sequence += 1
        record = DirectiveRecord(
            sequence=self._sequence,
            timestamp=datetime.now(UTC).isoformat(),
            kind=kind,
            payload=payload,
            payload_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
        )
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(_canonical(record.model_dump(mode="json")) + "\n")
        return record


def load_directive_journal(path: Path) -> tuple[DirectiveRecord, ...]:
    """Load and verify every payload hash and monotonic sequence."""
    records: list[DirectiveRecord] = []
    with path.open(encoding="utf-8") as stream:
        for expected_sequence, line in enumerate(stream, start=1):
            record = DirectiveRecord.model_validate_json(line)
            if record.sequence != expected_sequence:
                raise ValueError("directive journal sequence mismatch")
            digest = hashlib.sha256(_canonical(record.payload).encode()).hexdigest()
            if digest != record.payload_sha256:
                raise ValueError("directive journal payload hash mismatch")
            records.append(record)
    return tuple(records)

"""Thread-safe Phase 6 team topology and arbitration audit."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

from crossmarket_agentgym.agents.models import (
    AgentExecutionResult,
    AgentInstance,
    TeamRunResult,
    TeamSpec,
)
from crossmarket_agentgym.audit.logging import redact_value


class RuntimeAuditWriter:
    """Persist expanded identities, topology events, and the final team result."""

    def __init__(self, run_dir: Path) -> None:
        self.agent_dir = run_dir / "agent"
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        self._sequence = 0
        self._lock = Lock()

    def _write_json(self, path: Path, value: Any) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                redact_value(value),
                allow_nan=False,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    def record_team(
        self,
        team: TeamSpec,
        instances: tuple[AgentInstance, ...],
    ) -> None:
        """Record credential-free resolved topology and independent seeds."""
        self._write_json(
            self.agent_dir / "team.resolved.json",
            {
                "team": team.model_dump(mode="json", exclude={"agents"}),
                "agents": [
                    {
                        "instance_id": item.instance_id,
                        "index": item.index,
                        "seed": item.seed,
                        "type": item.spec.type,
                        "base_name": item.spec.name,
                        "provider": item.spec.provider,
                        "model": item.spec.model,
                        "tools": item.spec.tools,
                        "weight": item.spec.weight,
                    }
                    for item in instances
                ],
            },
        )

    def record_result(self, result: AgentExecutionResult) -> None:
        """Append one partial success, fallback, failure, or timeout."""
        with self._lock:
            self._sequence += 1
            payload = {
                "sequence": self._sequence,
                "timestamp": datetime.now(UTC).isoformat(),
                "event": "agent_invocation",
                "result": result.model_dump(mode="json"),
            }
            path = self.agent_dir / "runtime_events.jsonl"
            with path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(
                    json.dumps(
                        redact_value(payload),
                        allow_nan=False,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    + "\n"
                )

    def record_summary(self, summary: TeamRunResult) -> None:
        """Write the terminal team aggregate atomically."""
        self._write_json(
            self.agent_dir / "team_summary.json",
            summary.model_dump(mode="json"),
        )

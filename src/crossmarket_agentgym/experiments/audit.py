"""Append-only formal-run lifecycle and provenance evidence."""

from __future__ import annotations

import hashlib
import os
import platform
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import torch
from pydantic import BaseModel, ConfigDict, Field

from crossmarket_agentgym.experiments.matrix import FormalTask, RunStatus


class FormalRunEvent(BaseModel):
    """One immutable run-lifecycle event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    sequence: int = Field(ge=1)
    event: RunStatus
    recorded_at: datetime
    message: str | None = None


class FormalArtifact(BaseModel):
    """One content-addressed formal result file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class FormalRunRecord(BaseModel):
    """Current auditable state written after each lifecycle event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    task: FormalTask
    status: RunStatus
    started_at: datetime | None
    finished_at: datetime | None
    wall_time_seconds: float | None = Field(default=None, ge=0.0)
    python_version: str
    platform: str
    cpu_model: str
    gpu_model: str | None
    torch_version: str
    cuda_available: bool
    process_id: int = Field(ge=1)
    failure_type: str | None = None
    failure_reason: str | None = None
    test_partition_accessed: bool = False
    test_partition_access_count: int = Field(default=0, ge=0)
    test_access_authorized: bool = False
    configuration_lock_present_before_test: bool = False
    development_result_accessed: bool = False
    network_accessed: bool = False
    network_access_authorized: bool = False
    account_state_mutated_externally: bool = False
    artifacts: tuple[FormalArtifact, ...] = ()


class FormalRunAudit:
    """Retain failed and successful formal runs under a unique directory."""

    def __init__(self, task: FormalTask, output_root: Path) -> None:
        self.task = task
        self.run_dir = output_root / task.run_id
        if self.run_dir.exists():
            raise FileExistsError(f"formal run already exists: {self.run_dir}")
        self.run_dir.mkdir(parents=True)
        self._started_at: datetime | None = None
        self._started_counter: float | None = None
        self._events: list[FormalRunEvent] = []
        self._write_state("planned")

    def _runtime_fields(self) -> dict[str, Any]:
        gpu = (
            torch.cuda.get_device_name(torch.cuda.current_device())
            if torch.cuda.is_available()
            else None
        )
        return {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "cpu_model": platform.processor().strip() or platform.machine() or "unknown",
            "gpu_model": gpu,
            "torch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "process_id": os.getpid(),
        }

    def _write_state(
        self,
        status: RunStatus,
        *,
        failure: BaseException | None = None,
        inventory_artifacts: bool = False,
        audit_fields: dict[str, Any] | None = None,
    ) -> FormalRunRecord:
        now = datetime.now(UTC)
        if status == "running" and self._started_at is None:
            self._started_at = now
            self._started_counter = time.perf_counter()
        terminal = status in {"completed", "failed", "blocked"}
        wall_time = (
            time.perf_counter() - self._started_counter
            if terminal and self._started_counter is not None
            else None
        )
        event = FormalRunEvent(
            run_id=self.task.run_id,
            sequence=len(self._events) + 1,
            event=status,
            recorded_at=now,
            message=str(failure) if failure is not None else None,
        )
        self._events.append(event)
        with (self.run_dir / "events.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(event.model_dump_json() + "\n")
        artifacts: tuple[FormalArtifact, ...] = ()
        if inventory_artifacts:
            records: list[FormalArtifact] = []
            for path in sorted(self.run_dir.rglob("*"), key=lambda value: value.as_posix()):
                if not path.is_file() or path.name == "formal_run.json":
                    continue
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                records.append(
                    FormalArtifact(
                        path=path.relative_to(self.run_dir).as_posix(),
                        sha256=digest,
                        size_bytes=path.stat().st_size,
                    )
                )
            artifacts = tuple(records)
        record = FormalRunRecord(
            task=self.task,
            status=status,
            started_at=self._started_at,
            finished_at=now if terminal else None,
            wall_time_seconds=wall_time,
            failure_type=type(failure).__name__ if failure is not None else None,
            failure_reason=str(failure) if failure is not None else None,
            artifacts=artifacts,
            **(audit_fields or {}),
            **self._runtime_fields(),
        )
        (self.run_dir / "formal_run.json").write_text(
            record.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        return record

    def start(self) -> FormalRunRecord:
        """Record execution start."""
        return self._write_state("running")

    def complete(self, **audit_fields: Any) -> FormalRunRecord:
        """Record successful completion and content-address every result."""
        return self._write_state(
            "completed",
            inventory_artifacts=True,
            audit_fields=audit_fields,
        )

    def fail(self, error: BaseException) -> FormalRunRecord:
        """Retain the run directory and structured exception evidence."""
        return self._write_state("failed", failure=error, inventory_artifacts=True)

    def block(self, reason: str) -> FormalRunRecord:
        """Retain a fail-closed precondition result."""
        return self._write_state(
            "blocked",
            failure=RuntimeError(reason),
            inventory_artifacts=True,
        )

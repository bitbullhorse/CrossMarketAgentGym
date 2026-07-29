"""Internal result models for the immutable benchmark workflow."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class BenchmarkCheck(BaseModel):
    """One machine-verifiable benchmark invariant."""

    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    detail: str


class BenchmarkResult(BaseModel):
    """Structured output shared by build and verify commands."""

    model_config = ConfigDict(frozen=True)

    benchmark: Path
    benchmark_id: str
    is_valid: bool
    file_count: int
    run_count: int
    checks: tuple[BenchmarkCheck, ...]


class PaperExportResult(BaseModel):
    """Structured output for a non-mutating paper artifact export."""

    model_config = ConfigDict(frozen=True)

    benchmark: Path
    output: Path
    artifact_kind: str
    file_count: int
    is_valid: bool

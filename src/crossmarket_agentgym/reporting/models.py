"""Strict schemas for safe run browsing and SoftwareX reports."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RunKind = Literal["training", "tuning", "agent", "phase7"]
ReportPartition = Literal["validation", "test"]
ExperimentStatus = Literal["completed", "partial", "planned"]
ExperimentCategory = Literal[
    "environment_correctness",
    "algorithm_benchmark",
    "cross_stock_zero_shot",
    "leave_one_market_out",
    "market_mechanism_ablation",
    "agent_hpo_ablation",
]
Scalar = str | int | float | bool | None

_PORTABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
SOFTWAREX_CATEGORIES: frozenset[str] = frozenset(
    {
        "environment_correctness",
        "algorithm_benchmark",
        "cross_stock_zero_shot",
        "leave_one_market_out",
        "market_mechanism_ablation",
        "agent_hpo_ablation",
    }
)


class StrictReportModel(BaseModel):
    """Reject schema drift, mutation, and non-finite report values."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class RunRecord(StrictReportModel):
    """Whitelisted metadata extracted from one run directory."""

    run_id: str
    kind: RunKind
    relative_path: str
    status: str
    algorithm: str | None = None
    partitions: tuple[str, ...] = ()
    metrics: dict[str, dict[str, float]] = Field(default_factory=dict)
    attributes: dict[str, Scalar] = Field(default_factory=dict)
    artifact_count: int = Field(ge=0)
    source_files: tuple[str, ...]
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    warnings: tuple[str, ...] = ()

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        if _PORTABLE_ID.fullmatch(value) is None:
            raise ValueError("run_id contains unsupported path characters")
        return value


class RunIndex(StrictReportModel):
    """Deterministically ordered run browser payload."""

    schema_version: Literal["1.0"] = "1.0"
    runs_root: str
    runs: tuple[RunRecord, ...]
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class BenchmarkRow(StrictReportModel):
    """Comparable investment and resource metrics for one locked run."""

    run_id: str
    algorithm: str
    partition: ReportPartition
    seed: int | None = None
    mean_return: float | None = None
    sharpe: float | None = None
    sortino: float | None = None
    max_drawdown: float | None = None
    calmar: float | None = None
    cvar_95: float | None = None
    mean_turnover: float | None = None
    total_cost: float | None = None
    cross_seed_variance: float | None = None
    runtime_seconds: float | None = None


class BenchmarkComparison(StrictReportModel):
    """Descriptive comparison that cannot authorize HPO selection."""

    partition: ReportPartition
    selection_authority: Literal[False] = False
    rows: tuple[BenchmarkRow, ...]


class ExperimentDeclaration(StrictReportModel):
    """SoftwareX experiment readiness with explicit evidence provenance."""

    category: ExperimentCategory
    label: str = Field(min_length=1, max_length=200)
    status: ExperimentStatus
    evidence_paths: tuple[str, ...] = ()
    notes: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def completed_requires_evidence(self) -> ExperimentDeclaration:
        if self.status == "completed" and not self.evidence_paths:
            raise ValueError("completed experiment requires evidence_paths")
        return self


class SoftwareXReportConfig(StrictReportModel):
    """One-command, CPU-only report configuration."""

    report_id: str = "phase8-softwarex"
    title: str = Field(default="CrossMarketAgentGym SoftwareX Evidence", min_length=1)
    workspace_root: Path = Field(default=cast(Path, "."), validate_default=True)
    runs_root: Path = Field(default=cast(Path, "runs"), validate_default=True)
    output_dir: Path = Field(default=cast(Path, "reports"), validate_default=True)
    partition: ReportPartition = "validation"
    include_run_ids: tuple[str, ...] = ()
    max_runs: int = Field(default=500, ge=1, le=5000)
    max_json_bytes: int = Field(default=5_000_000, ge=1024, le=100_000_000)
    experiments: tuple[ExperimentDeclaration, ...]

    @field_validator("report_id")
    @classmethod
    def validate_report_id(cls, value: str) -> str:
        if _PORTABLE_ID.fullmatch(value) is None:
            raise ValueError("report_id contains unsupported path characters")
        return value

    @field_validator("include_run_ids")
    @classmethod
    def validate_run_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("include_run_ids must be unique")
        if any(_PORTABLE_ID.fullmatch(value) is None for value in values):
            raise ValueError("include_run_ids contains an unsupported identifier")
        return values

    @model_validator(mode="after")
    def require_softwarex_matrix(self) -> SoftwareXReportConfig:
        categories = [item.category for item in self.experiments]
        if len(categories) != len(set(categories)):
            raise ValueError("experiment categories must be unique")
        if set(categories) != SOFTWAREX_CATEGORIES:
            raise ValueError("all six SoftwareX experiment categories are required")
        return self


class ReportArtifact(StrictReportModel):
    """One generated artifact and its reproducibility digest."""

    relative_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class ReportManifest(StrictReportModel):
    """Self-contained provenance excluding the manifest's own digest."""

    schema_version: Literal["1.0"] = "1.0"
    report_id: str
    source_index_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifacts: tuple[ReportArtifact, ...]


class ReportBuildSummary(StrictReportModel):
    """CLI response for a completed deterministic report."""

    report_id: str
    report_dir: str
    markdown: str
    html: str
    run_browser: str
    manifest: str
    run_count: int = Field(ge=0)
    benchmark_rows: int = Field(ge=0)
    figure_count: int = Field(ge=0)
    source_index_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def load_softwarex_report_config(path: Path) -> SoftwareXReportConfig:
    """Load strict YAML without accessing any run or evidence path."""
    with path.open(encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise TypeError("report configuration must be a mapping")
    return SoftwareXReportConfig.model_validate(raw)

"""Phase 11 schemas for honest artifact verification and computational replay."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from crossmarket_agentgym.release.models import VerificationCheck
from crossmarket_agentgym.reporting.models import RunKind

ReproductionLevel = Literal[
    "artifact_verified",
    "bitwise_reproduced",
    "numerically_reproduced",
    "statistically_reproduced",
    "failed",
]
VerificationMode = Literal["artifact_integrity", "computational_replay"]
MetricName = Literal[
    "mean_return",
    "mean_reward",
    "max_drawdown",
    "mean_turnover",
    "total_cost",
]
RequiredInvariant = Literal[
    "trained_timesteps",
    "algorithm",
    "dataset_manifest_hash",
    "trainer_config_hash",
    "execution_protocol",
    "checkpoint_loadability",
]

_REQUIRED_METRICS = frozenset(
    {
        "mean_return",
        "mean_reward",
        "max_drawdown",
        "mean_turnover",
        "total_cost",
    }
)
_REQUIRED_INVARIANTS = frozenset(
    {
        "trained_timesteps",
        "algorithm",
        "dataset_manifest_hash",
        "trainer_config_hash",
        "execution_protocol",
        "checkpoint_loadability",
    }
)


def _default_absolute_tolerance() -> dict[MetricName, float]:
    return {
        "mean_return": 1.0e-6,
        "mean_reward": 1.0e-6,
        "max_drawdown": 1.0e-6,
        "mean_turnover": 1.0e-5,
        "total_cost": 1.0e-3,
    }


class StrictReproductionModel(BaseModel):
    """Reject silent Schema drift, mutation, and non-finite values."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class RelativeToleranceConfig(StrictReproductionModel):
    """Default relative tolerance applied to every compared validation metric."""

    default: float = Field(default=1.0e-3, ge=0.0)


class StatisticalToleranceConfig(StrictReproductionModel):
    """Bounded repeated-replay rule used only when a single replay is not numerical."""

    minimum_replays: int = Field(default=3, ge=2, le=100)
    standard_error_multiplier: float = Field(default=2.0, ge=0.0, le=10.0)


class ReproductionToleranceConfig(StrictReproductionModel):
    """Reviewed numerical, exact-invariant, and repeated-replay thresholds."""

    schema_version: Literal["1.0"] = "1.0"
    absolute_tolerance: dict[MetricName, float] = Field(
        default_factory=_default_absolute_tolerance
    )
    relative_tolerance: RelativeToleranceConfig = Field(
        default_factory=RelativeToleranceConfig
    )
    require_same: tuple[RequiredInvariant, ...] = (
        "trained_timesteps",
        "algorithm",
        "dataset_manifest_hash",
        "trainer_config_hash",
        "execution_protocol",
        "checkpoint_loadability",
    )
    statistical: StatisticalToleranceConfig = Field(
        default_factory=StatisticalToleranceConfig
    )

    @field_validator("absolute_tolerance")
    @classmethod
    def require_metric_tolerances(
        cls,
        value: dict[MetricName, float],
    ) -> dict[MetricName, float]:
        """Require one non-negative absolute tolerance for every core metric."""
        if set(value) != _REQUIRED_METRICS:
            raise ValueError(
                "absolute_tolerance must define exactly the five core metrics"
            )
        if any(tolerance < 0.0 for tolerance in value.values()):
            raise ValueError("absolute tolerances must be non-negative")
        return value

    @model_validator(mode="after")
    def require_safety_invariants(self) -> ReproductionToleranceConfig:
        """Prevent callers from weakening the mandatory exact comparisons."""
        if set(self.require_same) != _REQUIRED_INVARIANTS:
            raise ValueError("require_same must contain every mandatory invariant")
        if len(self.require_same) != len(_REQUIRED_INVARIANTS):
            raise ValueError("require_same cannot contain duplicate invariants")
        return self


class MetricComparison(StrictReproductionModel):
    """One source/replay validation-metric comparison."""

    source: float
    replay: float
    absolute_difference: float = Field(ge=0.0)
    relative_difference: float = Field(ge=0.0)
    absolute_tolerance: float = Field(ge=0.0)
    relative_tolerance: float = Field(ge=0.0)
    effective_tolerance: float = Field(ge=0.0)
    passed: bool


class InvariantComparison(StrictReproductionModel):
    """One value that must match exactly across source and replay."""

    source: str | int | bool
    replay: str | int | bool
    passed: bool


class CoreArtifactComparison(StrictReproductionModel):
    """Bitwise identity of one core source/replay artifact."""

    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    replay_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    passed: bool


class StatisticalMetricComparison(StrictReproductionModel):
    """Distribution-level comparison over repeated replay metric values."""

    source: float
    replay_count: int = Field(ge=2)
    replay_mean: float
    replay_std: float = Field(ge=0.0)
    standard_error: float = Field(ge=0.0)
    absolute_difference: float = Field(ge=0.0)
    allowed_difference: float = Field(ge=0.0)
    passed: bool


class ReproductionReport(StrictReproductionModel):
    """Phase 11 evidence that distinguishes verification from computation."""

    schema_version: Literal["1.0"] = "1.0"
    verification_mode: VerificationMode
    artifact_integrity_verified: bool
    computational_replay_executed: bool
    reproduction_level: ReproductionLevel
    bitwise_deterministic: bool
    within_tolerance: bool | None
    run_id: str
    source_run_id: str
    replay_run_id: str | None = None
    replay_relative_path: str | None = None
    kind: RunKind
    run_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    is_valid: bool
    deterministic_replay: bool
    network_used: Literal[False] = False
    account_state_mutated: Literal[False] = False
    test_partition_accessed_by_replay: Literal[False] = False
    test_metrics_used_for_selection: Literal[False] = False
    metric_comparison: dict[str, MetricComparison] = Field(default_factory=dict)
    invariant_comparison: dict[str, InvariantComparison] = Field(
        default_factory=dict
    )
    core_artifact_comparison: dict[str, CoreArtifactComparison] = Field(
        default_factory=dict
    )
    statistical_comparison: dict[str, StatisticalMetricComparison] = Field(
        default_factory=dict
    )
    checks: tuple[VerificationCheck, ...]


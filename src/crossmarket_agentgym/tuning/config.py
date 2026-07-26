"""Strict configuration for search, scheduling, and validation objectives."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal, cast

import yaml
from pydantic import Field, field_validator, model_validator

from crossmarket_agentgym.tuning.models import (
    Direction,
    SearchSpace,
    StrictTuningModel,
)

SearcherName = Literal[
    "random",
    "grid",
    "tpe",
    "cma_es",
    "nsga_ii",
    "pso",
    "genetic",
    "differential_evolution",
    "simulated_annealing",
]
SchedulerName = Literal["fifo", "median", "asha", "hyperband", "pbt"]
ExecutorName = Literal["local", "ray"]
_STUDY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class SearcherConfig(StrictTuningModel):
    """Union-like strict settings for all nine built-in search algorithms."""

    type: SearcherName = "random"
    seed: int = Field(default=1024, ge=0, le=2**32 - 1)
    population_size: int = Field(default=8, ge=2)
    startup_trials: int = Field(default=8, ge=2)
    candidate_count: int = Field(default=32, ge=2)
    gamma: float = Field(default=0.25, gt=0.0, lt=1.0)
    sigma: float = Field(default=0.25, gt=0.0)
    mutation_rate: float = Field(default=0.15, ge=0.0, le=1.0)
    inertia: float = Field(default=0.72, ge=0.0)
    cognitive: float = Field(default=1.49, ge=0.0)
    social: float = Field(default=1.49, ge=0.0)
    differential_weight: float = Field(default=0.8, gt=0.0)
    crossover_rate: float = Field(default=0.7, ge=0.0, le=1.0)
    temperature: float = Field(default=1.0, gt=0.0)
    cooling: float = Field(default=0.95, gt=0.0, lt=1.0)
    step_scale: float = Field(default=0.15, gt=0.0)


class SchedulerConfig(StrictTuningModel):
    """Independent resource scheduler settings."""

    type: SchedulerName = "fifo"
    direction: Direction | None = None
    grace_period: float = Field(default=1.0, gt=0.0)
    min_resource: float = Field(default=1.0, gt=0.0)
    max_resource: float = Field(default=81.0, gt=0.0)
    reduction_factor: int = Field(default=3, ge=2)
    min_trials: int = Field(default=3, ge=1)
    perturbation_interval: float = Field(default=10.0, gt=0.0)
    quantile_fraction: float = Field(default=0.25, gt=0.0, le=0.5)
    perturbation_factors: tuple[float, float] = (0.8, 1.2)

    @field_validator("perturbation_factors")
    @classmethod
    def validate_perturbation_factors(
        cls,
        values: tuple[float, float],
    ) -> tuple[float, float]:
        """Require at least one positive PBT perturbation factor."""
        if not values or any(value <= 0.0 for value in values):
            raise ValueError("perturbation_factors must be positive")
        return values

    @model_validator(mode="after")
    def validate_resource_geometry(self) -> SchedulerConfig:
        """Reject resource ranges that cannot create a valid schedule."""
        if self.max_resource < self.min_resource:
            raise ValueError("max_resource must be at least min_resource")
        if self.max_resource < self.grace_period:
            raise ValueError("max_resource must be at least grace_period")
        return self


class ObjectiveConfig(StrictTuningModel):
    """Benchmark or partition-safe PPO validation objective."""

    type: Literal["sphere", "rosenbrock", "ppo_validation"] = "sphere"
    base_train_config: Path | None = None
    budget_stage: Literal["stage_a", "stage_b"] = "stage_b"
    seeds: tuple[int, ...] = (1024, 2048, 4096, 8192, 16384)
    walk_forward_folds: int = Field(default=3, ge=1)
    walk_forward_stride: int | None = Field(default=None, ge=1)
    total_timesteps: int = Field(default=8, ge=1)
    mode: Literal["robust", "multi_objective"] = "robust"
    include_training_time: bool = False

    @field_validator("seeds")
    @classmethod
    def validate_seeds(cls, seeds: tuple[int, ...]) -> tuple[int, ...]:
        """Require stable, unique non-negative seeds."""
        if not seeds or any(seed < 0 for seed in seeds):
            raise ValueError("at least one non-negative seed is required")
        if len(seeds) != len(set(seeds)):
            raise ValueError("objective seeds must be unique")
        return seeds

    @model_validator(mode="after")
    def require_training_config(self) -> ObjectiveConfig:
        """Require a train config and a full Stage B evaluation budget."""
        if self.type == "ppo_validation" and self.base_train_config is None:
            raise ValueError("ppo_validation requires base_train_config")
        if self.type == "ppo_validation" and self.budget_stage == "stage_b":
            if len(self.seeds) < 5:
                raise ValueError("stage_b requires at least five seeds")
            if self.walk_forward_folds < 2:
                raise ValueError("stage_b requires walk-forward evaluation")
        return self


class SelectionConfig(StrictTuningModel):
    """Configurable final choice from completed or Pareto Trials."""

    strategy: Literal["primary", "weighted", "pareto_first"] = "primary"
    weights: tuple[float, ...] = ()

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, weights: tuple[float, ...]) -> tuple[float, ...]:
        """Reject negative or all-zero weighted selection."""
        if any(weight < 0.0 for weight in weights):
            raise ValueError("selection weights cannot be negative")
        if weights and not any(weight > 0.0 for weight in weights):
            raise ValueError("at least one selection weight must be positive")
        return weights


class ExecutorConfig(StrictTuningModel):
    """Optional resource placement independent of search and scheduling."""

    type: ExecutorName = "local"
    address: str | None = None
    num_cpus_per_trial: float = Field(default=1.0, gt=0.0)
    num_gpus_per_trial: float = Field(default=0.0, ge=0.0)
    shutdown_on_close: bool = True

    @model_validator(mode="after")
    def validate_local_resources(self) -> ExecutorConfig:
        """Keep the CPU executor free of misleading Ray/GPU placement."""
        if self.type == "local" and (
            self.address is not None or self.num_gpus_per_trial != 0.0
        ):
            raise ValueError("local executor cannot configure Ray address or GPU resources")
        return self


class TuningRunConfig(StrictTuningModel):
    """Complete CPU-first tuning study configuration."""

    study_name: str
    output_dir: Path = Field(
        default=cast(Path, "runs/tuning"),
        validate_default=True,
    )
    storage_path: Path = Field(
        default=cast(Path, "runs/tuning/study.sqlite3"),
        validate_default=True,
    )
    max_trials: int = Field(default=8, ge=1)
    batch_size: int = Field(default=1, ge=1)
    directions: tuple[Direction, ...] = ("maximize",)
    search_space: SearchSpace
    searcher: SearcherConfig = Field(default_factory=SearcherConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    objective: ObjectiveConfig = Field(default_factory=ObjectiveConfig)
    selection: SelectionConfig = Field(default_factory=SelectionConfig)
    executor: ExecutorConfig = Field(default_factory=ExecutorConfig)
    retrain_locked: bool = True
    retrain_seed: int = Field(default=7777, ge=0, le=2**32 - 1)
    retrain_timesteps: int | None = Field(default=None, ge=1)

    @field_validator("study_name")
    @classmethod
    def validate_study_name(cls, value: str) -> str:
        """Keep study artifact paths portable and deterministic."""
        if _STUDY_NAME.fullmatch(value) is None:
            raise ValueError("study_name contains unsupported path characters")
        return value

    @model_validator(mode="after")
    def validate_objective_count(self) -> TuningRunConfig:
        """Require directions to match the configured objective representation."""
        expected = (
            4 + int(self.objective.include_training_time)
            if self.objective.mode == "multi_objective"
            else 1
        )
        if len(self.directions) != expected:
            raise ValueError(f"objective mode requires {expected} directions")
        if self.selection.strategy == "weighted":
            if len(self.selection.weights) != len(self.directions):
                raise ValueError("weighted selection requires one weight per direction")
        elif self.selection.weights:
            raise ValueError("selection weights require the weighted strategy")
        if (
            self.objective.type == "ppo_validation"
            and self.retrain_locked
            and self.retrain_seed in self.objective.seeds
        ):
            raise ValueError("independent retrain seed must differ from HPO seeds")
        return self


def _normalize_search_space(raw: dict[str, Any]) -> dict[str, Any]:
    search_space = raw.get("search_space")
    if not isinstance(search_space, dict):
        return raw
    parameters = search_space.get("parameters")
    if not isinstance(parameters, dict):
        return raw
    normalized = dict(raw)
    normalized_space = dict(search_space)
    normalized_space["parameters"] = [
        {"name": name, **specification}
        for name, specification in parameters.items()
    ]
    normalized["search_space"] = normalized_space
    return normalized


def load_tuning_run_config(path: Path) -> TuningRunConfig:
    """Load strict YAML and support name-keyed parameter mappings."""
    with path.open(encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise TypeError("tuning configuration must be a mapping")
    config = TuningRunConfig.model_validate(_normalize_search_space(raw))
    if config.objective.base_train_config is not None:
        base_path = config.objective.base_train_config
        if not base_path.is_absolute():
            base_path = (path.parent / base_path).resolve()
        config = config.model_copy(
            update={
                "objective": config.objective.model_copy(
                    update={"base_train_config": base_path}
                )
            }
        )
    return config

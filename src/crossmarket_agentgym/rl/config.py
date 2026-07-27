"""Strict CPU-first training, split, and callback configuration."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from crossmarket_agentgym.environments import EnvironmentConfig
from crossmarket_agentgym.environments.observations import ObservationConfig
from crossmarket_agentgym.rl.policies import PolicyName

AlgorithmName = Literal["PPO", "SAC", "TD3", "A2C"]
_RUN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class StrictRLModel(BaseModel):
    """Reject unknown settings and runtime mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class TrainerConfig(StrictRLModel):
    """Algorithm and policy settings shared by every SB3 trainer."""

    algorithm: AlgorithmName = "PPO"
    policy: PolicyName = "shared_mlp"
    total_timesteps: int = Field(default=1000, ge=1)
    learning_rate: float = Field(default=3e-4, gt=0.0, le=1.0)
    gamma: float = Field(default=0.99, gt=0.0, le=1.0)
    n_steps: int = Field(default=64, ge=2)
    batch_size: int = Field(default=32, ge=2)
    n_epochs: int = Field(default=4, ge=1)
    buffer_size: int = Field(default=10_000, ge=2)
    learning_starts: int = Field(default=10, ge=0)
    train_freq: int = Field(default=1, ge=1)
    gradient_steps: int = Field(default=1, ge=1)
    tau: float = Field(default=0.005, gt=0.0, le=1.0)
    features_dim: int = Field(default=64, ge=8, le=1024)
    net_arch: tuple[int, ...] = (64, 64)
    transformer_model_dim: int = Field(default=32, ge=4, le=512)
    transformer_heads: int = Field(default=4, ge=1, le=32)
    transformer_layers: int = Field(default=1, ge=1, le=8)
    action_noise_std: float = Field(default=0.10, ge=0.0, le=2.0)
    device: Literal["auto", "cpu", "cuda"] = "cpu"
    seed: int = Field(default=1024, ge=0, le=2**32 - 1)
    deterministic_eval: bool = True
    eval_episodes: int = Field(default=1, ge=1, le=100)
    verbose: int = Field(default=0, ge=0, le=2)

    @field_validator("algorithm", mode="before")
    @classmethod
    def normalize_algorithm(cls, value: object) -> object:
        """Accept lower-case YAML while storing one canonical name."""
        return value.upper() if isinstance(value, str) else value

    @field_validator("net_arch")
    @classmethod
    def validate_net_arch(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        """Require a non-empty positive network architecture."""
        if not value or any(width < 1 for width in value):
            raise ValueError("net_arch must contain positive widths")
        return value

    @model_validator(mode="after")
    def validate_algorithm_geometry(self) -> TrainerConfig:
        """Reject incompatible rollout, replay, and attention settings."""
        if self.algorithm == "PPO" and self.batch_size > self.n_steps:
            raise ValueError("PPO batch_size cannot exceed n_steps for one CPU environment")
        if self.algorithm in {"SAC", "TD3"} and self.batch_size > self.buffer_size:
            raise ValueError("off-policy batch_size cannot exceed buffer_size")
        if self.transformer_model_dim % self.transformer_heads != 0:
            raise ValueError("transformer_model_dim must be divisible by transformer_heads")
        return self


class CallbackConfig(StrictRLModel):
    """Cadence and thresholds for every required training callback."""

    checkpoint_freq: int = Field(default=250, ge=0)
    validation_freq: int = Field(default=250, ge=0)
    early_stop_patience: int = Field(default=5, ge=0)
    finite_guard: bool = True
    max_drawdown: float | None = Field(default=0.80, ge=0.0, le=1.0)
    resource_monitor_freq: int = Field(default=100, ge=0)
    audit_freq: int = Field(default=1, ge=0)
    metrics_freq: int = Field(default=1, ge=0)


class TemporalSplitConfig(StrictRLModel):
    """Non-overlapping outcome intervals with shared boundary observations."""

    train_end_execution_index: int = Field(ge=1)
    validation_end_execution_index: int = Field(ge=2)
    test_end_execution_index: int | None = Field(default=None, ge=3)

    @model_validator(mode="after")
    def validate_order(self) -> TemporalSplitConfig:
        """Require monotonically increasing execution boundaries."""
        if self.validation_end_execution_index <= self.train_end_execution_index:
            raise ValueError("validation boundary must follow training boundary")
        if (
            self.test_end_execution_index is not None
            and self.test_end_execution_index <= self.validation_end_execution_index
        ):
            raise ValueError("test boundary must follow validation boundary")
        return self


class TrainRunConfig(StrictRLModel):
    """Complete local training workflow configuration."""

    dataset_root: Path
    output_dir: Path = Field(default=cast(Path, "runs"), validate_default=True)
    run_name: str = "ppo_cpu_quickstart"
    observation: ObservationConfig = Field(default_factory=ObservationConfig)
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    split: TemporalSplitConfig
    trainer: TrainerConfig = Field(default_factory=TrainerConfig)
    callbacks: CallbackConfig = Field(default_factory=CallbackConfig)

    @field_validator("run_name")
    @classmethod
    def validate_run_name(cls, value: str) -> str:
        """Keep run paths local and shell-independent."""
        if _RUN_NAME.fullmatch(value) is None:
            raise ValueError("run_name contains unsupported path characters")
        return value

    @model_validator(mode="after")
    def validate_observation_policy(self) -> TrainRunConfig:
        """Keep tensor-only extractors away from flattened market windows."""
        if (
            self.observation.market_window_layout == "flat"
            and self.trainer.policy in {"shared_mlp", "transformer"}
        ):
            raise ValueError(
                "flat market_window requires the mlp custom features extractor"
            )
        return self


def load_train_run_config(path: Path) -> TrainRunConfig:
    """Load a strict YAML training configuration."""
    with path.open(encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise TypeError("training configuration must be a mapping")
    return TrainRunConfig.model_validate(raw)

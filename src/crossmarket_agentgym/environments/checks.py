"""Environment compatibility and accounting smoke checks."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Literal

import numpy as np
import yaml
from gymnasium.utils.env_checker import check_env as gymnasium_check_env
from pydantic import BaseModel, ConfigDict, Field

from crossmarket_agentgym.environments.config import EnvironmentConfig
from crossmarket_agentgym.environments.observations import (
    MarketWindowLayout,
    ObservationConfig,
)
from crossmarket_agentgym.environments.panel import MarketDataPanel
from crossmarket_agentgym.environments.portfolio import CrossMarketPortfolioEnv


class EnvironmentCheckConfig(BaseModel):
    """Strict configuration for `cmag env check`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_root: Path
    seed: int = Field(default=1024, ge=0, le=2**32 - 1)
    smoke_steps: int = Field(default=1000, ge=1)
    observation: ObservationConfig = Field(default_factory=ObservationConfig)
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)


class EnvironmentCheckWarning(BaseModel):
    """One accepted or blocking compatibility warning."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    warning_code: str
    accepted: bool
    reason: str
    required_policy: str | None = None


class EnvironmentCheckSummary(BaseModel):
    """Serializable evidence from compatibility and random-action checks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    is_valid: bool
    gymnasium_check: Literal["passed"]
    sb3_check: Literal["passed", "skipped_not_installed"]
    smoke_steps: int
    resets: int
    finite_observations: bool
    finite_rewards: bool
    finite_values: bool
    max_accounting_error: float
    min_portfolio_value: float
    execution_protocol: str
    market_window_layout: MarketWindowLayout
    warnings: tuple[EnvironmentCheckWarning, ...] = ()


def load_environment_check_config(path: Path) -> EnvironmentCheckConfig:
    """Safely load a strict environment-check YAML file."""
    with path.open(encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise TypeError("environment check configuration must be a mapping")
    return EnvironmentCheckConfig.model_validate(raw)


def run_environment_checks(config: EnvironmentCheckConfig) -> EnvironmentCheckSummary:
    """Run Gymnasium/SB3 checks and a seeded random-action accounting smoke test."""
    panel = MarketDataPanel.from_manifest(
        config.dataset_root,
        base_currency=config.environment.base_currency,
    )
    env = CrossMarketPortfolioEnv(
        panel,
        config.environment,
        observation=config.observation,
    )
    gymnasium_check_env(env, skip_render_check=True)
    sb3_status: Literal["passed", "skipped_not_installed"]
    captured_warnings: list[warnings.WarningMessage] = []
    try:
        from stable_baselines3.common.env_checker import check_env as sb3_check_env
    except ImportError:
        sb3_status = "skipped_not_installed"
    else:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            sb3_check_env(env, warn=True, skip_render_check=True)
            captured_warnings = list(captured)
        sb3_status = "passed"
    compatibility_warnings: list[EnvironmentCheckWarning] = []
    if config.observation.market_window_layout == "tensor":
        compatibility_warnings.append(
            EnvironmentCheckWarning(
                warning_code="SB3_BOX_IMAGE_HEURISTIC",
                accepted=True,
                reason="market_window is a financial tensor, not an image",
                required_policy="custom_features_extractor",
            )
        )
    if captured_warnings:
        expected_fragments = (
            "observation market_window is an image",
            "observation space market_window is an image",
            "Treating image space as channels-last",
            "minimal resolution for an image",
        )
        for item in captured_warnings:
            message = str(item.message)
            expected_tensor_warning = (
                config.observation.market_window_layout == "tensor"
                and any(fragment in message for fragment in expected_fragments)
            )
            if not expected_tensor_warning:
                compatibility_warnings.append(
                    EnvironmentCheckWarning(
                        warning_code="SB3_UNEXPECTED_WARNING",
                        accepted=False,
                        reason=message[:500],
                    )
                )

    observation, _ = env.reset(seed=config.seed)
    finite_observations = all(np.isfinite(value).all() for value in observation.values())
    finite_rewards = True
    finite_values = True
    max_accounting_error = 0.0
    min_portfolio_value = config.environment.initial_cash
    resets = 0
    for _ in range(config.smoke_steps):
        action = env.action_space.sample()
        observation, reward, terminated, truncated, info = env.step(action)
        finite_observations &= all(
            np.isfinite(value).all() for value in observation.values()
        )
        finite_rewards &= bool(np.isfinite(reward))
        value = float(info["portfolio_value"])
        finite_values &= bool(np.isfinite(value))
        min_portfolio_value = min(min_portfolio_value, value)
        max_accounting_error = max(
            max_accounting_error, float(info["accounting_error"])
        )
        if terminated or truncated:
            observation, _ = env.reset()
            resets += 1
    is_valid = (
        finite_observations
        and finite_rewards
        and finite_values
        and max_accounting_error
        <= config.environment.accounting_tolerance
        * max(1.0, config.environment.initial_cash)
        and all(item.accepted for item in compatibility_warnings)
    )
    return EnvironmentCheckSummary(
        is_valid=is_valid,
        gymnasium_check="passed",
        sb3_check=sb3_status,
        smoke_steps=config.smoke_steps,
        resets=resets,
        finite_observations=finite_observations,
        finite_rewards=finite_rewards,
        finite_values=finite_values,
        max_accounting_error=max_accounting_error,
        min_portfolio_value=min_portfolio_value,
        execution_protocol=config.environment.execution_protocol,
        market_window_layout=config.observation.market_window_layout,
        warnings=tuple(compatibility_warnings),
    )

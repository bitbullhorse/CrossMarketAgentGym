"""Reward-function stability tests."""

from __future__ import annotations

import math

import pytest

from crossmarket_agentgym.environments import EnvironmentConfig
from crossmarket_agentgym.environments.rewards import RewardCalculator


@pytest.mark.parametrize(
    "reward_name",
    [
        "log_return",
        "return_minus_cost",
        "risk_adjusted",
        "differential_sharpe",
        "drawdown_penalty",
        "cvar_penalty",
    ],
)
def test_every_builtin_reward_is_finite(reward_name: str) -> None:
    """Every advertised reward handles short online histories safely."""
    calculator = RewardCalculator(EnvironmentConfig(reward=reward_name))  # type: ignore[arg-type]
    rewards = [
        calculator.calculate(
            net_return=value,
            gross_return=value + 0.001,
            cost_ratio=0.001,
            drawdown=0.05,
        )
        for value in (0.01, -0.02, 0.005)
    ]

    assert all(math.isfinite(value) for value in rewards)
    calculator.reset()

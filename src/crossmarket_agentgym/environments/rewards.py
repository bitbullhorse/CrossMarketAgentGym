"""Built-in portfolio reward functions with finite fallbacks."""

from __future__ import annotations

import math

import numpy as np

from crossmarket_agentgym.environments.config import EnvironmentConfig


class RewardCalculator:
    """Stateful online reward calculator reset at every episode."""

    def __init__(self, config: EnvironmentConfig) -> None:
        """Bind immutable reward settings."""
        self.config = config
        self._returns: list[float] = []
        self._previous_sharpe = 0.0

    def reset(self) -> None:
        """Clear online statistics between episodes."""
        self._returns.clear()
        self._previous_sharpe = 0.0

    def calculate(
        self,
        *,
        net_return: float,
        gross_return: float,
        cost_ratio: float,
        drawdown: float,
    ) -> float:
        """Calculate the configured finite scalar reward."""
        self._returns.append(net_return)
        reward_name = self.config.reward
        if reward_name == "log_return":
            reward = math.log(max(1.0 + net_return, 1e-12))
        elif reward_name == "return_minus_cost":
            reward = gross_return - cost_ratio
        elif reward_name == "risk_adjusted":
            volatility = float(np.std(self._returns[-20:], ddof=0))
            reward = net_return - self.config.risk_aversion * volatility
        elif reward_name == "differential_sharpe":
            sample = np.asarray(self._returns, dtype=np.float64)
            volatility = float(sample.std(ddof=0))
            sharpe = float(sample.mean() / volatility) if volatility > 1e-12 else 0.0
            reward = sharpe - self._previous_sharpe
            self._previous_sharpe = sharpe
        elif reward_name == "drawdown_penalty":
            reward = net_return - self.config.drawdown_penalty * drawdown
        elif reward_name == "cvar_penalty":
            sample = np.sort(np.asarray(self._returns, dtype=np.float64))
            tail_count = max(1, int(np.ceil(len(sample) * self.config.cvar_alpha)))
            cvar = float(sample[:tail_count].mean())
            reward = net_return - self.config.cvar_penalty * abs(min(cvar, 0.0))
        else:  # pragma: no cover - Pydantic prevents unsupported names
            raise ValueError(f"unsupported reward: {reward_name}")
        if not math.isfinite(reward):
            raise ValueError("reward calculation produced a non-finite value")
        return float(reward)

"""Publication-facing metrics derived from replayable evaluation records."""

from __future__ import annotations

import math
from typing import Any

import gymnasium as gym
import numpy as np
from numpy.typing import NDArray

from crossmarket_agentgym.data.partitions import require_partition
from crossmarket_agentgym.environments import CrossMarketPortfolioEnv
from crossmarket_agentgym.evaluation import EvaluationResult
from crossmarket_agentgym.evaluation.results import Predictor, TradeRecord, WeightRecord


def formal_portfolio_metrics(result: EvaluationResult) -> dict[str, float]:
    """Add annualized Sharpe and trade count without changing frozen artifacts."""
    returns: list[float] = []
    for episode in range(result.episodes):
        values = [
            row.portfolio_value for row in result.weights if row.episode == episode
        ]
        if len(values) > 1:
            array = np.asarray(values, dtype=np.float64)
            returns.extend((array[1:] / array[:-1] - 1.0).tolist())
    daily = np.asarray(returns, dtype=np.float64)
    standard_deviation = float(daily.std(ddof=1)) if daily.size > 1 else 0.0
    sharpe = (
        math.sqrt(252.0) * float(daily.mean()) / standard_deviation
        if standard_deviation > 0.0
        else 0.0
    )
    trade_count = sum(
        bool(np.any(np.abs(np.asarray(row.quantities, dtype=np.float64)) > 0.0))
        for row in result.trades
    )
    return {
        **result.metrics,
        "sharpe": float(sharpe),
        "trade_count": float(trade_count),
    }


def evaluate_formal_policy(
    env: gym.Env[dict[str, NDArray[Any]], NDArray[np.float32]],
    predictor: Predictor,
    *,
    algorithm: str,
    episodes: int,
    seed: int,
) -> tuple[EvaluationResult, dict[str, float]]:
    """Evaluate once while retaining invalid-order diagnostics needed by Group D."""
    base_env = env.unwrapped
    if not isinstance(base_env, CrossMarketPortfolioEnv):
        raise TypeError("formal evaluation requires CrossMarketPortfolioEnv")
    require_partition(base_env.partition, frozenset({"validation", "test"}))
    trades: list[TradeRecord] = []
    weights: list[WeightRecord] = []
    episode_returns: list[float] = []
    episode_rewards: list[float] = []
    invalid_order_count = 0
    total_steps = 0
    max_drawdown = 0.0
    total_turnover = 0.0
    total_cost = 0.0
    for episode in range(episodes):
        reset_predictor = getattr(predictor, "reset", None)
        if callable(reset_predictor):
            reset_predictor()
        observation, _ = env.reset(seed=seed + episode)
        initial_value = float(base_env.config.initial_cash)
        final_value = initial_value
        reward_sum = 0.0
        done = False
        step = 0
        while not done:
            action, _ = predictor.predict(observation, deterministic=True)
            observation, reward, terminated, truncated, info = env.step(
                np.asarray(action, dtype=np.float32)
            )
            step += 1
            total_steps += 1
            reward_sum += float(reward)
            final_value = float(info["portfolio_value"])
            drawdown = float(info["drawdown"])
            turnover = float(info["turnover"])
            cost = float(info["transaction_cost"]) + float(info["slippage"])
            rejected = tuple(info.get("rejected_orders", ()))
            invalid_order_count += sum(value is not None for value in rejected)
            max_drawdown = max(max_drawdown, drawdown)
            total_turnover += turnover
            total_cost += cost
            trades.append(
                TradeRecord(
                    episode=episode,
                    step=step,
                    signal_date=str(info["signal_date"]),
                    execution_date=str(info["execution_date"]),
                    quantities=np.asarray(
                        info["executed_quantities"], dtype=float
                    ).tolist(),
                    trade_value=float(info["trade_value"]),
                    transaction_cost=float(info["transaction_cost"]),
                    slippage=float(info["slippage"]),
                    turnover=turnover,
                )
            )
            weights.append(
                WeightRecord(
                    episode=episode,
                    step=step,
                    execution_date=str(info["execution_date"]),
                    projected=np.asarray(
                        info["projected_weights"], dtype=float
                    ).tolist(),
                    realized=np.asarray(
                        observation["portfolio_weights"], dtype=float
                    ).tolist(),
                    portfolio_value=final_value,
                    drawdown=drawdown,
                )
            )
            done = bool(terminated or truncated)
        episode_returns.append(final_value / initial_value - 1.0)
        episode_rewards.append(reward_sum)
    result = EvaluationResult(
        algorithm=algorithm,
        partition=base_env.partition.partition,
        episodes=episodes,
        evaluation_episodes=episodes,
        return_sample_count=len(episode_returns),
        reward_sample_count=len(episode_rewards),
        total_steps=total_steps,
        metrics={
            "mean_return": float(np.mean(episode_returns)),
            "std_return": float(np.std(episode_returns, ddof=0)),
            "mean_reward": float(np.mean(episode_rewards)),
            "max_drawdown": max_drawdown,
            "mean_turnover": total_turnover / total_steps,
            "total_cost": total_cost,
        },
        trades=trades,
        weights=weights,
    )
    diagnostics = {
        "invalid_order_count": float(invalid_order_count),
        "trade_count": formal_portfolio_metrics(result)["trade_count"],
    }
    return result, diagnostics

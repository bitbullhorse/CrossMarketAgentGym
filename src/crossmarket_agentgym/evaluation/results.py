"""Serializable evaluation records shared by RL and baseline policies."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Protocol

import gymnasium as gym
import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from crossmarket_agentgym.data.partitions import require_partition
from crossmarket_agentgym.environments import CrossMarketPortfolioEnv


class Predictor(Protocol):
    """Minimal prediction contract shared by SB3 models and baselines."""

    def predict(
        self,
        observation: dict[str, NDArray[Any]],
        *,
        deterministic: bool = True,
    ) -> tuple[NDArray[np.float32], Any]:
        """Return one action and optional recurrent state."""
        ...


class TradeRecord(BaseModel):
    """One environment transition's executed trade audit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    episode: int
    step: int
    signal_date: str
    execution_date: str
    quantities: list[float]
    trade_value: float
    transaction_cost: float
    slippage: float
    turnover: float


class WeightRecord(BaseModel):
    """One projected and realized portfolio record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    episode: int
    step: int
    execution_date: str
    projected: list[float]
    realized: list[float]
    portfolio_value: float
    drawdown: float


class EvaluationResult(BaseModel):
    """Metrics and replayable step records for one evaluated policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    algorithm: str
    partition: str
    episodes: int = Field(ge=1)
    total_steps: int = Field(ge=1)
    metrics: dict[str, float]
    trades: list[TradeRecord]
    weights: list[WeightRecord]


def evaluate_policy(
    env: gym.Env[dict[str, NDArray[Any]], NDArray[np.float32]],
    predictor: Predictor,
    *,
    algorithm: str,
    episodes: int = 1,
    deterministic: bool = True,
    seed: int = 1024,
) -> EvaluationResult:
    """Evaluate without granting a training path to validation/test metrics."""
    base_env = env.unwrapped
    if not isinstance(base_env, CrossMarketPortfolioEnv):
        raise TypeError("evaluation requires CrossMarketPortfolioEnv")
    capability = base_env.partition
    require_partition(
        capability,
        frozenset({"train", "validation", "test", "smoke"}),
    )
    trades: list[TradeRecord] = []
    weights: list[WeightRecord] = []
    episode_returns: list[float] = []
    episode_rewards: list[float] = []
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
            action, _ = predictor.predict(observation, deterministic=deterministic)
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
    return EvaluationResult(
        algorithm=algorithm,
        partition=capability.partition,
        episodes=episodes,
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


def write_evaluation_artifacts(result: EvaluationResult, output_dir: Path) -> None:
    """Write metrics, trades, and weights as separate deterministic JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics.json").write_text(
        json.dumps(
            result.model_dump(exclude={"trades", "weights"}),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (output_dir / "trades.json").write_text(
        TypeAdapter(list[TradeRecord]).dump_json(result.trades, indent=2).decode(),
        encoding="utf-8",
    )
    (output_dir / "weights.json").write_text(
        TypeAdapter(list[WeightRecord]).dump_json(result.weights, indent=2).decode(),
        encoding="utf-8",
    )

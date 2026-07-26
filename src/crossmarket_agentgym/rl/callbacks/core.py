"""Training safety, validation, resource, audit, and metrics callbacks."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from stable_baselines3.common.callbacks import BaseCallback, CheckpointCallback

from crossmarket_agentgym.data.partitions import require_partition
from crossmarket_agentgym.environments import CrossMarketPortfolioEnv
from crossmarket_agentgym.evaluation import evaluate_policy


def _jsonable(value: Any) -> Any:
    """Convert callback values into bounded JSON-compatible data."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def _append_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(_jsonable(payload), sort_keys=True) + "\n")


class FiniteGuardCallback(BaseCallback):
    """Abort immediately when rewards or observations contain NaN/Inf."""

    def _on_step(self) -> bool:
        rewards = np.asarray(self.locals.get("rewards", []), dtype=np.float64)
        if rewards.size and not np.isfinite(rewards).all():
            raise FloatingPointError("training reward contains NaN or Inf")
        observations = self.locals.get("new_obs")
        values = observations.values() if isinstance(observations, dict) else [observations]
        for value in values:
            if value is not None and not np.isfinite(np.asarray(value)).all():
                raise FloatingPointError("training observation contains NaN or Inf")
        return True


class MaxDrawdownGuardCallback(BaseCallback):
    """Stop training when an environment reports excessive drawdown."""

    def __init__(self, max_drawdown: float) -> None:
        super().__init__()
        self.max_drawdown = max_drawdown
        self.triggered = False

    def _on_step(self) -> bool:
        infos = self.locals.get("infos", [])
        self.triggered = any(
            float(info.get("drawdown", 0.0)) > self.max_drawdown
            for info in infos
        )
        return not self.triggered


class ResourceMonitorCallback(BaseCallback):
    """Record process time and optional CUDA allocation at a fixed cadence."""

    def __init__(self, frequency: int, output_path: Path) -> None:
        super().__init__()
        self.frequency = frequency
        self.output_path = output_path
        self._started = time.perf_counter()

    def _on_step(self) -> bool:
        if self.frequency and self.n_calls % self.frequency == 0:
            cuda_bytes = (
                int(torch.cuda.memory_allocated()) if torch.cuda.is_available() else 0
            )
            _append_json(
                self.output_path,
                {
                    "timesteps": self.num_timesteps,
                    "wall_seconds": time.perf_counter() - self._started,
                    "process_seconds": time.process_time(),
                    "cuda_allocated_bytes": cuda_bytes,
                },
            )
        return True


class AuditCallback(BaseCallback):
    """Persist deterministic environment decisions without credentials."""

    _FIELDS = (
        "signal_date",
        "execution_date",
        "clipping_reasons",
        "unresolved_constraints",
        "rejected_orders",
        "trade_value",
        "transaction_cost",
        "slippage",
        "turnover",
        "portfolio_value",
        "drawdown",
        "accounting_error",
    )

    def __init__(self, frequency: int, output_path: Path) -> None:
        super().__init__()
        self.frequency = frequency
        self.output_path = output_path

    def _on_step(self) -> bool:
        if self.frequency and self.n_calls % self.frequency == 0:
            selected = [
                {field: info[field] for field in self._FIELDS if field in info}
                for info in self.locals.get("infos", [])
            ]
            _append_json(
                self.output_path,
                {"timesteps": self.num_timesteps, "environments": selected},
            )
        return True


class MetricsWriterCallback(BaseCallback):
    """Write online reward and account metrics as JSON Lines."""

    def __init__(self, frequency: int, output_path: Path) -> None:
        super().__init__()
        self.frequency = frequency
        self.output_path = output_path

    def _on_step(self) -> bool:
        if self.frequency and self.n_calls % self.frequency == 0:
            rewards = np.asarray(self.locals.get("rewards", []), dtype=np.float64)
            infos = self.locals.get("infos", [])
            _append_json(
                self.output_path,
                {
                    "timesteps": self.num_timesteps,
                    "mean_reward": float(rewards.mean()) if rewards.size else 0.0,
                    "portfolio_values": [
                        float(info["portfolio_value"])
                        for info in infos
                        if "portfolio_value" in info
                    ],
                },
            )
        return True


@dataclass(slots=True)
class ValidationTracker:
    """Shared early-stopping state."""

    best_score: float = -math.inf
    evaluations: int = 0
    non_improving: int = 0


class ValidationEvaluationCallback(BaseCallback):
    """Evaluate only on a validation-capability environment."""

    def __init__(
        self,
        eval_env: CrossMarketPortfolioEnv,
        *,
        frequency: int,
        episodes: int,
        deterministic: bool,
        seed: int,
        tracker: ValidationTracker,
        output_path: Path,
    ) -> None:
        super().__init__()
        require_partition(eval_env.partition, frozenset({"validation"}))
        self.eval_env = eval_env
        self.frequency = frequency
        self.episodes = episodes
        self.deterministic = deterministic
        self.seed = seed
        self.tracker = tracker
        self.output_path = output_path

    def _on_step(self) -> bool:
        if not self.frequency or self.n_calls % self.frequency != 0:
            return True
        result = evaluate_policy(
            self.eval_env,
            self.model,
            algorithm=self.model.__class__.__name__,
            episodes=self.episodes,
            deterministic=self.deterministic,
            seed=self.seed,
        )
        score = result.metrics["mean_return"]
        self.tracker.evaluations += 1
        if score > self.tracker.best_score + 1e-12:
            self.tracker.best_score = score
            self.tracker.non_improving = 0
        else:
            self.tracker.non_improving += 1
        _append_json(
            self.output_path,
            {
                "timesteps": self.num_timesteps,
                "score": score,
                "best_score": self.tracker.best_score,
                "non_improving": self.tracker.non_improving,
            },
        )
        return True


class EarlyStopCallback(BaseCallback):
    """Stop after a configured number of non-improving validations."""

    def __init__(self, tracker: ValidationTracker, patience: int) -> None:
        super().__init__()
        self.tracker = tracker
        self.patience = patience
        self.triggered = False

    def _on_step(self) -> bool:
        self.triggered = (
            self.tracker.evaluations > 0
            and self.tracker.non_improving >= self.patience
        )
        return not self.triggered


class ModelCheckpointCallback(CheckpointCallback):
    """Named wrapper around the Stable-Baselines3 checkpoint callback."""

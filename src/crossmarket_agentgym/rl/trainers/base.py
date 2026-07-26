"""Unified trainer protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import gymnasium as gym
from stable_baselines3.common.callbacks import BaseCallback

from crossmarket_agentgym.evaluation import EvaluationResult
from crossmarket_agentgym.rl.artifacts import TrainingArtifact
from crossmarket_agentgym.rl.config import TrainerConfig


class RLTrainer(Protocol):
    """Common training, evaluation, save, and load contract."""

    algorithm_name: str

    def train(
        self,
        env: gym.Env[Any, Any],
        config: TrainerConfig,
        callbacks: list[BaseCallback],
    ) -> TrainingArtifact:
        """Train and persist a checkpoint."""
        ...

    def evaluate(
        self,
        env: gym.Env[Any, Any],
        checkpoint: Path,
        *,
        episodes: int = 1,
    ) -> EvaluationResult:
        """Evaluate a checkpoint."""
        ...

    def save(self, artifact: TrainingArtifact, path: Path) -> Path:
        """Save an artifact checkpoint and metadata."""
        ...

    def load(self, path: Path, env: gym.Env[Any, Any] | None = None) -> Any:
        """Load a model checkpoint."""
        ...

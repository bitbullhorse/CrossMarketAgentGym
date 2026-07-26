"""Unified Stable-Baselines3 trainer for PPO, SAC, TD3, and optional A2C."""

from __future__ import annotations

import hashlib
import platform
import random
from math import prod
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
import stable_baselines3
import torch
from stable_baselines3 import A2C, PPO, SAC, TD3
from stable_baselines3.common.base_class import BaseAlgorithm
from stable_baselines3.common.callbacks import BaseCallback, CallbackList
from stable_baselines3.common.noise import NormalActionNoise

from crossmarket_agentgym.data.partitions import require_partition
from crossmarket_agentgym.environments import CrossMarketPortfolioEnv
from crossmarket_agentgym.evaluation import EvaluationResult, evaluate_policy
from crossmarket_agentgym.rl.artifacts import TrainingArtifact, TrainingMetadata
from crossmarket_agentgym.rl.config import AlgorithmName, TrainerConfig
from crossmarket_agentgym.rl.policies import build_policy_kwargs

_ALGORITHMS: dict[AlgorithmName, type[BaseAlgorithm]] = {
    "PPO": PPO,
    "SAC": SAC,
    "TD3": TD3,
    "A2C": A2C,
}


def configure_reproducibility(seed: int) -> None:
    """Configure deterministic CPU behavior and seeded CUDA behavior."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


class SB3Trainer:
    """Algorithm-neutral implementation of the project trainer protocol."""

    def __init__(self, algorithm: AlgorithmName, run_dir: Path) -> None:
        """Bind one algorithm and deterministic output directory."""
        self.algorithm_name = algorithm
        self.run_dir = run_dir

    def _model_kwargs(
        self,
        env: gym.Env[Any, Any],
        config: TrainerConfig,
    ) -> dict[str, Any]:
        policy_kwargs = build_policy_kwargs(
            config.policy,
            features_dim=config.features_dim,
            net_arch=list(config.net_arch),
            transformer_model_dim=config.transformer_model_dim,
            transformer_heads=config.transformer_heads,
            transformer_layers=config.transformer_layers,
        )
        common: dict[str, Any] = {
            "learning_rate": config.learning_rate,
            "gamma": config.gamma,
            "policy_kwargs": policy_kwargs,
            "seed": config.seed,
            "device": config.device,
            "verbose": config.verbose,
        }
        if config.algorithm == "PPO":
            common.update(
                n_steps=config.n_steps,
                batch_size=config.batch_size,
                n_epochs=config.n_epochs,
            )
        elif config.algorithm == "A2C":
            common.update(n_steps=config.n_steps)
        else:
            common.update(
                buffer_size=config.buffer_size,
                learning_starts=config.learning_starts,
                batch_size=config.batch_size,
                train_freq=config.train_freq,
                gradient_steps=config.gradient_steps,
                tau=config.tau,
            )
            if config.algorithm == "TD3" and config.action_noise_std > 0.0:
                action_shape = env.action_space.shape
                if action_shape is None:
                    raise ValueError("TD3 requires a finite-dimensional action space")
                action_count = prod(action_shape)
                common["action_noise"] = NormalActionNoise(
                    mean=np.zeros(action_count),
                    sigma=np.full(action_count, config.action_noise_std),
                )
        return common

    def train(
        self,
        env: gym.Env[Any, Any],
        config: TrainerConfig,
        callbacks: list[BaseCallback],
    ) -> TrainingArtifact:
        """Train only with a training capability and persist final state."""
        if config.algorithm != self.algorithm_name:
            raise ValueError("trainer algorithm does not match configuration")
        base_env = env.unwrapped
        if not isinstance(base_env, CrossMarketPortfolioEnv):
            raise TypeError("SB3Trainer requires CrossMarketPortfolioEnv")
        require_partition(base_env.partition, frozenset({"train"}))
        configure_reproducibility(config.seed)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        model_class = _ALGORITHMS[self.algorithm_name]
        model = model_class(
            "MultiInputPolicy",
            env,
            **self._model_kwargs(env, config),
        )
        callback = CallbackList(callbacks) if callbacks else None
        model.learn(
            total_timesteps=config.total_timesteps,
            callback=callback,
            progress_bar=False,
        )
        checkpoint_path = self.run_dir / "checkpoints" / "final_model.zip"
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        model.save(checkpoint_path)
        canonical_config = config.model_dump_json()
        metadata = TrainingMetadata(
            algorithm=self.algorithm_name,
            policy=config.policy,
            requested_timesteps=config.total_timesteps,
            trained_timesteps=model.num_timesteps,
            seed=config.seed,
            config_sha256=hashlib.sha256(canonical_config.encode()).hexdigest(),
            checkpoint=checkpoint_path.relative_to(self.run_dir).as_posix(),
            dataset_id=base_env.partition.dataset_id,
            data_partition=base_env.partition.partition,
            dependencies={
                "python": platform.python_version(),
                "stable_baselines3": stable_baselines3.__version__,
                "torch": torch.__version__,
                "numpy": np.__version__,
            },
        )
        (self.run_dir / "training_artifact.json").write_text(
            metadata.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return TrainingArtifact(
            model=model,
            metadata=metadata,
            run_dir=self.run_dir,
            checkpoint_path=checkpoint_path,
        )

    def evaluate(
        self,
        env: gym.Env[Any, Any],
        checkpoint: Path,
        *,
        episodes: int = 1,
    ) -> EvaluationResult:
        """Load and evaluate a checkpoint on an explicitly labeled partition."""
        model = self.load(checkpoint, env)
        return evaluate_policy(
            env,
            model,
            algorithm=self.algorithm_name,
            episodes=episodes,
        )

    def save(self, artifact: TrainingArtifact, path: Path) -> Path:
        """Save a model plus a credential-free metadata sidecar."""
        path.parent.mkdir(parents=True, exist_ok=True)
        artifact.model.save(path)
        sidecar = path.with_suffix(".metadata.json")
        sidecar.write_text(
            artifact.metadata.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return path

    def load(
        self,
        path: Path,
        env: gym.Env[Any, Any] | None = None,
    ) -> BaseAlgorithm:
        """Load the bound algorithm on CPU unless its environment overrides it."""
        if not path.exists():
            raise FileNotFoundError(path)
        return _ALGORITHMS[self.algorithm_name].load(path, env=env, device="cpu")


def trainer_from_config(config: TrainerConfig, run_dir: Path) -> SB3Trainer:
    """Construct the unified trainer for an approved algorithm."""
    return SB3Trainer(config.algorithm, run_dir)

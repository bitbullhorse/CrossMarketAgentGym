"""Training callback behavior and artifact-output tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from crossmarket_agentgym.data import PartitionCapability
from crossmarket_agentgym.environments import (
    CrossMarketPortfolioEnv,
    EnvironmentConfig,
    MarketDataPanel,
)
from crossmarket_agentgym.rl import CallbackConfig, TrainerConfig
from crossmarket_agentgym.rl.callbacks import (
    FiniteGuardCallback,
    build_callbacks,
)
from crossmarket_agentgym.rl.trainers import trainer_from_config
from tests.helpers import make_us_ohlcv


def _partitioned_envs() -> tuple[CrossMarketPortfolioEnv, CrossMarketPortfolioEnv]:
    panel = MarketDataPanel.from_frame(make_us_ohlcv(days=10))
    environment = EnvironmentConfig(
        lookback=2,
        max_asset_weight=1.0,
        max_market_weight=1.0,
        cash_floor=0.0,
        max_turnover=2.0,
    )
    train = CrossMarketPortfolioEnv(
        panel,
        environment,
        partition=PartitionCapability(
            dataset_id="callbacks",
            partition="train",
            start_signal_index=1,
            end_execution_index=5,
        ),
    )
    validation = CrossMarketPortfolioEnv(
        panel,
        environment,
        partition=PartitionCapability(
            dataset_id="callbacks",
            partition="validation",
            start_signal_index=5,
            end_execution_index=9,
        ),
    )
    return train, validation


def test_finite_guard_raises_on_nonfinite_reward() -> None:
    """A non-finite reward cannot silently enter an optimizer."""
    callback = FiniteGuardCallback()
    callback.locals = {"rewards": np.array([np.nan])}

    with pytest.raises(FloatingPointError):
        callback._on_step()


def test_required_callbacks_write_evidence_during_training(tmp_path: Path) -> None:
    """Checkpoint, validation, resource, audit, and metrics callbacks compose."""
    train_env, validation_env = _partitioned_envs()
    trainer_config = TrainerConfig(
        algorithm="PPO",
        policy="mlp",
        total_timesteps=16,
        n_steps=8,
        batch_size=4,
        n_epochs=1,
        features_dim=16,
        net_arch=(16,),
        eval_episodes=1,
    )
    callback_config = CallbackConfig(
        checkpoint_freq=4,
        validation_freq=4,
        early_stop_patience=2,
        finite_guard=True,
        max_drawdown=1.0,
        resource_monitor_freq=4,
        audit_freq=1,
        metrics_freq=1,
    )
    run_dir = tmp_path / "callbacks"
    callbacks, tracker = build_callbacks(
        callback_config,
        trainer_config,
        run_dir,
        validation_env=validation_env,
    )

    artifact = trainer_from_config(trainer_config, run_dir).train(
        train_env,
        trainer_config,
        callbacks,
    )

    assert artifact.checkpoint_path.exists()
    assert tracker.evaluations >= 1
    for name in (
        "validation.jsonl",
        "resources.jsonl",
        "audit.jsonl",
        "training_metrics.jsonl",
    ):
        assert (run_dir / name).stat().st_size > 0
    assert list((run_dir / "checkpoints").glob("step_*_steps.zip"))

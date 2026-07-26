"""CPU integration tests for the unified PPO/SAC/TD3 trainer."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from tests.helpers import make_us_ohlcv

from crossmarket_agentgym.data import PartitionCapability
from crossmarket_agentgym.environments import (
    CrossMarketPortfolioEnv,
    EnvironmentConfig,
    MarketDataPanel,
)
from crossmarket_agentgym.rl import TrainerConfig
from crossmarket_agentgym.rl.trainers import trainer_from_config


def _environments() -> tuple[CrossMarketPortfolioEnv, CrossMarketPortfolioEnv]:
    panel = MarketDataPanel.from_frame(make_us_ohlcv(days=10))
    config = EnvironmentConfig(
        lookback=2,
        initial_cash=10_000.0,
        max_asset_weight=1.0,
        max_market_weight=1.0,
        cash_floor=0.0,
        max_turnover=2.0,
    )
    train = CrossMarketPortfolioEnv(
        panel,
        config,
        partition=PartitionCapability(
            dataset_id="rl_fixture",
            partition="train",
            start_signal_index=1,
            end_execution_index=5,
        ),
    )
    validation = CrossMarketPortfolioEnv(
        panel,
        config,
        partition=PartitionCapability(
            dataset_id="rl_fixture",
            partition="validation",
            start_signal_index=5,
            end_execution_index=9,
        ),
    )
    return train, validation


@pytest.mark.integration
@pytest.mark.parametrize("algorithm", ["PPO", "SAC", "TD3", "A2C"])
def test_approved_algorithms_train_evaluate_and_reload(
    algorithm: str,
    tmp_path: Path,
) -> None:
    """Each required algorithm emits a reproducible checkpoint and evaluation."""
    train_env, validation_env = _environments()
    config = TrainerConfig(
        algorithm=algorithm,
        policy="mlp",
        total_timesteps=16,
        n_steps=8,
        batch_size=4,
        n_epochs=1,
        buffer_size=64,
        learning_starts=2,
        features_dim=16,
        net_arch=(16,),
        seed=11,
    )
    trainer = trainer_from_config(config, tmp_path / algorithm.lower())

    artifact = trainer.train(train_env, config, [])
    result = trainer.evaluate(validation_env, artifact.checkpoint_path)

    assert artifact.checkpoint_path.exists()
    assert artifact.metadata.algorithm == algorithm
    assert result.algorithm == algorithm
    assert result.partition == "validation"
    assert result.trades and result.weights

    observation, _ = validation_env.reset(seed=7)
    expected, _ = artifact.model.predict(observation, deterministic=True)
    loaded = trainer.load(artifact.checkpoint_path, validation_env)
    actual, _ = loaded.predict(observation, deterministic=True)
    np.testing.assert_allclose(actual, expected, atol=1e-7)
    if algorithm == "PPO":
        copied = trainer.save(artifact, tmp_path / "copied_model.zip")
        assert copied.exists()
        assert copied.with_suffix(".metadata.json").exists()


def test_trainer_rejects_test_partition(tmp_path: Path) -> None:
    """The model training API cannot consume a hidden test environment."""
    train_env, _ = _environments()
    test_env = CrossMarketPortfolioEnv(
        train_env.panel,
        train_env.config,
        partition=PartitionCapability(
            dataset_id="rl_fixture",
            partition="test",
            start_signal_index=5,
            end_execution_index=9,
        ),
    )
    config = TrainerConfig(
        algorithm="PPO",
        total_timesteps=8,
        n_steps=8,
        batch_size=4,
    )

    with pytest.raises(PermissionError):
        trainer_from_config(config, tmp_path / "blocked").train(test_env, config, [])


def test_fixed_seed_reproduces_deterministic_action(tmp_path: Path) -> None:
    """Independent CPU runs with one seed produce the same policy action."""
    first_train, first_validation = _environments()
    second_train, second_validation = _environments()
    config = TrainerConfig(
        algorithm="PPO",
        policy="mlp",
        total_timesteps=8,
        n_steps=8,
        batch_size=4,
        n_epochs=1,
        features_dim=16,
        net_arch=(16,),
        seed=23,
    )
    first = trainer_from_config(config, tmp_path / "first").train(
        first_train, config, []
    )
    second = trainer_from_config(config, tmp_path / "second").train(
        second_train, config, []
    )
    first_observation, _ = first_validation.reset(seed=23)
    second_observation, _ = second_validation.reset(seed=23)

    first_action, _ = first.model.predict(first_observation, deterministic=True)
    second_action, _ = second.model.predict(second_observation, deterministic=True)

    np.testing.assert_array_equal(first_action, second_action)

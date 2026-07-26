"""Partitioned training workflow and locked test evaluation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crossmarket_agentgym.rl import (
    CallbackConfig,
    TrainerConfig,
    TrainRunConfig,
    build_partitioned_environments,
    evaluate_saved_run,
    execute_training_run,
    load_train_run_config,
)


def _quick_config(tmp_path: Path, run_name: str) -> TrainRunConfig:
    base = load_train_run_config(Path("configs/train/ppo.yaml"))
    return base.model_copy(
        update={
            "output_dir": tmp_path,
            "run_name": run_name,
            "trainer": TrainerConfig(
                algorithm="PPO",
                policy="mlp",
                total_timesteps=8,
                n_steps=8,
                batch_size=4,
                n_epochs=1,
                features_dim=16,
                net_arch=(16,),
                eval_episodes=1,
                seed=17,
            ),
            "callbacks": CallbackConfig(
                checkpoint_freq=4,
                validation_freq=4,
                early_stop_patience=2,
                resource_monitor_freq=4,
                audit_freq=1,
                metrics_freq=1,
            ),
        }
    )


def test_training_never_reads_test_and_locked_evaluation_is_separate(
    tmp_path: Path,
) -> None:
    """Training emits validation outputs; test outputs appear only on evaluate."""
    config = _quick_config(tmp_path, "partitioned")
    training_environments = build_partitioned_environments(
        config,
        include_test=False,
    )

    summary = execute_training_run(config)
    run_dir = Path(summary.run_dir)

    assert "test" not in training_environments
    assert training_environments["train"].panel.dates[-1].isoformat() == "2024-01-04"
    assert (
        training_environments["validation"].panel.dates[-1].isoformat()
        == "2024-01-05"
    )
    assert (run_dir / "validation" / "metrics.json").exists()
    assert not (run_dir / "test").exists()
    test_result = evaluate_saved_run(run_dir)
    assert test_result.partition == "test"
    assert (run_dir / "test" / "trades.json").exists()
    metrics = json.loads(
        (run_dir / "test" / "metrics.json").read_text(encoding="utf-8")
    )
    assert "trades" not in metrics
    assert "weights" not in metrics
    assert isinstance(
        json.loads((run_dir / "test" / "weights.json").read_text(encoding="utf-8")),
        list,
    )
    with pytest.raises(FileExistsError, match="already exists"):
        evaluate_saved_run(run_dir)


def test_all_required_algorithm_configs_load() -> None:
    """The shipped PPO, SAC, and TD3 configurations are strict and resolvable."""
    algorithms = {
        load_train_run_config(Path(f"configs/train/{name}.yaml")).trainer.algorithm
        for name in ("ppo", "sac", "td3")
    }

    assert algorithms == {"PPO", "SAC", "TD3"}

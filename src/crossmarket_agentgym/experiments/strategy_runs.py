"""Protocol-derived Phase 12 strategy configurations and Group B execution."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import date
from pathlib import Path
from typing import Any, cast

from crossmarket_agentgym.environments import EnvironmentConfig, MarketDataPanel
from crossmarket_agentgym.environments.observations import ObservationConfig
from crossmarket_agentgym.evaluation import (
    baseline_by_name,
    evaluate_policy,
    write_evaluation_artifacts,
)
from crossmarket_agentgym.experiments.metrics import formal_portfolio_metrics
from crossmarket_agentgym.experiments.models import FormalExperimentProtocol
from crossmarket_agentgym.experiments.training import (
    build_formal_partitioned_environments,
    execute_formal_training_run,
)
from crossmarket_agentgym.rl.config import (
    AlgorithmName,
    CallbackConfig,
    TemporalSplitConfig,
    TrainerConfig,
    TrainRunConfig,
)
from crossmarket_agentgym.rl.workflow import (
    evaluate_saved_run,
)

_BASELINES = {
    "cash": "cash",
    "buy_and_hold": "buy_and_hold",
    "equal_weight": "equal_weight",
    "risk_parity": "risk_parity",
    "mean_variance": "mean_variance",
}


def _index_on_or_before(panel: MarketDataPanel, boundary: date) -> int:
    candidates = [index for index, value in enumerate(panel.dates) if value <= boundary]
    if not candidates:
        raise ValueError(f"dataset has no session on or before {boundary.isoformat()}")
    return candidates[-1]


def environment_config(protocol: FormalExperimentProtocol) -> EnvironmentConfig:
    """Map the frozen execution section without introducing run-time defaults."""
    execution = protocol.execution
    return EnvironmentConfig(
        execution_protocol=execution.signal_execution,
        base_currency=execution.base_currency,
        lookback=protocol.drl.lookback,
        initial_cash=execution.initial_cash,
        allow_short=execution.allow_short,
        max_leverage=execution.max_leverage,
        max_asset_weight=execution.max_asset_weight,
        max_market_weight=execution.max_market_weight,
        market_weight_overrides={},
        cash_floor=execution.cash_floor,
        max_turnover=execution.max_turnover,
        transaction_cost_bps=execution.transaction_cost_bps,
        slippage_bps=execution.slippage_bps,
        reward="risk_adjusted",
        risk_aversion=0.10,
        drawdown_penalty=0.50,
        cvar_alpha=0.05,
        cvar_penalty=0.50,
        lot_sizes={},
        t_plus_one_markets=frozenset(execution.t_plus_one_markets),
        max_episode_steps=None,
        accounting_tolerance=execution.accounting_tolerance,
    )


def formal_train_config(
    protocol: FormalExperimentProtocol,
    *,
    workspace_root: Path,
    run_name: str,
    output_dir: Path,
    algorithm: AlgorithmName,
    seed: int,
    total_timesteps: int | None = None,
) -> TrainRunConfig:
    """Create one exact default algorithm config and chronological split."""
    dataset_root = workspace_root / protocol.dataset.processed_root
    panel = MarketDataPanel.from_manifest(dataset_root)
    split = TemporalSplitConfig(
        train_end_execution_index=_index_on_or_before(
            panel, protocol.partitions.train.end
        ),
        validation_end_execution_index=_index_on_or_before(
            panel, protocol.partitions.validation.end
        ),
        test_end_execution_index=_index_on_or_before(
            panel, protocol.partitions.test.end
        ),
    )
    trainer = TrainerConfig(
        algorithm=algorithm,
        policy=protocol.drl.policy,
        total_timesteps=total_timesteps or protocol.drl.total_timesteps,
        learning_rate=3e-4,
        gamma=0.99,
        n_steps=256,
        batch_size=64,
        n_epochs=4,
        buffer_size=100_000,
        learning_starts=1_000,
        train_freq=1,
        gradient_steps=1,
        tau=0.005,
        features_dim=128,
        net_arch=(128, 128),
        transformer_model_dim=32,
        transformer_heads=4,
        transformer_layers=1,
        action_noise_std=0.10,
        device="auto",
        seed=seed,
        deterministic_eval=protocol.drl.deterministic_evaluation,
        eval_episodes=protocol.drl.evaluation_episodes,
        verbose=0,
    )
    callback_interval = max(1_000, trainer.total_timesteps // 10)
    return TrainRunConfig(
        dataset_root=dataset_root,
        output_dir=output_dir,
        run_name=run_name,
        observation=ObservationConfig(
            market_window_layout=protocol.drl.observation_layout
        ),
        environment=environment_config(protocol),
        split=split,
        trainer=trainer,
        callbacks=CallbackConfig(
            checkpoint_freq=callback_interval,
            validation_freq=callback_interval,
            early_stop_patience=5,
            finite_guard=True,
            max_drawdown=0.80,
            resource_monitor_freq=1_000,
            audit_freq=100,
            metrics_freq=100,
        ),
    )


def _write_lock(
    run_dir: Path,
    *,
    method: str,
    seed: int,
    resolved_config: dict[str, Any],
) -> str:
    payload = {
        "lock_version": "1.0",
        "method": method,
        "seed": seed,
        "selected_using": ["frozen_protocol", "train", "validation"],
        "test_metrics_read_before_lock": False,
        "resolved_config": resolved_config,
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path = run_dir / "configuration_lock.json"
    path.write_text(serialized, encoding="utf-8")
    digest = hashlib.sha256(serialized.encode()).hexdigest()
    (run_dir / "configuration_lock.sha256").write_text(
        f"{digest}  {path.name}\n",
        encoding="utf-8",
    )
    return digest


def run_group_b(
    *,
    protocol: FormalExperimentProtocol,
    workspace_root: Path,
    method: str,
    seed: int,
    run_dir: Path,
) -> dict[str, Any]:
    """Run one five-seed Group B method and lock before test access."""
    started = time.perf_counter()
    run_dir.mkdir(parents=True, exist_ok=True)
    normalized = method.lower()
    if normalized in _BASELINES:
        config = formal_train_config(
            protocol,
            workspace_root=workspace_root,
            run_name="baseline_context",
            output_dir=run_dir / "unused_training",
            algorithm="PPO",
            seed=seed,
            total_timesteps=1,
        )
        (run_dir / "resolved_config.json").write_text(
            config.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        _write_lock(
            run_dir,
            method=normalized,
            seed=seed,
            resolved_config=config.model_dump(mode="json"),
        )
        environments = build_formal_partitioned_environments(protocol, config)
        predictor = baseline_by_name(_BASELINES[normalized])
        validation = evaluate_policy(
            environments["validation"],
            predictor,
            algorithm=normalized,
            episodes=protocol.drl.evaluation_episodes,
            deterministic=True,
            seed=seed,
        )
        write_evaluation_artifacts(validation, run_dir / "validation")
        test = evaluate_policy(
            environments["test"],
            predictor,
            algorithm=normalized,
            episodes=protocol.drl.evaluation_episodes,
            deterministic=True,
            seed=seed,
        )
        write_evaluation_artifacts(test, run_dir / "test")
        return {
            "method": normalized,
            "seed": seed,
            "trained": False,
            "validation_metrics": formal_portfolio_metrics(validation),
            "test_metrics": formal_portfolio_metrics(test),
            "test_evaluation_count": 1,
            "runtime_seconds": time.perf_counter() - started,
        }
    algorithm_text = method.upper()
    if algorithm_text not in protocol.drl.algorithms:
        raise ValueError(f"unsupported Group B method: {method}")
    algorithm = cast(AlgorithmName, algorithm_text)
    config = formal_train_config(
        protocol,
        workspace_root=workspace_root,
        run_name="training",
        output_dir=run_dir / "model",
        algorithm=algorithm,
        seed=seed,
    )
    training = execute_formal_training_run(protocol, config)
    lock_hash = _write_lock(
        run_dir,
        method=algorithm,
        seed=seed,
        resolved_config=config.model_dump(mode="json"),
    )
    test = evaluate_saved_run(
        Path(training.run_dir),
        partition="test",
    )
    return {
        "method": algorithm,
        "seed": seed,
        "trained": True,
        "trained_timesteps": training.trained_timesteps,
        "validation_metrics": training.validation_metrics,
        "test_metrics": formal_portfolio_metrics(test),
        "configuration_lock_sha256": lock_hash,
        "test_evaluation_count": 1,
        "training_runtime_seconds": training.training_runtime_seconds,
        "evaluation_runtime_seconds": training.evaluation_runtime_seconds,
        "runtime_seconds": time.perf_counter() - started,
    }

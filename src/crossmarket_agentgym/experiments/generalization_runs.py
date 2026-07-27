"""Phase 12 Group C cross-market and unseen-stock experiments."""

from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from crossmarket_agentgym.data.manifests import sha256_file
from crossmarket_agentgym.data.partitions import PartitionCapability
from crossmarket_agentgym.environments import (
    CrossMarketPortfolioEnv,
    EnvironmentConfig,
    MarketDataPanel,
)
from crossmarket_agentgym.environments.observations import ObservationConfig
from crossmarket_agentgym.evaluation import evaluate_policy, write_evaluation_artifacts
from crossmarket_agentgym.experiments.metrics import formal_portfolio_metrics
from crossmarket_agentgym.experiments.models import FormalExperimentProtocol
from crossmarket_agentgym.experiments.strategy_runs import formal_train_config
from crossmarket_agentgym.experiments.training import (
    formal_train_start_signal_index,
)
from crossmarket_agentgym.rl.callbacks import build_callbacks
from crossmarket_agentgym.rl.trainers import trainer_from_config


def _asset_indices(
    panel: MarketDataPanel,
    *,
    markets: frozenset[str] | None = None,
    symbols: frozenset[tuple[str, str]] | None = None,
) -> frozenset[int]:
    selected: set[int] = set()
    for index, (market, symbol) in enumerate(
        zip(panel.markets, panel.symbols, strict=True)
    ):
        if markets is not None and market not in markets:
            continue
        if symbols is not None and (market, symbol) not in symbols:
            continue
        selected.add(index)
    if not selected:
        raise ValueError("formal asset selection is empty")
    return frozenset(selected)


def _masked_panel(
    panel: MarketDataPanel,
    *,
    active: frozenset[int],
    hide_inactive_features: bool,
) -> MarketDataPanel:
    mask = np.zeros(panel.asset_count, dtype=bool)
    mask[list(active)] = True
    tradable = panel.tradable_mask.copy()
    tradable[:, ~mask] = False
    features = panel.features.copy()
    if hide_inactive_features:
        features[:, ~mask, :] = 0.0
    suspension = panel.suspension_mask.copy()
    limit_up = panel.limit_up_mask.copy()
    limit_down = panel.limit_down_mask.copy()
    suspension[:, ~mask] = False
    limit_up[:, ~mask] = False
    limit_down[:, ~mask] = False
    return replace(
        panel,
        features=features,
        tradable_mask=tradable,
        suspension_mask=suspension,
        limit_up_mask=limit_up,
        limit_down_mask=limit_down,
    )


def _environment(
    panel: MarketDataPanel,
    config: EnvironmentConfig,
    *,
    dataset_id: str,
    partition: str,
    signal_index: int,
    end_index: int,
    active: frozenset[int],
) -> CrossMarketPortfolioEnv:
    context_start = max(0, signal_index - config.lookback + 1)
    sliced = panel.slice_sessions(context_start, end_index)
    masked = _masked_panel(sliced, active=active, hide_inactive_features=True)
    return CrossMarketPortfolioEnv(
        masked,
        config,
        observation=ObservationConfig(market_window_layout="flat"),
        partition=PartitionCapability(
            dataset_id=dataset_id,
            partition=partition,  # type: ignore[arg-type]
            start_signal_index=signal_index - context_start,
            end_execution_index=end_index - context_start,
        ),
    )


def _train_one(
    *,
    protocol: FormalExperimentProtocol,
    workspace_root: Path,
    seed: int,
    output_dir: Path,
    train_active: frozenset[int],
    test_active: frozenset[int],
    environment: EnvironmentConfig | None = None,
) -> dict[str, Any]:
    base_config = formal_train_config(
        protocol,
        workspace_root=workspace_root,
        run_name="context",
        output_dir=output_dir,
        algorithm="PPO",
        seed=seed,
    )
    config = environment or base_config.environment
    panel = MarketDataPanel.from_manifest(base_config.dataset_root)
    dataset_id = sha256_file(base_config.dataset_root / "dataset_manifest.json")
    split = base_config.split
    train = _environment(
        panel,
        config,
        dataset_id=dataset_id,
        partition="train",
        signal_index=formal_train_start_signal_index(
            panel,
            train_start=protocol.partitions.train.start,
            lookback=config.lookback,
        ),
        end_index=split.train_end_execution_index,
        active=train_active,
    )
    validation = _environment(
        panel,
        config,
        dataset_id=dataset_id,
        partition="validation",
        signal_index=split.train_end_execution_index,
        end_index=split.validation_end_execution_index,
        active=train_active,
    )
    test = _environment(
        panel,
        config,
        dataset_id=dataset_id,
        partition="test",
        signal_index=split.validation_end_execution_index,
        end_index=split.test_end_execution_index or split.validation_end_execution_index,
        active=test_active,
    )
    trainer = trainer_from_config(base_config.trainer, output_dir)
    callbacks, _ = build_callbacks(
        base_config.callbacks,
        base_config.trainer,
        output_dir,
        validation_env=validation,
    )
    started = time.perf_counter()
    artifact = trainer.train(train, base_config.trainer, callbacks)
    training_seconds = time.perf_counter() - started
    validation_result = evaluate_policy(
        validation,
        artifact.model,
        algorithm="PPO",
        episodes=protocol.drl.evaluation_episodes,
        deterministic=True,
        seed=seed,
    )
    write_evaluation_artifacts(validation_result, output_dir / "validation")
    lock = {
        "selected_using": ["frozen_protocol", "train", "validation"],
        "test_metrics_read_before_lock": False,
        "seed": seed,
        "train_active_indices": sorted(train_active),
        "test_active_indices": sorted(test_active),
        "trainer": base_config.trainer.model_dump(mode="json"),
    }
    (output_dir / "configuration_lock.json").write_text(
        json.dumps(lock, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    test_result = evaluate_policy(
        test,
        artifact.model,
        algorithm="PPO",
        episodes=protocol.drl.evaluation_episodes,
        deterministic=True,
        seed=seed,
    )
    write_evaluation_artifacts(test_result, output_dir / "test")
    return {
        "trained_timesteps": artifact.metadata.trained_timesteps,
        "training_runtime_seconds": training_seconds,
        "validation_metrics": formal_portfolio_metrics(validation_result),
        "test_metrics": formal_portfolio_metrics(test_result),
        "test_evaluation_count": 1,
        "train_active_indices": sorted(train_active),
        "test_active_indices": sorted(test_active),
    }


def _visible_and_held_out(
    panel: MarketDataPanel,
    protocol: FormalExperimentProtocol,
    workspace_root: Path,
) -> tuple[frozenset[tuple[str, str]], frozenset[tuple[str, str]]]:
    inventory = json.loads(
        (workspace_root / protocol.dataset.source_inventory).read_text(encoding="utf-8")
    )
    visible = frozenset(
        (market, symbol)
        for market, symbols in inventory["training_symbols"].items()
        for symbol in symbols
    )
    held_out = frozenset(
        (market, symbol)
        for market, symbols in inventory["held_out_symbols"].items()
        for symbol in symbols
    )
    panel_identities = frozenset(zip(panel.markets, panel.symbols, strict=True))
    if not visible.issubset(panel_identities) or not held_out.issubset(panel_identities):
        raise ValueError("source-inventory universe differs from the canonical panel")
    return visible, held_out


def run_group_c(
    *,
    protocol: FormalExperimentProtocol,
    workspace_root: Path,
    method: str,
    seed: int,
    run_dir: Path,
) -> dict[str, Any]:
    """Execute one frozen Group C method with target features hidden during training."""
    panel = MarketDataPanel.from_manifest(
        workspace_root / protocol.dataset.processed_root
    )
    visible, held_out = _visible_and_held_out(panel, protocol, workspace_root)
    all_markets = frozenset({"CN", "HK", "JP", "US"})

    def identities(markets: frozenset[str], pool: frozenset[tuple[str, str]]) -> frozenset[int]:
        return _asset_indices(panel, markets=markets, symbols=pool)

    routes = {
        "CN+HK+JP_to_US": "US",
        "CN+HK+US_to_JP": "JP",
        "CN+JP+US_to_HK": "HK",
        "HK+JP+US_to_CN": "CN",
    }
    subruns: dict[str, dict[str, Any]] = {}
    if method in routes:
        target = routes[method]
        subruns[target] = _train_one(
            protocol=protocol,
            workspace_root=workspace_root,
            seed=seed,
            output_dir=run_dir / f"target_{target}",
            train_active=identities(all_markets - {target}, visible),
            test_active=identities(frozenset({target}), visible),
        )
    elif method in {"leave_one_market_out", "single_market"}:
        for target in ("CN", "HK", "JP", "US"):
            train_markets = (
                all_markets - {target}
                if method == "leave_one_market_out"
                else frozenset({target})
            )
            subruns[target] = _train_one(
                protocol=protocol,
                workspace_root=workspace_root,
                seed=seed,
                output_dir=run_dir / f"target_{target}",
                train_active=identities(train_markets, visible),
                test_active=identities(frozenset({target}), visible),
            )
    elif method == "joint_market":
        subruns["joint"] = _train_one(
            protocol=protocol,
            workspace_root=workspace_root,
            seed=seed,
            output_dir=run_dir / "joint",
            train_active=identities(all_markets, visible),
            test_active=identities(all_markets, visible),
        )
    elif method == "unseen_stock":
        subruns["held_out"] = _train_one(
            protocol=protocol,
            workspace_root=workspace_root,
            seed=seed,
            output_dir=run_dir / "held_out",
            train_active=identities(all_markets, visible),
            test_active=identities(all_markets, held_out),
        )
    elif method == "market_rule_sensitivity":
        relaxed = base = formal_train_config(
            protocol,
            workspace_root=workspace_root,
            run_name="context",
            output_dir=run_dir,
            algorithm="PPO",
            seed=seed,
        ).environment
        relaxed = base.model_copy(update={"t_plus_one_markets": frozenset()})
        subruns["standardized_rules"] = _train_one(
            protocol=protocol,
            workspace_root=workspace_root,
            seed=seed,
            output_dir=run_dir / "standardized_rules",
            train_active=identities(all_markets, visible),
            test_active=identities(all_markets, visible),
            environment=relaxed,
        )
    else:
        raise ValueError(f"unsupported Group C method: {method}")
    return {
        "method": method,
        "seed": seed,
        "target_features_visible_during_training": False,
        "test_metrics_read_before_configuration_lock": False,
        "subruns": subruns,
    }

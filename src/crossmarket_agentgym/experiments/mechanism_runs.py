"""Phase 12 Group D safety-preserving market-mechanism ablations."""

from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from crossmarket_agentgym.data.fx import FXRateTable
from crossmarket_agentgym.data.manifests import sha256_file
from crossmarket_agentgym.environments import EnvironmentConfig, MarketDataPanel
from crossmarket_agentgym.evaluation import baseline_by_name, write_evaluation_artifacts
from crossmarket_agentgym.experiments.generalization_runs import (
    _asset_indices,
    _environment,
    _visible_and_held_out,
)
from crossmarket_agentgym.experiments.metrics import (
    evaluate_formal_policy,
    formal_portfolio_metrics,
)
from crossmarket_agentgym.experiments.models import FormalExperimentProtocol
from crossmarket_agentgym.experiments.strategy_runs import formal_train_config


def _constant_fx_panel(
    panel: MarketDataPanel,
    *,
    fx_path: Path,
    freeze_date: Any,
) -> MarketDataPanel:
    fx_frame = (
        pd.read_parquet(fx_path)
        if fx_path.suffix.lower() in {".parquet", ".pq"}
        else pd.read_csv(fx_path)
    )
    table = FXRateTable(fx_frame, quote_currency=panel.base_currency)
    features = panel.features.astype(np.float64, copy=True)
    opens = panel.open_prices.copy()
    closes = panel.close_prices.copy()
    for asset, currency in enumerate(panel.currencies):
        if currency == panel.base_currency:
            continue
        fixed = table.rate_on_or_before(freeze_date, currency)
        historical = np.asarray(
            [table.rate_on_or_before(day, currency) for day in panel.dates],
            dtype=np.float64,
        )
        scale = fixed / historical
        opens[:, asset] *= scale
        closes[:, asset] *= scale
        features[:, asset, 0:4] *= scale[:, None]
        close = np.maximum(closes[:, asset], 1e-12)
        log_return = np.zeros_like(close)
        log_return[1:] = np.log(close[1:] / close[:-1])
        features[:, asset, 5] = log_return
    return replace(
        panel,
        open_prices=opens,
        close_prices=closes,
        features=features.astype(np.float32),
    )


def _synchronous_execution_panel(
    panel: MarketDataPanel,
    *,
    active: frozenset[int],
) -> MarketDataPanel:
    tradable = panel.tradable_mask.copy()
    active_indices = np.asarray(sorted(active), dtype=int)
    active_markets = np.asarray(panel.markets, dtype=object)[active_indices]
    for session in range(panel.session_count):
        open_markets = {
            str(market)
            for market, is_open in zip(
                active_markets,
                tradable[session, active_indices],
                strict=True,
            )
            if is_open
        }
        if open_markets != {"CN", "HK", "JP", "US"}:
            tradable[session, :] = False
    return replace(panel, tradable_mask=tradable)


def _variant(
    method: str,
    *,
    config: EnvironmentConfig,
    panel: MarketDataPanel,
    protocol: FormalExperimentProtocol,
    workspace_root: Path,
    active: frozenset[int],
) -> tuple[EnvironmentConfig, MarketDataPanel, dict[str, Any]]:
    evidence: dict[str, Any] = {
        "deterministic_risk_layer_bypassed": False,
        "account_state_mutation_boundary_changed": False,
    }
    if method == "no_transaction_cost":
        return config.model_copy(update={"transaction_cost_bps": 0.0}), panel, evidence
    if method == "no_slippage":
        return config.model_copy(update={"slippage_bps": 0.0}), panel, evidence
    if method == "no_t_plus_one":
        return config.model_copy(update={"t_plus_one_markets": frozenset()}), panel, evidence
    if method == "no_price_limits":
        return config, replace(
            panel,
            limit_up_mask=np.zeros_like(panel.limit_up_mask),
            limit_down_mask=np.zeros_like(panel.limit_down_mask),
        ), evidence
    if method == "no_suspension":
        return config, replace(
            panel,
            tradable_mask=panel.tradable_without_suspension_mask.copy(),
            suspension_mask=np.zeros_like(panel.suspension_mask),
        ), evidence
    if method == "no_fx_variation":
        manifest = json.loads(
            (
                workspace_root / protocol.dataset.processed_manifest
            ).read_text(encoding="utf-8")
        )
        fx_entry = next(item for item in manifest["files"] if item["role"] == "fx")
        fixed_panel = _constant_fx_panel(
            panel,
            fx_path=workspace_root / protocol.dataset.processed_root / fx_entry["path"],
            freeze_date=protocol.partitions.train.end,
        )
        evidence["fx_frozen_as_of"] = protocol.partitions.train.end.isoformat()
        return config, fixed_panel, evidence
    if method == "synchronous_calendar":
        return config, _synchronous_execution_panel(panel, active=active), evidence
    if method == "no_turnover_cap":
        return config.model_copy(update={"max_turnover": 2.0}), panel, evidence
    if method == "minimum_deterministic_risk_projection":
        evidence["retained_constraints"] = [
            "long_only",
            "max_leverage_1",
            "finite_sum_one_weights",
            "nonnegative_cash",
            "execution_engine_only_account_mutation",
        ]
        return config.model_copy(
            update={
                "max_asset_weight": 1.0,
                "max_market_weight": 1.0,
                "cash_floor": 0.0,
                "max_turnover": 2.0,
            }
        ), panel, evidence
    raise ValueError(f"unsupported Group D method: {method}")


def _evaluate(
    *,
    env: Any,
    protocol: FormalExperimentProtocol,
    seed: int,
    output_dir: Path,
) -> tuple[dict[str, float], dict[str, float]]:
    predictor = baseline_by_name("equal_weight")
    result, diagnostics = evaluate_formal_policy(
        env,
        predictor,
        algorithm="equal_weight",
        episodes=protocol.drl.evaluation_episodes,
        seed=seed,
    )
    write_evaluation_artifacts(result, output_dir)
    return formal_portfolio_metrics(result), diagnostics


def run_group_d(
    *,
    protocol: FormalExperimentProtocol,
    workspace_root: Path,
    method: str,
    seed: int,
    run_dir: Path,
) -> dict[str, Any]:
    """Compare one mechanism ablation against the exact base environment."""
    run_dir.mkdir(parents=True, exist_ok=True)
    context = formal_train_config(
        protocol,
        workspace_root=workspace_root,
        run_name="context",
        output_dir=run_dir,
        algorithm="PPO",
        seed=seed,
        total_timesteps=1,
    )
    panel = MarketDataPanel.from_manifest(context.dataset_root)
    visible, _ = _visible_and_held_out(panel, protocol, workspace_root)
    active = _asset_indices(panel, symbols=visible)
    variant_config, variant_panel, evidence = _variant(
        method,
        config=context.environment,
        panel=panel,
        protocol=protocol,
        workspace_root=workspace_root,
        active=active,
    )
    split = context.split
    dataset_id = sha256_file(context.dataset_root / "dataset_manifest.json")
    end = split.test_end_execution_index or split.validation_end_execution_index
    base_env = _environment(
        panel,
        context.environment,
        dataset_id=dataset_id,
        partition="test",
        signal_index=split.validation_end_execution_index,
        end_index=end,
        active=active,
    )
    variant_env = _environment(
        variant_panel,
        variant_config,
        dataset_id=dataset_id,
        partition="test",
        signal_index=split.validation_end_execution_index,
        end_index=end,
        active=active,
    )
    lock = {
        "method": method,
        "strategy": "equal_weight",
        "selected_using": ["frozen_protocol"],
        "test_metrics_read_before_lock": False,
        "base_environment": context.environment.model_dump(mode="json"),
        "variant_environment": variant_config.model_dump(mode="json"),
        **evidence,
    }
    (run_dir / "configuration_lock.json").write_text(
        json.dumps(lock, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    started = time.perf_counter()
    base_metrics, base_diagnostics = _evaluate(
        env=base_env,
        protocol=protocol,
        seed=seed,
        output_dir=run_dir / "base" / "test",
    )
    variant_metrics, variant_diagnostics = _evaluate(
        env=variant_env,
        protocol=protocol,
        seed=seed,
        output_dir=run_dir / "variant" / "test",
    )
    runtime = time.perf_counter() - started
    return {
        "method": method,
        "seed": seed,
        "strategy": "equal_weight",
        "base_metrics": base_metrics | base_diagnostics,
        "variant_metrics": variant_metrics | variant_diagnostics,
        "runtime_seconds": runtime,
        "test_evaluation_count_per_arm": 1,
        **evidence,
    }

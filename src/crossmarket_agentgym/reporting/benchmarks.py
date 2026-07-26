"""Descriptive benchmark metrics derived from locked evaluation artifacts."""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from statistics import fmean, pstdev, pvariance
from typing import Any

from crossmarket_agentgym.reporting.io import read_bounded_json, resolve_inside
from crossmarket_agentgym.reporting.models import (
    BenchmarkComparison,
    BenchmarkRow,
    ReportPartition,
    RunIndex,
    RunRecord,
)


def _optional_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _attribute_number(record: RunRecord, name: str) -> float | None:
    return _optional_number(record.attributes.get(name))


def _daily_returns(
    record: RunRecord,
    workspace: Path,
    partition: ReportPartition,
    *,
    max_json_bytes: int,
) -> list[float]:
    run_dir = resolve_inside(record.relative_path, workspace)
    weights_path = run_dir / partition / "weights.json"
    config_path = run_dir / "resolved_config.json"
    if not weights_path.exists() or not config_path.exists():
        return []
    weights = read_bounded_json(weights_path, max_bytes=max_json_bytes)
    config = read_bounded_json(config_path, max_bytes=max_json_bytes)
    if not isinstance(weights, list) or not isinstance(config, dict):
        return []
    environment = config.get("environment")
    initial = (
        _optional_number(environment.get("initial_cash"))
        if isinstance(environment, dict)
        else None
    )
    if initial is None or initial <= 0.0:
        return []
    previous: dict[int, float] = {}
    returns: list[float] = []
    ordered = sorted(
        (item for item in weights if isinstance(item, dict)),
        key=lambda item: (int(item.get("episode", 0)), int(item.get("step", 0))),
    )
    for item in ordered:
        episode = int(item.get("episode", 0))
        value = _optional_number(item.get("portfolio_value"))
        if value is None or value <= 0.0:
            continue
        baseline = previous.get(episode, initial)
        returns.append(value / baseline - 1.0)
        previous[episode] = value
    return returns


def _risk_statistics(
    returns: list[float],
    mean_return: float | None,
    max_drawdown: float | None,
) -> tuple[float | None, float | None, float | None, float | None]:
    sharpe: float | None = None
    sortino: float | None = None
    cvar: float | None = None
    if returns:
        count = max(1, math.ceil(len(returns) * 0.05))
        cvar = fmean(sorted(returns)[:count])
    if len(returns) >= 2:
        deviation = pstdev(returns)
        if deviation > 1e-12:
            sharpe = fmean(returns) / deviation * math.sqrt(252.0)
        downside = [value for value in returns if value < 0.0]
        if len(downside) >= 2:
            downside_deviation = pstdev(downside)
            if downside_deviation > 1e-12:
                sortino = fmean(returns) / downside_deviation * math.sqrt(252.0)
    calmar = (
        mean_return / max_drawdown
        if mean_return is not None
        and max_drawdown is not None
        and max_drawdown > 1e-12
        else None
    )
    return sharpe, sortino, calmar, cvar


def _base_row(
    record: RunRecord,
    workspace: Path,
    partition: ReportPartition,
    *,
    max_json_bytes: int,
) -> BenchmarkRow | None:
    if record.kind != "training" or partition not in record.metrics:
        return None
    metrics = record.metrics[partition]
    mean_return = _optional_number(metrics.get("mean_return"))
    max_drawdown = _optional_number(metrics.get("max_drawdown"))
    returns = _daily_returns(
        record,
        workspace,
        partition,
        max_json_bytes=max_json_bytes,
    )
    sharpe, sortino, calmar, cvar = _risk_statistics(
        returns,
        mean_return,
        max_drawdown,
    )
    seed_value = record.attributes.get("seed")
    seed = int(seed_value) if isinstance(seed_value, int) else None
    return BenchmarkRow(
        run_id=record.run_id,
        algorithm=record.algorithm or "unknown",
        partition=partition,
        seed=seed,
        mean_return=mean_return,
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown=max_drawdown,
        calmar=calmar,
        cvar_95=cvar,
        mean_turnover=_optional_number(metrics.get("mean_turnover")),
        total_cost=_optional_number(metrics.get("total_cost")),
        runtime_seconds=_attribute_number(record, "runtime_seconds"),
    )


def build_benchmark_comparison(
    index: RunIndex,
    workspace_root: str | Path,
    *,
    partition: ReportPartition = "validation",
    max_json_bytes: int = 5_000_000,
) -> BenchmarkComparison:
    """Compare locked artifacts without producing a tuning winner."""
    workspace = Path(workspace_root).resolve()
    rows = [
        row
        for record in index.runs
        if (
            row := _base_row(
                record,
                workspace,
                partition,
                max_json_bytes=max_json_bytes,
            )
        )
        is not None
    ]
    grouped: dict[str, list[BenchmarkRow]] = defaultdict(list)
    for row in rows:
        grouped[row.algorithm].append(row)
    updated: list[BenchmarkRow] = []
    for row in rows:
        group = grouped[row.algorithm]
        distinct_seeds = {
            item.seed for item in group if item.seed is not None and item.mean_return is not None
        }
        values = [
            item.mean_return
            for item in group
            if item.seed in distinct_seeds and item.mean_return is not None
        ]
        variance = (
            pvariance(values)
            if len(distinct_seeds) >= 2 and len(values) >= 2
            else None
        )
        updated.append(row.model_copy(update={"cross_seed_variance": variance}))
    updated.sort(key=lambda item: (item.algorithm, item.run_id))
    return BenchmarkComparison(partition=partition, rows=tuple(updated))


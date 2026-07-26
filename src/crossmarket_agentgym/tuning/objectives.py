"""Validation-only robust and multi-objective portfolio scores."""

from __future__ import annotations

from statistics import median, pstdev

from pydantic import Field

from crossmarket_agentgym.tuning.models import (
    Direction,
    StrictTuningModel,
    TrialResult,
    dominates,
)


class ValidationRecord(StrictTuningModel):
    """One seed/fold result produced exclusively on validation data."""

    seed: int = Field(ge=0)
    fold: int = Field(ge=0)
    sharpe: float
    max_drawdown: float = Field(ge=0.0)
    turnover: float = Field(ge=0.0)
    training_seconds: float = Field(default=0.0, ge=0.0)


class RobustObjectiveConfig(StrictTuningModel):
    """Auditable weights for the default scalar robust score."""

    drawdown_weight: float = Field(default=0.5, ge=0.0)
    turnover_weight: float = Field(default=0.05, ge=0.0)
    instability_weight: float = Field(default=0.25, ge=0.0)


def seed_sharpe_instability(
    records: list[ValidationRecord] | tuple[ValidationRecord, ...],
) -> float:
    """Compute cross-seed dispersion after aggregating walk-forward folds."""
    if not records:
        raise ValueError("seed instability requires validation records")
    grouped: dict[int, list[float]] = {}
    for record in records:
        grouped.setdefault(record.seed, []).append(record.sharpe)
    per_seed = [median(values) for _, values in sorted(grouped.items())]
    return float(pstdev(per_seed))


def robust_portfolio_score(
    records: list[ValidationRecord] | tuple[ValidationRecord, ...],
    config: RobustObjectiveConfig | None = None,
) -> float:
    """Compute median Sharpe minus drawdown, turnover, and instability penalties."""
    if not records:
        raise ValueError("robust objective requires validation records")
    weights = config or RobustObjectiveConfig()
    sharpes = [record.sharpe for record in records]
    return float(
        median(sharpes)
        - weights.drawdown_weight * median(record.max_drawdown for record in records)
        - weights.turnover_weight * median(record.turnover for record in records)
        - weights.instability_weight * seed_sharpe_instability(records)
    )


def multi_objective_values(
    records: list[ValidationRecord] | tuple[ValidationRecord, ...],
    *,
    include_training_time: bool = False,
) -> tuple[float, ...]:
    """Return Sharpe/max-drawdown/turnover/instability objectives."""
    if not records:
        raise ValueError("multi-objective evaluation requires validation records")
    sharpes = [record.sharpe for record in records]
    values: tuple[float, ...] = (
        float(median(sharpes)),
        float(median(record.max_drawdown for record in records)),
        float(median(record.turnover for record in records)),
        seed_sharpe_instability(records),
    )
    if include_training_time:
        values += (float(median(record.training_seconds for record in records)),)
    return values


def default_multi_objective_directions(
    *,
    include_training_time: bool = False,
) -> tuple[Direction, ...]:
    """Return directions matching :func:`multi_objective_values`."""
    directions: tuple[Direction, ...] = (
        "maximize",
        "minimize",
        "minimize",
        "minimize",
    )
    return directions + (("minimize",) if include_training_time else ())


def pareto_front(
    results: list[TrialResult] | tuple[TrialResult, ...],
    directions: tuple[Direction, ...],
) -> list[TrialResult]:
    """Return the stable trial-ID-ordered nondominated completed set."""
    completed = [result for result in results if result.status == "completed"]
    front = [
        candidate
        for candidate in completed
        if not any(
            dominates(other, candidate, directions)
            for other in completed
            if other.trial_id != candidate.trial_id
        )
    ]
    return sorted(front, key=lambda item: item.trial_id)


def select_trial(
    results: list[TrialResult] | tuple[TrialResult, ...],
    directions: tuple[Direction, ...],
    *,
    strategy: str = "primary",
    weights: tuple[float, ...] = (),
) -> TrialResult | None:
    """Select a completed Trial by primary, weighted, or stable Pareto rule."""
    completed = [result for result in results if result.status == "completed"]
    if not completed:
        return None
    if strategy == "pareto_first":
        return pareto_front(completed, directions)[0]
    if strategy == "primary":
        sign = 1.0 if directions[0] == "maximize" else -1.0
        return max(
            completed,
            key=lambda result: (sign * result.objectives[0], -result.trial_id),
        )
    if strategy != "weighted" or len(weights) != len(directions):
        raise ValueError("invalid weighted Trial selection configuration")
    utilities = [
        [
            value if direction == "maximize" else -value
            for value, direction in zip(
                result.objectives,
                directions,
                strict=True,
            )
        ]
        for result in completed
    ]
    lows = [min(values[index] for values in utilities) for index in range(len(directions))]
    highs = [max(values[index] for values in utilities) for index in range(len(directions))]

    def score(index: int) -> tuple[float, int]:
        normalized = [
            1.0
            if highs[objective] == lows[objective]
            else (
                utilities[index][objective] - lows[objective]
            ) / (highs[objective] - lows[objective])
            for objective in range(len(directions))
        ]
        return (
            sum(
                weight * value
                for weight, value in zip(weights, normalized, strict=True)
            ),
            -completed[index].trial_id,
        )

    selected_index = max(range(len(completed)), key=score)
    return completed[selected_index]

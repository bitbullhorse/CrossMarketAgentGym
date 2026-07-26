from __future__ import annotations

import json
from pathlib import Path

import pytest

from crossmarket_agentgym.tuning.models import StudyState, TrialResult
from crossmarket_agentgym.tuning.objectives import (
    ValidationRecord,
    default_multi_objective_directions,
    multi_objective_values,
    pareto_front,
    robust_portfolio_score,
    select_trial,
)
from crossmarket_agentgym.tuning.reports import build_study_report, write_study_report


def _records() -> list[ValidationRecord]:
    return [
        ValidationRecord(
            seed=1,
            fold=0,
            sharpe=1.0,
            max_drawdown=0.2,
            turnover=2.0,
            training_seconds=4.0,
        ),
        ValidationRecord(
            seed=2,
            fold=0,
            sharpe=3.0,
            max_drawdown=0.4,
            turnover=4.0,
            training_seconds=8.0,
        ),
    ]


def test_robust_objective_uses_validation_medians_and_seed_instability() -> None:
    assert robust_portfolio_score(_records()) == pytest.approx(1.45)
    assert multi_objective_values(_records(), include_training_time=True) == pytest.approx(
        (2.0, 0.3, 3.0, 1.0, 6.0)
    )
    assert default_multi_objective_directions(include_training_time=True) == (
        "maximize",
        "minimize",
        "minimize",
        "minimize",
        "minimize",
    )


def test_pareto_front_respects_mixed_directions() -> None:
    results = [
        TrialResult(
            trial_id=0,
            parameters={"x": 0},
            status="completed",
            objectives=(2.0, 0.3),
        ),
        TrialResult(
            trial_id=1,
            parameters={"x": 1},
            status="completed",
            objectives=(1.0, 0.4),
        ),
        TrialResult(
            trial_id=2,
            parameters={"x": 2},
            status="completed",
            objectives=(1.5, 0.1),
        ),
    ]
    assert [result.trial_id for result in pareto_front(results, ("maximize", "minimize"))] == [
        0,
        2,
    ]
    assert select_trial(
        results,
        ("maximize", "minimize"),
        strategy="pareto_first",
    ).trial_id == 0
    assert select_trial(
        results,
        ("maximize", "minimize"),
        strategy="weighted",
        weights=(0.1, 0.9),
    ).trial_id == 2


def test_report_is_strict_json_and_explicitly_excludes_test_metrics(
    tmp_path: Path,
) -> None:
    state = StudyState(
        study_name="report",
        directions=("maximize",),
        results=(
            TrialResult(
                trial_id=0,
                parameters={"x": 0.5},
                status="completed",
                objectives=(1.2,),
                metrics={"validation_sharpe": 1.2},
            ),
            TrialResult(
                trial_id=1,
                parameters={"x": 1.0},
                status="failed",
                error="failed safely",
            ),
        ),
    )
    report = build_study_report(state)
    assert report["test_metrics_present"] is False
    assert report["best_trial"]["trial_id"] == 0
    json_path, markdown_path = write_study_report(state, tmp_path)
    assert json.loads(json_path.read_text(encoding="utf-8")) == report
    assert "不含测试集指标" in markdown_path.read_text(encoding="utf-8")

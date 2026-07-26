from __future__ import annotations

import json

import pytest

from crossmarket_agentgym.tuning.models import TrialSuggestion
from crossmarket_agentgym.tuning.schedulers import (
    SCHEDULERS,
    ASHAScheduler,
    FIFOScheduler,
    HyperBandScheduler,
    MedianStoppingScheduler,
    PopulationBasedTrainingScheduler,
    ensure_compatible,
)
from crossmarket_agentgym.tuning.schedulers.base import TrialScheduler
from crossmarket_agentgym.tuning.searchers import SEARCHERS


def _suggestion(trial_id: int, value: float = 0.5) -> TrialSuggestion:
    return TrialSuggestion(trial_id=trial_id, parameters={"learning_rate": value})


def test_search_algorithms_and_resource_schedulers_are_separate_registries() -> None:
    assert set(SCHEDULERS) == {"fifo", "median", "asha", "hyperband", "pbt"}
    assert not set(SCHEDULERS).intersection(SEARCHERS)
    ensure_compatible("pso", "pbt")
    with pytest.raises(ValueError, match="incompatible"):
        ensure_compatible("grid", "pbt")


def test_fifo_never_early_stops() -> None:
    scheduler = FIFOScheduler()
    suggestion = _suggestion(0)
    scheduler.on_trial_add(suggestion.trial_id)
    decision = scheduler.on_result(
        suggestion.trial_id,
        resource=1.0,
        metric=-10.0,
    )
    assert decision.action == "continue"
    scheduler.on_complete(suggestion.trial_id, -10.0)
    assert scheduler.state_dict()["active"] == []


def test_median_stopping_rejects_a_weak_trial_after_warmup() -> None:
    scheduler = MedianStoppingScheduler(
        direction="maximize",
        grace_period=1.0,
        min_trials=3,
    )
    for trial_id, score in enumerate((1.0, 2.0, 3.0)):
        suggestion = _suggestion(trial_id)
        scheduler.on_trial_add(suggestion.trial_id)
        assert (
            scheduler.on_result(
                suggestion.trial_id,
                resource=1.0,
                metric=score,
            ).action
            == "continue"
        )
        scheduler.on_complete(suggestion.trial_id, score)

    weak = _suggestion(10)
    scheduler.on_trial_add(weak.trial_id)
    decision = scheduler.on_result(weak.trial_id, resource=1.0, metric=0.1)
    assert decision.action == "stop"
    assert decision.reason == "below_median"


def test_asha_promotes_only_the_top_reduction_fraction() -> None:
    scheduler = ASHAScheduler(
        direction="maximize",
        max_resource=9.0,
        grace_period=1.0,
        reduction_factor=3,
    )
    decisions = []
    for trial_id, score in enumerate((3.0, 2.0, 1.0)):
        suggestion = _suggestion(trial_id)
        scheduler.on_trial_add(suggestion.trial_id)
        decisions.append(
            scheduler.on_result(
                suggestion.trial_id,
                resource=1.0,
                metric=score,
            )
        )

    assert decisions[0].action == "continue"
    assert decisions[1].action == "continue"
    assert decisions[2].action == "stop"
    assert decisions[2].reason == "asha_rung_1"


def test_hyperband_assignment_and_resume_are_deterministic() -> None:
    scheduler = HyperBandScheduler(
        direction="maximize",
        max_resource=9.0,
        min_resource=1.0,
        reduction_factor=3,
    )
    for trial_id in range(4):
        suggestion = _suggestion(trial_id)
        scheduler.on_trial_add(suggestion.trial_id)
        scheduler.on_result(
            suggestion.trial_id,
            resource=1.0,
            metric=float(trial_id),
        )

    state = scheduler.state_dict()
    json.dumps(state, allow_nan=False)
    restored = HyperBandScheduler(
        direction="maximize",
        max_resource=9.0,
        min_resource=1.0,
        reduction_factor=3,
    )
    restored.load_state_dict(state)

    next_trial = _suggestion(5)
    scheduler.on_trial_add(next_trial.trial_id)
    restored.on_trial_add(next_trial.trial_id)
    assert scheduler.state_dict() == restored.state_dict()


def test_pbt_exploits_a_top_trial_and_perturbs_numeric_parameters() -> None:
    scheduler = PopulationBasedTrainingScheduler(
        direction="maximize",
        perturbation_interval=10.0,
        quantile_fraction=0.25,
        perturbation_factors=(0.8, 1.2),
    )
    decisions = []
    for trial_id, score in enumerate((4.0, 3.0, 2.0, 1.0)):
        suggestion = _suggestion(trial_id, value=0.01 * (trial_id + 1))
        scheduler.on_trial_add(suggestion.trial_id)
        decisions.append(
            scheduler.on_result(
                suggestion.trial_id,
                resource=10.0,
                metric=score,
                parameters=dict(suggestion.parameters),
            )
        )

    exploit = decisions[-1]
    assert exploit.action == "exploit"
    assert exploit.source_trial_id == 0
    assert exploit.parameter_patch["learning_rate"] in {0.008, 0.012}


@pytest.mark.parametrize(
    "scheduler",
    [
        MedianStoppingScheduler(),
        ASHAScheduler(max_resource=9.0),
        HyperBandScheduler(max_resource=9.0),
        PopulationBasedTrainingScheduler(),
    ],
)
def test_scheduler_state_is_strict_json_and_restorable(
    scheduler: TrialScheduler,
) -> None:
    suggestion = _suggestion(0)
    scheduler.on_trial_add(suggestion.trial_id)
    scheduler.on_result(
        suggestion.trial_id,
        resource=1.0,
        metric=1.0,
    )
    state = scheduler.state_dict()
    json.dumps(state, allow_nan=False)
    scheduler.load_state_dict(state)

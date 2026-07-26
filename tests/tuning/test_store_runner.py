from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from crossmarket_agentgym.tuning import (
    FunctionalObjective,
    ParameterSpec,
    SearchSpace,
    SQLiteStudyStore,
    TrialResult,
    TrialRunner,
    TrialSuggestion,
)
from crossmarket_agentgym.tuning.schedulers import FIFOScheduler
from crossmarket_agentgym.tuning.searchers import RandomSearch


@pytest.fixture
def space() -> SearchSpace:
    return SearchSpace(
        parameters=(
            ParameterSpec(name="x", kind="float", low=-2.0, high=2.0),
            ParameterSpec(name="choice", kind="categorical", choices=("a", "b")),
        ),
    )


def _objective(parameters: dict[str, object]) -> float:
    x = float(parameters["x"])
    return -(x * x)


def _runner(
    database: Path,
    space: SearchSpace,
    *,
    seed: int = 17,
) -> tuple[SQLiteStudyStore, TrialRunner]:
    store = SQLiteStudyStore(database)
    runner = TrialRunner(
        study_name="resume-study",
        directions=("maximize",),
        search_space=space,
        searcher=RandomSearch(seed=seed),
        scheduler=FIFOScheduler(),
        evaluator=FunctionalObjective(_objective),
        store=store,
        batch_size=2,
    )
    return store, runner


def test_sqlite_store_round_trips_trials_and_checkpoints(
    tmp_path: Path,
    space: SearchSpace,
) -> None:
    with SQLiteStudyStore(tmp_path / "study.sqlite3") as store:
        state = store.create_study("demo", ("maximize", "minimize"))
        assert state.results == ()
        suggestion = TrialSuggestion(
            trial_id=2,
            parameters=space.sample(np.random.default_rng(2)),
            generation=1,
            metadata={"source": "test"},
        )
        store.save_suggestion("demo", suggestion)
        assert store.pending_suggestions("demo") == [suggestion]
        result = TrialResult(
            trial_id=suggestion.trial_id,
            parameters=suggestion.parameters,
            status="completed",
            objectives=(1.5, 0.2),
            metrics={"sharpe": 1.5},
            resource=8.0,
        )
        store.save_result("demo", result)
        assert store.list_results("demo") == [result]
        store.save_checkpoint("demo", "searcher", {"counter": 3})
        assert store.load_checkpoint("demo", "searcher") == {"counter": 3}
        json.dumps(store.study_state("demo").model_dump(), allow_nan=False)

        with pytest.raises(ValueError, match="cannot change"):
            store.create_study("demo", ("minimize",))

        with pytest.raises(ValueError, match="configuration cannot change"):
            store.create_study(
                "demo",
                ("maximize", "minimize"),
                {"config_sha256": "changed"},
            )


def test_runner_resume_matches_uninterrupted_sequence(
    tmp_path: Path,
    space: SearchSpace,
) -> None:
    continuous_store, continuous = _runner(tmp_path / "continuous.sqlite3", space)
    try:
        continuous_state = continuous.run(6)
    finally:
        continuous_store.close()

    first_store, first = _runner(tmp_path / "resumed.sqlite3", space)
    try:
        assert len(first.run(2).results) == 2
    finally:
        first_store.close()
    resumed_store, resumed = _runner(tmp_path / "resumed.sqlite3", space)
    try:
        resumed_state = resumed.run(6)
        assert resumed.run(6) == resumed_state
    finally:
        resumed_store.close()

    assert [item.parameters for item in resumed_state.results] == [
        item.parameters for item in continuous_state.results
    ]
    assert [item.objectives for item in resumed_state.results] == [
        item.objectives for item in continuous_state.results
    ]


def test_runner_records_objective_exceptions_and_continues(
    tmp_path: Path,
    space: SearchSpace,
) -> None:
    def fail_for_category_a(parameters: dict[str, object]) -> float:
        if parameters["choice"] == "a":
            raise RuntimeError("deliberate trial failure")
        return _objective(parameters)

    with SQLiteStudyStore(tmp_path / "failures.sqlite3") as store:
        runner = TrialRunner(
            study_name="failures",
            directions=("maximize",),
            search_space=space,
            searcher=RandomSearch(seed=9),
            scheduler=FIFOScheduler(),
            evaluator=FunctionalObjective(fail_for_category_a),
            store=store,
            batch_size=1,
        )
        state = runner.run(8)

    assert len(state.results) == 8
    assert {result.status for result in state.results} == {"completed", "failed"}
    assert all(result.error for result in state.results if result.status == "failed")


def test_store_rejects_parameter_reassignment(
    tmp_path: Path,
) -> None:
    with SQLiteStudyStore(tmp_path / "identity.sqlite3") as store:
        store.create_study("identity", ("maximize",))
        first = TrialSuggestion(trial_id=0, parameters={"x": 0.0, "choice": "a"})
        store.save_suggestion("identity", first)
        with pytest.raises(ValueError, match="different parameters"):
            store.save_suggestion(
                "identity",
                TrialSuggestion(trial_id=0, parameters={"x": 1.0, "choice": "b"}),
            )

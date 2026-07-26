"""Boundary, mathematical-objective, fixed-seed, and resume tests for searchers."""

from __future__ import annotations

import json
import math
from collections.abc import Callable

import numpy as np
import pytest

from crossmarket_agentgym.tuning import (
    ParameterSpec,
    SearchSpace,
    StudyState,
    TrialResult,
)
from crossmarket_agentgym.tuning.searchers import SEARCHERS, BaseSearcher, NSGAIISearch


def _continuous_space() -> SearchSpace:
    return SearchSpace(
        parameters=(
            ParameterSpec(name="x", kind="float", low=-5.0, high=5.0),
            ParameterSpec(name="y", kind="float", low=-5.0, high=5.0),
        )
    )


def _sphere(parameters: dict[str, object]) -> float:
    x, y = float(parameters["x"]), float(parameters["y"])
    return -(x * x + y * y)


def _rosenbrock(parameters: dict[str, object]) -> float:
    x, y = float(parameters["x"]), float(parameters["y"])
    return -((1.0 - x) ** 2 + 100.0 * (y - x * x) ** 2)


def _run_objective(
    searcher: BaseSearcher,
    objective: Callable[[dict[str, object]], float],
    *,
    budget: int = 32,
) -> list[TrialResult]:
    space = _continuous_space()
    searcher.initialize(space, StudyState(study_name="math"))
    results: list[TrialResult] = []
    while len(results) < budget:
        suggestions = searcher.suggest(min(4, budget - len(results)))
        if not suggestions:
            break
        batch = [
            TrialResult(
                trial_id=suggestion.trial_id,
                parameters=suggestion.parameters,
                status="completed",
                objectives=(objective(suggestion.parameters),),
            )
            for suggestion in suggestions
        ]
        searcher.observe(batch)
        results.extend(batch)
    return results


@pytest.mark.parametrize("name", sorted(SEARCHERS))
@pytest.mark.parametrize("objective", [_sphere, _rosenbrock], ids=["sphere", "rosenbrock"])
def test_every_searcher_handles_math_functions_and_bounds(
    name: str,
    objective: Callable[[dict[str, object]], float],
) -> None:
    """Every core algorithm produces valid finite candidates on both functions."""
    results = _run_objective(SEARCHERS[name](seed=41), objective)

    assert results
    assert all(math.isfinite(result.objectives[0]) for result in results)
    assert all(
        -5.0 <= float(result.parameters[parameter]) <= 5.0
        for result in results
        for parameter in ("x", "y")
    )


@pytest.mark.parametrize("name", sorted(SEARCHERS))
def test_fixed_seed_and_json_checkpoint_resume(name: str) -> None:
    """A JSON round-trip resumes the exact next candidate sequence."""
    space = _continuous_space()
    state = StudyState(study_name="resume")
    first = SEARCHERS[name](seed=7)
    first.initialize(space, state)
    suggestions = first.suggest(4)
    results = [
        TrialResult(
            trial_id=item.trial_id,
            parameters=item.parameters,
            status="completed",
            objectives=(_sphere(item.parameters),),
        )
        for item in suggestions
    ]
    first.observe(results)
    serialized = json.loads(json.dumps(first.state_dict(), allow_nan=False))

    resumed = SEARCHERS[name](seed=7)
    resumed.initialize(
        space,
        StudyState(study_name="resume", results=tuple(results)),
    )
    resumed.load_state_dict(serialized)

    expected = first.suggest(1)
    actual = resumed.suggest(1)
    assert [item.parameters for item in actual] == [
        item.parameters for item in expected
    ]
    assert [item.trial_id for item in actual] == [item.trial_id for item in expected]


def test_nsga_ii_retains_a_nondominated_pareto_front() -> None:
    """Conflicting objectives remain in the first front instead of scalar collapse."""
    space = SearchSpace(
        parameters=(ParameterSpec(name="x", kind="float", low=0.0, high=1.0),)
    )
    searcher = NSGAIISearch(seed=3, population_size=8)
    searcher.initialize(
        space,
        StudyState(study_name="pareto", directions=("maximize", "minimize")),
    )
    suggestions = searcher.suggest(8)
    searcher.observe(
        [
            TrialResult(
                trial_id=item.trial_id,
                parameters=item.parameters,
                status="completed",
                objectives=(
                    float(item.parameters["x"]),
                    float(item.parameters["x"]) ** 2,
                ),
            )
            for item in suggestions
        ]
    )

    front = searcher.pareto_front()

    assert len(front) >= 2
    assert np.isfinite([result.objectives for result in front]).all()

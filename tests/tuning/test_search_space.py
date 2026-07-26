"""Mixed SearchSpace validation, encoding, and constraint tests."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from crossmarket_agentgym.tuning import ParameterSpec, SearchSpace


def _mixed_space() -> SearchSpace:
    return SearchSpace(
        parameters=(
            ParameterSpec(name="optimizer", kind="categorical", choices=("adam", "sgd")),
            ParameterSpec(name="learning_rate", kind="float", low=1e-5, high=1e-2, log=True),
            ParameterSpec(name="n_steps", kind="int", low=8, high=32, step=8),
            ParameterSpec(name="batch_size", kind="int", low=4, high=32, step=4),
            ParameterSpec(name="momentum", kind="float", low=0.0, high=0.9, condition="optimizer == 'sgd'"),
            ParameterSpec(name="normalize", kind="bool"),
        ),
        constraints=("batch_size <= n_steps",),
    )


@given(st.integers(min_value=0, max_value=2**32 - 1))
def test_mixed_space_samples_only_valid_bounded_candidates(seed: int) -> None:
    """All sampling paths share conditions and pre-training constraints."""
    space = _mixed_space()
    candidate = space.sample(np.random.default_rng(seed))

    space.validate_candidate(candidate)
    assert candidate["batch_size"] <= candidate["n_steps"]
    assert ("momentum" in candidate) == (candidate["optimizer"] == "sgd")
    encoded = space.encode(candidate)
    assert encoded.shape == (space.dimension,)
    assert np.logical_and(encoded >= 0.0, encoded <= 1.0).all()


def test_invalid_candidate_is_rejected_before_training() -> None:
    """Cross-parameter constraints are not delegated to an RL exception."""
    space = _mixed_space()
    candidate = {
        "optimizer": "adam",
        "learning_rate": 1e-3,
        "n_steps": 8,
        "batch_size": 32,
        "normalize": True,
    }

    with pytest.raises(ValueError, match="constraint"):
        space.validate_candidate(candidate)


def test_grid_respects_conditions_and_constraints() -> None:
    """Grid expansion omits inactive parameters and invalid combinations."""
    candidates = _mixed_space().grid()

    assert candidates
    assert all(item["batch_size"] <= item["n_steps"] for item in candidates)
    assert all(
        ("momentum" in item) == (item["optimizer"] == "sgd")
        for item in candidates
    )

"""Deterministic portfolio constraint projection tests."""

from __future__ import annotations

import numpy as np
from hypothesis import given
from hypothesis import strategies as st

from crossmarket_agentgym.environments import EnvironmentConfig
from crossmarket_agentgym.environments.projection import ConstraintProjector


def test_projection_enforces_cash_asset_market_and_turnover_limits() -> None:
    """One projection satisfies every configured hard bound."""
    config = EnvironmentConfig(
        cash_floor=0.20,
        max_asset_weight=0.35,
        max_market_weight=0.50,
        max_turnover=0.40,
    )
    projector = ConstraintProjector(config, ("CN", "CN", "US"))
    current = np.array([1.0, 0.0, 0.0, 0.0])

    result = projector.project(
        np.array([0.0, 10.0, 10.0, 10.0]),
        current_weights=current,
        tradable_mask=np.array([True, True, True]),
    )

    np.testing.assert_allclose(result.projected_weights.sum(), 1.0, atol=1e-10)
    assert result.projected_weights[0] >= 0.20 - 1e-10
    assert np.max(result.projected_weights[1:]) <= 0.35 + 1e-10
    assert result.projected_weights[1:3].sum() <= 0.50 + 1e-10
    assert np.abs(result.projected_weights[1:] - current[1:]).sum() <= 0.40 + 1e-10


def test_untradable_asset_is_frozen() -> None:
    """Projection cannot manufacture a trade in a closed market."""
    config = EnvironmentConfig(max_turnover=2.0)
    projector = ConstraintProjector(config, ("US", "JP"))
    current = np.array([0.5, 0.3, 0.2])

    result = projector.project(
        np.array([0.0, 0.0, 1.0]),
        current_weights=current,
        tradable_mask=np.array([True, False]),
    )

    assert result.projected_weights[2] == current[2]


@given(st.lists(st.floats(allow_nan=True, allow_infinity=True), min_size=4, max_size=4))
def test_projection_cleans_every_raw_action(raw: list[float]) -> None:
    """Arbitrary action values always produce finite normalized weights."""
    config = EnvironmentConfig(
        cash_floor=0.05,
        max_asset_weight=0.50,
        max_market_weight=0.70,
        max_turnover=2.0,
    )
    result = ConstraintProjector(config, ("CN", "HK", "US")).project(
        np.asarray(raw, dtype=np.float64),
        current_weights=np.array([1.0, 0.0, 0.0, 0.0]),
        tradable_mask=np.array([True, True, True]),
    )

    assert np.isfinite(result.projected_weights).all()
    np.testing.assert_allclose(result.projected_weights.sum(), 1.0, atol=1e-10)
    assert result.projected_weights[0] >= config.cash_floor - 1e-10

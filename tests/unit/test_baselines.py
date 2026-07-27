"""Traditional baseline strategy tests."""

from __future__ import annotations

import numpy as np
import pytest

from crossmarket_agentgym.environments import (
    CrossMarketPortfolioEnv,
    EnvironmentConfig,
    MarketDataPanel,
)
from crossmarket_agentgym.evaluation import BASELINES, baseline_by_name, evaluate_policy
from tests.helpers import make_us_ohlcv


@pytest.mark.parametrize("name", sorted(BASELINES))
def test_every_baseline_returns_finite_sum_one_action(name: str) -> None:
    """All seven baselines share the environment action contract."""
    env = CrossMarketPortfolioEnv(
        MarketDataPanel.from_frame(make_us_ohlcv(days=5)),
        EnvironmentConfig(lookback=3),
    )
    observation, _ = env.reset()
    strategy = baseline_by_name(name)

    action, state = strategy.predict(observation)

    assert state is None
    assert action.shape == env.action_space.shape
    assert np.isfinite(action).all()
    assert action.sum() == pytest.approx(1.0)


def test_baseline_evaluation_produces_trades_weights_and_metrics() -> None:
    """Non-RL strategies use the same auditable output schema as RL."""
    env = CrossMarketPortfolioEnv(
        MarketDataPanel.from_frame(make_us_ohlcv(days=5)),
        EnvironmentConfig(
            lookback=2,
            max_asset_weight=1.0,
            max_market_weight=1.0,
        ),
    )
    strategy = baseline_by_name("equal_weight")
    strategy.reset()

    result = evaluate_policy(env, strategy, algorithm=strategy.name)

    assert result.total_steps == 3
    assert len(result.trades) == result.total_steps
    assert len(result.weights) == result.total_steps
    assert "mean_return" in result.metrics
    assert result.evaluation_episodes == 1
    assert result.return_sample_count == 1
    assert result.reward_sample_count == 1
    assert result.metrics["std_return"] == 0.0
    assert result.statistical_warnings == (
        "Insufficient samples for reliable return dispersion estimates.",
        "Insufficient samples for reliable reward dispersion estimates.",
    )

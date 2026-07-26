"""No-future-information tests for the daily execution protocol."""

from __future__ import annotations

import numpy as np
from tests.helpers import make_us_ohlcv

from crossmarket_agentgym.environments import (
    CrossMarketPortfolioEnv,
    EnvironmentConfig,
    MarketDataPanel,
)


def test_t_observation_does_not_contain_t_plus_one_close() -> None:
    """Changing a future close changes returns but not the preceding observation."""
    base = make_us_ohlcv(days=2, close_multiplier_last=1.0)
    shocked = make_us_ohlcv(days=2, close_multiplier_last=2.0)
    config = EnvironmentConfig(
        lookback=1,
        cash_floor=0.0,
        max_asset_weight=1.0,
        max_market_weight=1.0,
        max_turnover=2.0,
    )
    env_base = CrossMarketPortfolioEnv(MarketDataPanel.from_frame(base), config)
    env_shocked = CrossMarketPortfolioEnv(MarketDataPanel.from_frame(shocked), config)

    observation_base, _ = env_base.reset(seed=1)
    observation_shocked, _ = env_shocked.reset(seed=1)
    for key in observation_base:
        np.testing.assert_array_equal(observation_base[key], observation_shocked[key])

    action = np.array([0.0, 1.0], dtype=np.float32)
    _, reward_base, _, _, info_base = env_base.step(action)
    _, reward_shocked, _, _, info_shocked = env_shocked.step(action)

    np.testing.assert_array_equal(
        info_base["executed_quantities"], info_shocked["executed_quantities"]
    )
    np.testing.assert_array_equal(
        info_base["projected_weights"], info_shocked["projected_weights"]
    )
    assert reward_shocked > reward_base


def test_next_session_nontradable_asset_does_not_trade() -> None:
    """A target cannot force execution through the next-day tradable mask."""
    frame = make_us_ohlcv(days=2, tradable_last=False)
    env = CrossMarketPortfolioEnv(
        MarketDataPanel.from_frame(frame),
        EnvironmentConfig(
            lookback=1,
            cash_floor=0.0,
            max_asset_weight=1.0,
            max_market_weight=1.0,
            max_turnover=2.0,
        ),
    )
    env.reset(seed=1)
    _, _, _, _, info = env.step(np.array([0.0, 1.0], dtype=np.float32))

    assert info["executed_quantities"][0] == 0.0
    assert info["rejected_orders"][0] == "not_tradable"

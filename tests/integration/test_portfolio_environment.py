"""Gymnasium environment integration tests."""

from __future__ import annotations

import numpy as np
from gymnasium.utils.env_checker import check_env
from tests.helpers import make_us_ohlcv

from crossmarket_agentgym.environments import (
    CrossMarketPortfolioEnv,
    EnvironmentConfig,
    MarketDataPanel,
    ObservationConfig,
)


def test_gymnasium_check_env_passes() -> None:
    """The environment follows the modern reset/step API."""
    panel = MarketDataPanel.from_frame(make_us_ohlcv(days=8))
    env = CrossMarketPortfolioEnv(
        panel,
        EnvironmentConfig(
            lookback=2,
            cash_floor=0.0,
            max_asset_weight=1.0,
            max_market_weight=1.0,
            max_turnover=2.0,
        ),
    )

    check_env(env, skip_render_check=True)


def test_market_window_layouts_preserve_tensor_values() -> None:
    panel = MarketDataPanel.from_frame(make_us_ohlcv(days=5))
    config = EnvironmentConfig(lookback=2)
    tensor_env = CrossMarketPortfolioEnv(
        panel,
        config,
        observation=ObservationConfig(market_window_layout="tensor"),
    )
    flat_env = CrossMarketPortfolioEnv(
        panel,
        config,
        observation=ObservationConfig(market_window_layout="flat"),
    )

    tensor, _ = tensor_env.reset(seed=11)
    flat, _ = flat_env.reset(seed=11)

    assert tensor["market_window"].shape == (1, 2, len(panel.feature_names))
    assert flat["market_window"].shape == (
        tensor["market_window"].size,
    )
    np.testing.assert_array_equal(
        flat["market_window"],
        tensor["market_window"].reshape(-1),
    )
    assert flat["market_window"].dtype == np.float32


def test_step_executes_next_open_and_returns_auditable_info() -> None:
    """An action at t is recorded against the next session's open."""
    panel = MarketDataPanel.from_frame(make_us_ohlcv(days=4))
    env = CrossMarketPortfolioEnv(
        panel,
        EnvironmentConfig(
            lookback=1,
            initial_cash=1000.0,
            cash_floor=0.0,
            max_asset_weight=1.0,
            max_market_weight=1.0,
            max_turnover=2.0,
        ),
    )
    _, reset_info = env.reset(seed=7)
    _, reward, terminated, truncated, info = env.step(
        np.array([0.0, 1.0], dtype=np.float32)
    )

    assert reset_info["observation_date"] == "2024-01-02"
    assert info["signal_date"] == "2024-01-02"
    assert info["execution_date"] == "2024-01-03"
    assert np.isfinite(reward)
    assert not terminated
    assert not truncated
    assert info["accounting_error"] < 1e-8


def test_random_actions_run_1000_steps_without_nan() -> None:
    """The CPU smoke workload remains finite across episode resets."""
    panel = MarketDataPanel.from_frame(make_us_ohlcv(days=1105))
    env = CrossMarketPortfolioEnv(
        panel,
        EnvironmentConfig(
            lookback=5,
            cash_floor=0.05,
            max_asset_weight=0.95,
            max_market_weight=0.95,
            max_turnover=0.50,
        ),
    )
    observation, _ = env.reset(seed=1024)
    for _ in range(1000):
        action = env.action_space.sample()
        observation, reward, terminated, truncated, info = env.step(action)
        assert np.isfinite(reward)
        assert np.isfinite(info["portfolio_value"])
        assert all(np.isfinite(value).all() for value in observation.values())
        if terminated or truncated:
            observation, _ = env.reset()

"""Execution-engine and accounting identity tests."""

from __future__ import annotations

import numpy as np
import pytest

from crossmarket_agentgym.environments import EnvironmentConfig
from crossmarket_agentgym.environments.accounting import AccountState
from crossmarket_agentgym.environments.execution import ExecutionEngine


def test_manual_one_asset_accounting_without_costs() -> None:
    """Buying at 100 and marking at 110 yields exactly 1,100."""
    config = EnvironmentConfig(
        initial_cash=1000.0,
        cash_floor=0.0,
        max_asset_weight=1.0,
        max_market_weight=1.0,
        max_turnover=2.0,
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
    )
    engine = ExecutionEngine(config, symbols=("A",), markets=("US",))
    result = engine.execute(
        AccountState.initial(asset_count=1, cash=1000.0),
        target_weights=np.array([0.0, 1.0]),
        open_prices=np.array([100.0]),
        close_prices=np.array([110.0]),
        tradable_mask=np.array([True]),
        suspension_mask=np.array([False]),
        limit_up_mask=np.array([False]),
        limit_down_mask=np.array([False]),
    )

    assert result.state.cash == pytest.approx(0.0)
    assert result.state.shares[0] == pytest.approx(10.0)
    assert result.end_value == pytest.approx(1100.0)
    assert result.accounting_error == pytest.approx(0.0, abs=1e-9)


def test_cost_and_slippage_are_nonnegative_and_conserved() -> None:
    """Mid-price value falls only by recorded fees and slippage at execution."""
    config = EnvironmentConfig(
        initial_cash=1000.0,
        cash_floor=0.0,
        max_asset_weight=1.0,
        max_market_weight=1.0,
        max_turnover=2.0,
        transaction_cost_bps=10.0,
        slippage_bps=20.0,
    )
    result = ExecutionEngine(config, symbols=("A",), markets=("US",)).execute(
        AccountState.initial(asset_count=1, cash=1000.0),
        target_weights=np.array([0.0, 1.0]),
        open_prices=np.array([100.0]),
        close_prices=np.array([100.0]),
        tradable_mask=np.array([True]),
        suspension_mask=np.array([False]),
        limit_up_mask=np.array([False]),
        limit_down_mask=np.array([False]),
    )

    assert result.fees > 0
    assert result.slippage_cost > 0
    assert result.accounting_error == pytest.approx(0.0, abs=1e-8)
    assert result.end_value == pytest.approx(
        result.pretrade_value - result.fees - result.slippage_cost,
        abs=1e-8,
    )


def test_suspension_rejects_trades() -> None:
    """Suspension blocks an order before account mutation."""
    config = EnvironmentConfig(
        initial_cash=1000.0,
        cash_floor=0.0,
        max_asset_weight=1.0,
        max_market_weight=1.0,
        max_turnover=2.0,
    )
    engine = ExecutionEngine(config, symbols=("A",), markets=("US",))
    result = engine.execute(
        AccountState.initial(asset_count=1, cash=1000.0),
        target_weights=np.array([0.0, 1.0]),
        open_prices=np.array([100.0]),
        close_prices=np.array([100.0]),
        tradable_mask=np.array([True]),
        suspension_mask=np.array([True]),
        limit_up_mask=np.array([False]),
        limit_down_mask=np.array([False]),
    )

    assert result.state.shares[0] == 0
    assert result.rejected_orders[0] == "suspension"


@pytest.mark.parametrize(
    ("state", "target", "limit_up", "limit_down", "reason"),
    [
        (
            AccountState.initial(asset_count=1, cash=1000.0),
            np.array([0.0, 1.0]),
            True,
            False,
            "limit_up",
        ),
        (
            AccountState(
                cash=0.0,
                shares=np.array([10.0]),
                sellable_long_shares=np.array([10.0]),
                last_value=1000.0,
                peak_value=1000.0,
                step_count=1,
            ),
            np.array([1.0, 0.0]),
            False,
            True,
            "limit_down",
        ),
    ],
)
def test_price_limits_reject_directional_orders(
    state: AccountState,
    target: np.ndarray,
    limit_up: bool,
    limit_down: bool,
    reason: str,
) -> None:
    """Limit-up blocks buys and limit-down blocks sells."""
    config = EnvironmentConfig(
        initial_cash=1000.0,
        cash_floor=0.0,
        max_asset_weight=1.0,
        max_market_weight=1.0,
        max_turnover=2.0,
    )
    result = ExecutionEngine(config, symbols=("A",), markets=("US",)).execute(
        state,
        target_weights=target,
        open_prices=np.array([100.0]),
        close_prices=np.array([100.0]),
        tradable_mask=np.array([True]),
        suspension_mask=np.array([False]),
        limit_up_mask=np.array([limit_up]),
        limit_down_mask=np.array([limit_down]),
    )

    assert result.executed_quantities[0] == 0.0
    assert result.rejected_orders[0] == reason


def test_lot_size_rounds_quantity_toward_zero() -> None:
    """Configured whole-lot rules prevent fractional or partial-lot fills."""
    config = EnvironmentConfig(
        initial_cash=1000.0,
        cash_floor=0.0,
        max_asset_weight=1.0,
        max_market_weight=1.0,
        max_turnover=2.0,
        lot_sizes={"A": 2},
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
    )
    result = ExecutionEngine(config, symbols=("A",), markets=("US",)).execute(
        AccountState.initial(asset_count=1, cash=1000.0),
        target_weights=np.array([0.0, 1.0]),
        open_prices=np.array([333.0]),
        close_prices=np.array([333.0]),
        tradable_mask=np.array([True]),
        suspension_mask=np.array([False]),
        limit_up_mask=np.array([False]),
        limit_down_mask=np.array([False]),
    )

    assert result.executed_quantities[0] == 2.0
    assert result.state.shares[0] == 2.0


def test_short_sale_is_signed_and_reconciled() -> None:
    """A configured short position uses signed shares without bypassing accounting."""
    config = EnvironmentConfig(
        initial_cash=1000.0,
        allow_short=True,
        max_leverage=2.0,
        cash_floor=0.0,
        max_asset_weight=1.0,
        max_market_weight=2.0,
        max_turnover=2.0,
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
    )
    result = ExecutionEngine(config, symbols=("A",), markets=("US",)).execute(
        AccountState.initial(asset_count=1, cash=1000.0),
        target_weights=np.array([1.5, -0.5]),
        open_prices=np.array([100.0]),
        close_prices=np.array([90.0]),
        tradable_mask=np.array([True]),
        suspension_mask=np.array([False]),
        limit_up_mask=np.array([False]),
        limit_down_mask=np.array([False]),
    )

    assert result.state.shares[0] == pytest.approx(-5.0)
    assert result.end_value == pytest.approx(1050.0)
    assert result.accounting_error == pytest.approx(0.0)


def test_t_plus_one_blocks_same_session_long_sale() -> None:
    """CN shares with zero sellable balance remain unchanged."""
    config = EnvironmentConfig(
        initial_cash=1000.0,
        cash_floor=0.0,
        max_asset_weight=1.0,
        max_market_weight=1.0,
        max_turnover=2.0,
    )
    state = AccountState(
        cash=0.0,
        shares=np.array([10.0]),
        sellable_long_shares=np.array([0.0]),
        last_value=1000.0,
        peak_value=1000.0,
        step_count=1,
    )
    result = ExecutionEngine(config, symbols=("000001",), markets=("CN",)).execute(
        state,
        target_weights=np.array([1.0, 0.0]),
        open_prices=np.array([100.0]),
        close_prices=np.array([100.0]),
        tradable_mask=np.array([True]),
        suspension_mask=np.array([False]),
        limit_up_mask=np.array([False]),
        limit_down_mask=np.array([False]),
    )

    assert result.state.shares[0] == 10.0
    assert result.rejected_orders[0] == "t_plus_one_partial"

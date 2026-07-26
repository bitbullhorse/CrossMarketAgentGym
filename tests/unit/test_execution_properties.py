"""Property tests for the deterministic account mutation boundary."""

from __future__ import annotations

import numpy as np
from hypothesis import given
from hypothesis import strategies as st

from crossmarket_agentgym.environments import EnvironmentConfig
from crossmarket_agentgym.environments.accounting import AccountState
from crossmarket_agentgym.environments.execution import ExecutionEngine


@given(
    target=st.floats(min_value=0.0, max_value=1.0),
    open_price=st.floats(min_value=1.0, max_value=500.0),
    close_price=st.floats(min_value=1.0, max_value=500.0),
    fee_bps=st.floats(min_value=0.0, max_value=100.0),
    slip_bps=st.floats(min_value=0.0, max_value=100.0),
)
def test_account_value_conserves_cash_positions_and_nonnegative_costs(
    target: float,
    open_price: float,
    close_price: float,
    fee_bps: float,
    slip_bps: float,
) -> None:
    """Every generated trade reconciles at open and marks exactly at close."""
    config = EnvironmentConfig(
        initial_cash=100_000.0,
        cash_floor=0.0,
        max_asset_weight=1.0,
        max_market_weight=1.0,
        max_turnover=2.0,
        transaction_cost_bps=fee_bps,
        slippage_bps=slip_bps,
    )
    result = ExecutionEngine(config, symbols=("A",), markets=("US",)).execute(
        AccountState.initial(asset_count=1, cash=config.initial_cash),
        target_weights=np.array([1.0 - target, target]),
        open_prices=np.array([open_price]),
        close_prices=np.array([close_price]),
        tradable_mask=np.array([True]),
        suspension_mask=np.array([False]),
        limit_up_mask=np.array([False]),
        limit_down_mask=np.array([False]),
    )

    assert result.fees >= 0.0
    assert result.slippage_cost >= 0.0
    assert result.accounting_error <= (
        config.accounting_tolerance * config.initial_cash
    )
    assert result.end_value == result.state.value(np.array([close_price]))


@given(target=st.floats(min_value=0.0, max_value=1.0))
def test_nontradable_property_never_mutates_position(target: float) -> None:
    """The execution mask is authoritative for every generated target."""
    config = EnvironmentConfig(
        cash_floor=0.0,
        max_asset_weight=1.0,
        max_market_weight=1.0,
        max_turnover=2.0,
    )
    result = ExecutionEngine(config, symbols=("A",), markets=("US",)).execute(
        AccountState.initial(asset_count=1, cash=config.initial_cash),
        target_weights=np.array([1.0 - target, target]),
        open_prices=np.array([100.0]),
        close_prices=np.array([100.0]),
        tradable_mask=np.array([False]),
        suspension_mask=np.array([False]),
        limit_up_mask=np.array([False]),
        limit_down_mask=np.array([False]),
    )

    assert result.executed_quantities[0] == 0.0
    assert result.state.shares[0] == 0.0

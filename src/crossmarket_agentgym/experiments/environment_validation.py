"""Hand-computable Phase 12 Group A environment checks."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from crossmarket_agentgym.data.fx import FXRateTable
from crossmarket_agentgym.environments import EnvironmentConfig, MarketDataPanel
from crossmarket_agentgym.environments.accounting import AccountState
from crossmarket_agentgym.environments.execution import ExecutionEngine
from crossmarket_agentgym.environments.projection import ConstraintProjector


class EnvironmentValidationResult(BaseModel):
    """Expected and observed evidence for one hand-computable invariant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: str
    passed: bool
    expected: dict[str, Any]
    observed: dict[str, Any]
    absolute_error: float = Field(ge=0.0)
    accounting_tolerance: float = Field(gt=0.0)


def _config(**updates: Any) -> EnvironmentConfig:
    base: dict[str, Any] = {
        "initial_cash": 10_000.0,
        "cash_floor": 0.0,
        "max_asset_weight": 1.0,
        "max_market_weight": 1.0,
        "max_turnover": 2.0,
        "transaction_cost_bps": 0.0,
        "slippage_bps": 0.0,
        "accounting_tolerance": 1e-8,
    }
    return EnvironmentConfig(**(base | updates))


def _execute(
    config: EnvironmentConfig,
    *,
    market: str = "US",
    state: AccountState | None = None,
    target: tuple[float, float] = (0.5, 0.5),
    tradable: bool = True,
    suspended: bool = False,
    limit_up: bool = False,
    limit_down: bool = False,
    open_price: float = 100.0,
    close_price: float = 100.0,
) -> Any:
    engine = ExecutionEngine(
        config,
        symbols=("ASSET",),
        markets=(market,),  # type: ignore[arg-type]
    )
    return engine.execute(
        state or AccountState.initial(asset_count=1, cash=config.initial_cash),
        target_weights=np.asarray(target, dtype=np.float64),
        open_prices=np.asarray([open_price]),
        close_prices=np.asarray([close_price]),
        tradable_mask=np.asarray([tradable]),
        suspension_mask=np.asarray([suspended]),
        limit_up_mask=np.asarray([limit_up]),
        limit_down_mask=np.asarray([limit_down]),
    )


def _numeric_result(
    method: str,
    *,
    expected: dict[str, float],
    observed: dict[str, float],
    tolerance: float = 1e-8,
) -> EnvironmentValidationResult:
    keys = set(expected)
    if keys != set(observed):
        raise ValueError("expected and observed numeric fields must match")
    error = max((abs(expected[key] - observed[key]) for key in keys), default=0.0)
    return EnvironmentValidationResult(
        method=method,
        passed=bool(error <= tolerance),
        expected=expected,
        observed=observed,
        absolute_error=error,
        accounting_tolerance=tolerance,
    )


def _categorical_result(
    method: str,
    *,
    expected: dict[str, Any],
    observed: dict[str, Any],
) -> EnvironmentValidationResult:
    return EnvironmentValidationResult(
        method=method,
        passed=bool(expected == observed),
        expected=expected,
        observed=observed,
        absolute_error=0.0 if expected == observed else 1.0,
        accounting_tolerance=1e-8,
    )


def validate_transaction_cost() -> EnvironmentValidationResult:
    result = _execute(_config(transaction_cost_bps=10.0))
    expected_fee = abs(float(result.executed_quantities[0])) * 100.0 * 0.001
    return _numeric_result(
        "transaction_cost",
        expected={"fees": expected_fee, "accounting_error": 0.0},
        observed={"fees": result.fees, "accounting_error": result.accounting_error},
    )


def validate_slippage() -> EnvironmentValidationResult:
    result = _execute(_config(slippage_bps=20.0))
    expected = abs(float(result.executed_quantities[0])) * 100.0 * 0.002
    return _numeric_result(
        "slippage",
        expected={"slippage_cost": expected, "accounting_error": 0.0},
        observed={
            "slippage_cost": result.slippage_cost,
            "accounting_error": result.accounting_error,
        },
    )


def validate_t_plus_one() -> EnvironmentValidationResult:
    state = AccountState(
        cash=0.0,
        shares=np.asarray([100.0]),
        sellable_long_shares=np.asarray([0.0]),
        last_value=10_000.0,
        peak_value=10_000.0,
        step_count=1,
    )
    result = _execute(
        _config(),
        market="CN",
        state=state,
        target=(1.0, 0.0),
    )
    return _categorical_result(
        "t_plus_one",
        expected={"quantity": 0.0, "reason": "t_plus_one_partial"},
        observed={
            "quantity": float(result.executed_quantities[0]),
            "reason": result.rejected_orders[0],
        },
    )


def validate_suspension() -> EnvironmentValidationResult:
    result = _execute(_config(), suspended=True)
    return _categorical_result(
        "suspension",
        expected={"quantity": 0.0, "reason": "suspension"},
        observed={
            "quantity": float(result.executed_quantities[0]),
            "reason": result.rejected_orders[0],
        },
    )


def validate_price_limits() -> EnvironmentValidationResult:
    result = _execute(_config(), limit_up=True)
    return _categorical_result(
        "price_limits",
        expected={"quantity": 0.0, "reason": "limit_up"},
        observed={
            "quantity": float(result.executed_quantities[0]),
            "reason": result.rejected_orders[0],
        },
    )


def validate_minimum_lot() -> EnvironmentValidationResult:
    result = _execute(
        _config(lot_sizes={"ASSET": 100}),
        target=(0.0, 1.0),
        open_price=33.0,
        close_price=33.0,
    )
    return _numeric_result(
        "minimum_lot",
        expected={"quantity": 300.0},
        observed={"quantity": float(result.executed_quantities[0])},
    )


def _row(
    trade_date: str,
    *,
    symbol: str,
    market: str,
    currency: str,
    timezone: str,
    close: float,
) -> dict[str, Any]:
    return {
        "trade_date": trade_date,
        "symbol": symbol,
        "market": market,
        "exchange": f"{market}_TEST",
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": 1000.0,
        "currency": currency,
        "timezone": timezone,
        "adjusted": False,
        "source": "hand_computable",
        "suspension_flag": None,
        "limit_up": None,
        "limit_down": None,
        "tradable": None,
    }


def _fx_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "trade_date": "2024-01-01",
                "base_currency": "CNY",
                "quote_currency": "USD",
                "rate": 0.14,
                "source": "hand_computable",
            },
            {
                "trade_date": "2024-01-02",
                "base_currency": "CNY",
                "quote_currency": "USD",
                "rate": 0.15,
                "source": "hand_computable",
            },
        ]
    )


def validate_market_holiday() -> EnvironmentValidationResult:
    frame = pd.DataFrame(
        [
            _row(
                "2024-01-02",
                symbol="CN1",
                market="CN",
                currency="CNY",
                timezone="Asia/Shanghai",
                close=10.0,
            ),
            _row(
                "2024-01-02",
                symbol="US1",
                market="US",
                currency="USD",
                timezone="America/New_York",
                close=100.0,
            ),
            _row(
                "2024-01-03",
                symbol="US1",
                market="US",
                currency="USD",
                timezone="America/New_York",
                close=101.0,
            ),
        ]
    )
    panel = MarketDataPanel.from_frame(frame, fx_rates=_fx_frame())
    cn_index = panel.symbols.index("CN1")
    holiday_index = panel.dates.index(pd.Timestamp("2024-01-03").date())
    return _categorical_result(
        "market_holiday",
        expected={"tradable": False, "valuation_finite": True},
        observed={
            "tradable": bool(panel.tradable_mask[holiday_index, cn_index]),
            "valuation_finite": bool(
                np.isfinite(panel.close_prices[holiday_index, cn_index])
            ),
        },
    )


def validate_fx_conversion() -> EnvironmentValidationResult:
    table = FXRateTable(_fx_frame(), quote_currency="USD")
    rate = table.rate_on_or_before(pd.Timestamp("2024-01-03").date(), "CNY")
    return _numeric_result(
        "fx_conversion",
        expected={"rate": 0.15, "ten_cny_in_usd": 1.5},
        observed={"rate": rate, "ten_cny_in_usd": 10.0 * rate},
    )


def validate_weight_projection() -> EnvironmentValidationResult:
    config = _config(
        cash_floor=0.20,
        max_asset_weight=0.35,
        max_market_weight=0.50,
        max_turnover=0.40,
    )
    result = ConstraintProjector(config, ("CN", "CN", "US")).project(
        np.asarray([0.0, 10.0, 10.0, 10.0]),
        current_weights=np.asarray([1.0, 0.0, 0.0, 0.0]),
        tradable_mask=np.asarray([True, True, True]),
    )
    weights = result.projected_weights
    observed = {
        "sum": float(weights.sum()),
        "cash_minimum": float(weights[0] >= 0.20 - 1e-10),
        "asset_cap": float(np.max(weights[1:]) <= 0.35 + 1e-10),
        "market_cap": float(weights[1:3].sum() <= 0.50 + 1e-10),
        "turnover_cap": float(np.abs(weights[1:]).sum() <= 0.40 + 1e-10),
    }
    return _numeric_result(
        "weight_projection",
        expected={key: 1.0 for key in observed},
        observed=observed,
    )


def validate_cash_holdings_nav() -> EnvironmentValidationResult:
    result = _execute(
        _config(),
        target=(0.5, 0.5),
        open_price=100.0,
        close_price=110.0,
    )
    expected_end = result.state.cash + result.state.shares[0] * 110.0
    return _numeric_result(
        "cash_holdings_nav",
        expected={
            "cash_plus_holdings": expected_end,
            "end_value": expected_end,
            "accounting_error": 0.0,
        },
        observed={
            "cash_plus_holdings": result.state.value(np.asarray([110.0])),
            "end_value": result.end_value,
            "accounting_error": result.accounting_error,
        },
    )


_VALIDATORS: dict[str, Callable[[], EnvironmentValidationResult]] = {
    "transaction_cost": validate_transaction_cost,
    "slippage": validate_slippage,
    "t_plus_one": validate_t_plus_one,
    "suspension": validate_suspension,
    "price_limits": validate_price_limits,
    "minimum_lot": validate_minimum_lot,
    "market_holiday": validate_market_holiday,
    "fx_conversion": validate_fx_conversion,
    "weight_projection": validate_weight_projection,
    "cash_holdings_nav": validate_cash_holdings_nav,
}


def run_environment_validation(method: str) -> EnvironmentValidationResult:
    """Execute exactly one frozen Group A method."""
    try:
        validator = _VALIDATORS[method]
    except KeyError as error:
        raise ValueError(f"unsupported Group A method: {method}") from error
    result = validator()
    if not result.passed:
        raise AssertionError(f"Group A validation failed: {method}: {result.model_dump()}")
    return result

"""Deterministic next-open execution with explicit costs and rejection reasons."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from crossmarket_agentgym.data.schemas import Market
from crossmarket_agentgym.environments.accounting import (
    AccountingInvariantError,
    AccountState,
)
from crossmarket_agentgym.environments.config import EnvironmentConfig
from crossmarket_agentgym.environments.rules import LotSize, PriceLimit, Suspension, TPlusOne


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """All account mutations and reconciliation values for one session."""

    state: AccountState
    pretrade_value: float
    post_trade_mid_value: float
    end_value: float
    fees: float
    slippage_cost: float
    turnover: float
    executed_quantities: NDArray[np.float64]
    rejected_orders: tuple[str | None, ...]
    accounting_error: float


class ExecutionEngine:
    """The sole component authorized to replace account state."""

    def __init__(
        self,
        config: EnvironmentConfig,
        *,
        symbols: tuple[str, ...],
        markets: tuple[Market, ...],
    ) -> None:
        """Bind deterministic rules and per-asset metadata."""
        if len(symbols) != len(markets) or not symbols:
            raise ValueError("symbols and markets must have equal non-zero length")
        self.config = config
        self.symbols = symbols
        self.markets = markets
        self._lot_sizes = np.asarray(
            [config.lot_sizes.get(symbol, 1) for symbol in symbols], dtype=np.int64
        )

    def _validate_inputs(
        self,
        state: AccountState,
        target_weights: NDArray[np.floating[Any]],
        open_prices: NDArray[np.floating[Any]],
        close_prices: NDArray[np.floating[Any]],
        masks: tuple[NDArray[np.bool_], ...],
    ) -> None:
        """Reject malformed execution inputs before touching a copied account."""
        asset_count = len(self.symbols)
        if state.shares.shape != (asset_count,):
            raise ValueError("account asset count does not match engine")
        if target_weights.shape != (asset_count + 1,):
            raise ValueError("target weight shape does not match engine")
        if not np.isfinite(target_weights).all():
            raise ValueError("target weights must be finite")
        if abs(float(np.asarray(target_weights).sum()) - 1.0) > 1e-8:
            raise ValueError("target weights must sum to one")
        for prices in (open_prices, close_prices):
            if prices.shape != (asset_count,):
                raise ValueError("price shape does not match engine")
            if not np.isfinite(prices).all() or (prices <= 0.0).any():
                raise ValueError("execution prices must be finite and positive")
        if any(mask.shape != (asset_count,) for mask in masks):
            raise ValueError("execution mask shape does not match engine")

    def execute(
        self,
        state: AccountState,
        *,
        target_weights: NDArray[np.floating[Any]],
        open_prices: NDArray[np.floating[Any]],
        close_prices: NDArray[np.floating[Any]],
        tradable_mask: NDArray[np.bool_],
        suspension_mask: NDArray[np.bool_],
        limit_up_mask: NDArray[np.bool_],
        limit_down_mask: NDArray[np.bool_],
    ) -> ExecutionResult:
        """Execute projected targets at open, then mark holdings at close."""
        masks = (
            tradable_mask,
            suspension_mask,
            limit_up_mask,
            limit_down_mask,
        )
        self._validate_inputs(state, target_weights, open_prices, close_prices, masks)
        open_values = np.asarray(open_prices, dtype=np.float64)
        close_values = np.asarray(close_prices, dtype=np.float64)
        target = np.asarray(target_weights, dtype=np.float64)
        session_state = state
        pretrade_value = session_state.value(open_values)
        if pretrade_value <= 0.0:
            raise AccountingInvariantError("pretrade portfolio value is non-positive")

        shares = session_state.shares.copy()
        sellable = session_state.sellable_long_shares.copy()
        cash = float(session_state.cash)
        desired_values = target[1:] * pretrade_value
        current_values = shares * open_values
        requested = (desired_values - current_values) / open_values
        executed = np.zeros_like(shares)
        rejected: list[str | None] = [None] * len(shares)

        for index in range(len(shares)):
            reason: str | None = None
            if not bool(tradable_mask[index]):
                reason = "not_tradable"
            elif (suspension_reason := Suspension.reason(bool(suspension_mask[index]))):
                reason = suspension_reason
            elif price_reason := PriceLimit.reason(
                float(requested[index]),
                limit_up=bool(limit_up_mask[index]),
                limit_down=bool(limit_down_mask[index]),
            ):
                reason = price_reason
            if reason is not None:
                requested[index] = 0.0
                rejected[index] = reason
                continue
            requested[index] = LotSize.round_toward_zero(
                float(requested[index]), int(self._lot_sizes[index])
            )
            if not self.config.allow_short and requested[index] < 0.0:
                requested[index] = -min(abs(requested[index]), max(shares[index], 0.0))
            if self.markets[index] in self.config.t_plus_one_markets:
                capped = TPlusOne.cap_sell_quantity(
                    float(requested[index]),
                    sellable_long_shares=float(sellable[index]),
                    enabled=shares[index] > 0.0,
                )
                if capped != requested[index]:
                    rejected[index] = "t_plus_one_partial"
                    requested[index] = capped

        fee_rate = self.config.transaction_cost_bps / 10_000.0
        slip_rate = self.config.slippage_bps / 10_000.0
        fees = 0.0
        slippage_cost = 0.0

        sell_indices = np.flatnonzero(requested < 0.0)
        for index in sell_indices:
            quantity = float(requested[index])
            mid_notional = abs(quantity) * open_values[index]
            fee = mid_notional * fee_rate
            slip = mid_notional * slip_rate
            execution_price = open_values[index] * (1.0 - slip_rate)
            cash += abs(quantity) * execution_price - fee
            shares[index] += quantity
            sellable[index] = max(0.0, sellable[index] + quantity)
            executed[index] = quantity
            fees += fee
            slippage_cost += slip

        buy_indices = np.flatnonzero(requested > 0.0)
        required_cash = float(
            sum(
                requested[index]
                * open_values[index]
                * (1.0 + slip_rate + fee_rate)
                for index in buy_indices
            )
        )
        target_cash = max(float(target[0] * pretrade_value), 0.0)
        available_cash = max(cash - target_cash, 0.0)
        buy_scale = (
            min(1.0, available_cash / required_cash) if required_cash > 0.0 else 1.0
        )
        for index in buy_indices:
            quantity = LotSize.round_toward_zero(
                float(requested[index] * buy_scale), int(self._lot_sizes[index])
            )
            if quantity <= 0.0:
                if requested[index] > 0.0 and rejected[index] is None:
                    rejected[index] = "insufficient_cash_or_lot"
                continue
            mid_notional = quantity * open_values[index]
            fee = mid_notional * fee_rate
            slip = mid_notional * slip_rate
            execution_price = open_values[index] * (1.0 + slip_rate)
            total_cash = quantity * execution_price + fee
            if total_cash > cash + self.config.accounting_tolerance:
                if rejected[index] is None:
                    rejected[index] = "insufficient_cash"
                continue
            cash -= total_cash
            shares[index] += quantity
            if self.markets[index] not in self.config.t_plus_one_markets:
                sellable[index] = max(shares[index], 0.0)
            executed[index] += quantity
            fees += fee
            slippage_cost += slip
            if buy_scale < 1.0 and rejected[index] is None:
                rejected[index] = "insufficient_cash_partial"

        if abs(cash) < self.config.accounting_tolerance:
            cash = 0.0
        post_trade_mid_value = float(cash + np.dot(shares, open_values))
        expected_post_trade = pretrade_value - fees - slippage_cost
        accounting_error = abs(post_trade_mid_value - expected_post_trade)
        tolerance = self.config.accounting_tolerance * max(1.0, pretrade_value)
        if accounting_error > tolerance:
            raise AccountingInvariantError(
                "post-trade account does not reconcile: "
                f"error={accounting_error}, tolerance={tolerance}"
            )

        end_value = float(cash + np.dot(shares, close_values))
        next_state = AccountState(
            cash=cash,
            shares=shares.copy(),
            sellable_long_shares=sellable.copy(),
            last_value=end_value,
            peak_value=max(state.peak_value, end_value),
            step_count=state.step_count + 1,
        )
        turnover = float(np.dot(np.abs(executed), open_values) / pretrade_value)
        return ExecutionResult(
            state=next_state,
            pretrade_value=pretrade_value,
            post_trade_mid_value=post_trade_mid_value,
            end_value=end_value,
            fees=fees,
            slippage_cost=slippage_cost,
            turnover=turnover,
            executed_quantities=executed,
            rejected_orders=tuple(rejected),
            accounting_error=accounting_error,
        )

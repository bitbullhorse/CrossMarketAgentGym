"""Composable deterministic portfolio and execution rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from crossmarket_agentgym.data.schemas import Market
from crossmarket_agentgym.environments.config import EnvironmentConfig

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


@dataclass(frozen=True, slots=True)
class ProjectionContext:
    """State visible to deterministic weight rules."""

    config: EnvironmentConfig
    markets: tuple[Market, ...]
    current_weights: FloatArray
    tradable_mask: BoolArray

    @property
    def mutable_mask(self) -> BoolArray:
        """Return the asset positions that execution may change."""
        return self.tradable_mask


class WeightRule(Protocol):
    """Project portfolio weights toward one hard constraint."""

    name: str

    def apply(
        self,
        weights: FloatArray,
        context: ProjectionContext,
        reasons: list[str],
        unresolved: list[str],
    ) -> FloatArray:
        """Return constrained weights without mutating the input."""
        ...


def _with_cash(asset_weights: FloatArray) -> FloatArray:
    """Derive cash so signed portfolio weights sum exactly to one."""
    cash = 1.0 - float(asset_weights.sum())
    return np.concatenate((np.array([cash], dtype=np.float64), asset_weights))


class TradableMask:
    """Freeze weights of assets that cannot trade in the execution session."""

    name = "tradable_mask"

    def apply(
        self,
        weights: FloatArray,
        context: ProjectionContext,
        reasons: list[str],
        unresolved: list[str],
    ) -> FloatArray:
        """Restore current weights for every non-tradable asset."""
        del unresolved
        assets = weights[1:].copy()
        frozen = ~context.mutable_mask
        if frozen.any() and not np.allclose(
            assets[frozen], context.current_weights[1:][frozen]
        ):
            assets[frozen] = context.current_weights[1:][frozen]
            reasons.append(self.name)
        return _with_cash(assets)


class LongOnly:
    """Forbid negative asset weights when shorting is disabled."""

    name = "long_only"

    def apply(
        self,
        weights: FloatArray,
        context: ProjectionContext,
        reasons: list[str],
        unresolved: list[str],
    ) -> FloatArray:
        """Clip mutable negative weights while preserving frozen positions."""
        del unresolved
        if context.config.allow_short:
            return weights.copy()
        assets = weights[1:].copy()
        mask = context.mutable_mask & (assets < 0.0)
        if mask.any():
            assets[mask] = 0.0
            reasons.append(self.name)
        return _with_cash(assets)


class MaxAssetWeight:
    """Cap absolute exposure of each mutable asset."""

    name = "max_asset_weight"

    def apply(
        self,
        weights: FloatArray,
        context: ProjectionContext,
        reasons: list[str],
        unresolved: list[str],
    ) -> FloatArray:
        """Clip tradable assets and report frozen violations."""
        assets = weights[1:].copy()
        cap = context.config.max_asset_weight
        mutable = context.mutable_mask
        clipped = np.clip(assets[mutable], -cap, cap)
        if not np.allclose(clipped, assets[mutable]):
            assets[mutable] = clipped
            reasons.append(self.name)
        if np.any(np.abs(assets[~mutable]) > cap + 1e-12):
            unresolved.append(f"{self.name}:frozen")
        return _with_cash(assets)


class MaxMarketWeight:
    """Cap gross exposure independently for each market."""

    name = "max_market_weight"

    def apply(
        self,
        weights: FloatArray,
        context: ProjectionContext,
        reasons: list[str],
        unresolved: list[str],
    ) -> FloatArray:
        """Scale mutable market exposure around frozen holdings."""
        assets = weights[1:].copy()
        market_array = np.asarray(context.markets, dtype=object)
        mutable = context.mutable_mask
        changed = False
        for market in sorted(set(context.markets)):
            group = market_array == market
            cap = context.config.market_weight_overrides.get(
                market, context.config.max_market_weight
            )
            frozen_gross = float(np.abs(assets[group & ~mutable]).sum())
            mutable_gross = float(np.abs(assets[group & mutable]).sum())
            available = max(cap - frozen_gross, 0.0)
            if frozen_gross > cap + 1e-12:
                unresolved.append(f"{self.name}:{market}:frozen")
            if mutable_gross > available + 1e-12 and mutable_gross > 0.0:
                assets[group & mutable] *= available / mutable_gross
                changed = True
        if changed:
            reasons.append(self.name)
        return _with_cash(assets)


class Leverage:
    """Cap portfolio gross asset exposure."""

    name = "leverage"

    def apply(
        self,
        weights: FloatArray,
        context: ProjectionContext,
        reasons: list[str],
        unresolved: list[str],
    ) -> FloatArray:
        """Scale mutable gross exposure inside the configured leverage budget."""
        assets = weights[1:].copy()
        mutable = context.mutable_mask
        frozen_gross = float(np.abs(assets[~mutable]).sum())
        mutable_gross = float(np.abs(assets[mutable]).sum())
        available = max(context.config.max_leverage - frozen_gross, 0.0)
        if frozen_gross > context.config.max_leverage + 1e-12:
            unresolved.append(f"{self.name}:frozen")
        if mutable_gross > available + 1e-12 and mutable_gross > 0.0:
            assets[mutable] *= available / mutable_gross
            reasons.append(self.name)
        return _with_cash(assets)


class CashFloor:
    """Retain the configured minimum cash weight."""

    name = "cash_floor"

    def apply(
        self,
        weights: FloatArray,
        context: ProjectionContext,
        reasons: list[str],
        unresolved: list[str],
    ) -> FloatArray:
        """Reduce mutable long exposure until cash meets its floor."""
        assets = weights[1:].copy()
        cash = 1.0 - float(assets.sum())
        if cash >= context.config.cash_floor - 1e-12:
            return _with_cash(assets)
        excess = context.config.cash_floor - cash
        mutable_positive = context.mutable_mask & (assets > 0.0)
        positive_sum = float(assets[mutable_positive].sum())
        if positive_sum <= excess + 1e-12:
            assets[mutable_positive] = 0.0
            unresolved.append(f"{self.name}:frozen")
        else:
            assets[mutable_positive] *= (positive_sum - excess) / positive_sum
        reasons.append(self.name)
        return _with_cash(assets)


class TurnoverLimit:
    """Interpolate targets toward current holdings when turnover is excessive."""

    name = "turnover_limit"

    def apply(
        self,
        weights: FloatArray,
        context: ProjectionContext,
        reasons: list[str],
        unresolved: list[str],
    ) -> FloatArray:
        """Limit the L1 change in asset weights."""
        del unresolved
        assets = weights[1:].copy()
        current = context.current_weights[1:]
        mutable = context.mutable_mask
        turnover = float(np.abs(assets[mutable] - current[mutable]).sum())
        limit = context.config.max_turnover
        if turnover > limit + 1e-12 and turnover > 0.0:
            scale = limit / turnover
            assets[mutable] = current[mutable] + scale * (
                assets[mutable] - current[mutable]
            )
            reasons.append(self.name)
        return _with_cash(assets)


class Suspension:
    """Block every order for a suspended asset."""

    name = "suspension"

    @staticmethod
    def reason(is_suspended: bool) -> str | None:
        """Return a rejection reason for suspended assets."""
        return Suspension.name if is_suspended else None


class PriceLimit:
    """Block buys at limit-up and sells at limit-down."""

    @staticmethod
    def reason(delta: float, *, limit_up: bool, limit_down: bool) -> str | None:
        """Return the deterministic price-limit rejection reason."""
        if delta > 0.0 and limit_up:
            return "limit_up"
        if delta < 0.0 and limit_down:
            return "limit_down"
        return None


class LotSize:
    """Round order quantities toward zero to an explicit lot size."""

    @staticmethod
    def round_toward_zero(quantity: float, lot_size: int) -> float:
        """Return a sign-preserving whole-lot quantity."""
        magnitude = np.floor(abs(quantity) / lot_size) * lot_size
        return float(np.copysign(magnitude, quantity))


class TPlusOne:
    """Prevent same-session sale of newly acquired long shares."""

    @staticmethod
    def cap_sell_quantity(
        requested: float,
        *,
        sellable_long_shares: float,
        enabled: bool,
    ) -> float:
        """Cap long-share sales while allowing existing short exposure rules."""
        if not enabled or requested >= 0.0:
            return requested
        return -min(abs(requested), max(sellable_long_shares, 0.0))

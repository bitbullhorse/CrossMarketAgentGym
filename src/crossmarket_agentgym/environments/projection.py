"""Deterministic raw-action cleaning and constraint projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from crossmarket_agentgym.data.schemas import Market
from crossmarket_agentgym.environments.config import EnvironmentConfig
from crossmarket_agentgym.environments.rules import (
    CashFloor,
    Leverage,
    LongOnly,
    MaxAssetWeight,
    MaxMarketWeight,
    ProjectionContext,
    TradableMask,
    TurnoverLimit,
    WeightRule,
)


@dataclass(frozen=True, slots=True)
class ProjectionResult:
    """Every action representation needed for audit and replay."""

    raw_action: NDArray[np.float64]
    normalized_weights: NDArray[np.float64]
    projected_weights: NDArray[np.float64]
    clipping_reasons: tuple[str, ...]
    unresolved_constraints: tuple[str, ...]


class ConstraintProjector:
    """Apply a fixed, replayable sequence of hard portfolio rules."""

    def __init__(self, config: EnvironmentConfig, markets: tuple[Market, ...]) -> None:
        """Bind immutable constraints and asset-to-market membership."""
        self.config = config
        self.markets = markets
        self.rules: tuple[WeightRule, ...] = (
            TradableMask(),
            LongOnly(),
            MaxAssetWeight(),
            MaxMarketWeight(),
            Leverage(),
            CashFloor(),
            TurnoverLimit(),
        )

    def _normalize(self, raw_action: NDArray[np.float64]) -> NDArray[np.float64]:
        """Clean NaN/Inf and derive a sum-one portfolio."""
        clean = np.nan_to_num(
            raw_action.astype(np.float64, copy=True),
            nan=0.0,
            posinf=1.0,
            neginf=-1.0,
        )
        clean = np.clip(clean, -1e6, 1e6)
        if self.config.allow_short:
            assets = clean[1:]
            return np.concatenate(
                (np.array([1.0 - float(assets.sum())]), assets)
            )
        nonnegative = np.clip(clean, 0.0, None)
        total = float(nonnegative.sum())
        if total <= 0.0:
            result = np.zeros_like(nonnegative)
            result[0] = 1.0
            return result
        return nonnegative / total

    def project(
        self,
        raw_action: NDArray[np.floating[Any]],
        *,
        current_weights: NDArray[np.floating[Any]],
        tradable_mask: NDArray[np.bool_],
    ) -> ProjectionResult:
        """Return finite sum-one weights that obey every resolvable hard limit."""
        expected = len(self.markets) + 1
        if raw_action.shape != (expected,):
            raise ValueError(f"action shape must be {(expected,)}")
        if current_weights.shape != (expected,):
            raise ValueError(f"current_weights shape must be {(expected,)}")
        if tradable_mask.shape != (len(self.markets),):
            raise ValueError(f"tradable_mask shape must be {(len(self.markets),)}")

        raw = np.asarray(raw_action, dtype=np.float64).copy()
        normalized = self._normalize(raw)
        context = ProjectionContext(
            config=self.config,
            markets=self.markets,
            current_weights=np.asarray(current_weights, dtype=np.float64),
            tradable_mask=np.asarray(tradable_mask, dtype=bool),
        )
        projected = normalized.copy()
        reasons: list[str] = []
        unresolved: list[str] = []
        for rule in self.rules:
            projected = rule.apply(projected, context, reasons, unresolved)
        projected[0] = 1.0 - float(projected[1:].sum())
        if not np.isfinite(projected).all():
            raise ValueError("constraint projection produced non-finite weights")
        return ProjectionResult(
            raw_action=raw,
            normalized_weights=normalized,
            projected_weights=projected,
            clipping_reasons=tuple(dict.fromkeys(reasons)),
            unresolved_constraints=tuple(dict.fromkeys(unresolved)),
        )

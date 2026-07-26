"""Portfolio account state and accounting invariants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray


class AccountingInvariantError(RuntimeError):
    """Raised when execution cannot reconcile cash, positions, costs, and value."""


@dataclass(frozen=True, slots=True)
class AccountState:
    """The only mutable-through-replacement portfolio account representation."""

    cash: float
    shares: NDArray[np.float64]
    sellable_long_shares: NDArray[np.float64]
    last_value: float
    peak_value: float
    step_count: int

    @classmethod
    def initial(cls, *, asset_count: int, cash: float) -> AccountState:
        """Create a cash-only account with independent position arrays."""
        if asset_count < 1:
            raise ValueError("asset_count must be positive")
        if cash <= 0.0:
            raise ValueError("initial cash must be positive")
        return cls(
            cash=float(cash),
            shares=np.zeros(asset_count, dtype=np.float64),
            sellable_long_shares=np.zeros(asset_count, dtype=np.float64),
            last_value=float(cash),
            peak_value=float(cash),
            step_count=0,
        )

    def begin_session(self) -> AccountState:
        """Make positive positions from prior sessions sellable."""
        return AccountState(
            cash=self.cash,
            shares=self.shares.copy(),
            sellable_long_shares=np.maximum(self.shares, 0.0),
            last_value=self.last_value,
            peak_value=self.peak_value,
            step_count=self.step_count,
        )

    def value(self, prices: NDArray[np.floating[Any]]) -> float:
        """Mark cash and signed positions in the already-converted base currency."""
        values = np.asarray(prices, dtype=np.float64)
        if values.shape != self.shares.shape:
            raise ValueError("price vector shape does not match account positions")
        if not np.isfinite(values).all() or (values <= 0.0).any():
            raise ValueError("valuation prices must be finite and positive")
        return float(self.cash + np.dot(self.shares, values))

    def weights(self, prices: NDArray[np.floating[Any]]) -> NDArray[np.float64]:
        """Return cash plus signed asset weights at supplied base-currency prices."""
        total = self.value(prices)
        if total <= 0.0:
            raise AccountingInvariantError("portfolio value is non-positive")
        assets = self.shares * np.asarray(prices, dtype=np.float64) / total
        cash = self.cash / total
        return np.concatenate((np.array([cash], dtype=np.float64), assets))

    @property
    def drawdown(self) -> float:
        """Return current peak-to-value drawdown in `[0, 1+]`."""
        if self.peak_value <= 0.0:
            return 0.0
        return max(0.0, 1.0 - self.last_value / self.peak_value)

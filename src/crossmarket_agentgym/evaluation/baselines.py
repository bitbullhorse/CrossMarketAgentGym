"""Deterministic non-RL portfolio baselines."""

from __future__ import annotations

from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

Observation = dict[str, NDArray[Any]]


class BaselineStrategy(Protocol):
    """Stateful baseline contract compatible with the evaluator."""

    name: str

    def reset(self) -> None:
        """Reset episode-specific state."""
        ...

    def predict(
        self,
        observation: Observation,
        *,
        deterministic: bool = True,
    ) -> tuple[NDArray[np.float32], None]:
        """Return one raw portfolio action."""
        ...


def _tradable(observation: Observation) -> NDArray[np.bool_]:
    return np.asarray(observation["tradable_mask"], dtype=bool)


def _asset_action(weights: NDArray[np.floating[Any]]) -> NDArray[np.float32]:
    assets = np.nan_to_num(np.asarray(weights, dtype=np.float64), nan=0.0)
    assets = np.clip(assets, 0.0, None)
    total = float(assets.sum())
    if total <= 0.0:
        result = np.zeros(len(assets) + 1, dtype=np.float32)
        result[0] = 1.0
        return result
    assets /= total
    return np.concatenate(([0.0], assets)).astype(np.float32)


def _returns(observation: Observation) -> NDArray[np.float64]:
    market = _market_tensor(observation)
    close = np.maximum(market[:, :, 3], 1e-12)
    return np.diff(np.log(close), axis=1)


def _market_tensor(observation: Observation) -> NDArray[np.float64]:
    """Restore the canonical `[asset, lookback, feature]` view from flat adapters."""
    market = np.asarray(observation["market_window"], dtype=np.float64)
    if market.ndim == 3:
        return market
    if market.ndim != 1:
        raise ValueError("market_window must be flat or a three-dimensional tensor")
    asset_count = len(_tradable(observation))
    feature_count = 6
    denominator = asset_count * feature_count
    if denominator == 0 or market.size % denominator:
        raise ValueError("flat market_window is incompatible with the canonical feature geometry")
    return market.reshape(asset_count, market.size // denominator, feature_count)


class CashBaseline:
    """Hold cash for the entire episode."""

    name = "cash"

    def reset(self) -> None:
        """No state to reset."""

    def predict(
        self,
        observation: Observation,
        *,
        deterministic: bool = True,
    ) -> tuple[NDArray[np.float32], None]:
        """Return a cash-only target."""
        del deterministic
        action = np.zeros(len(_tradable(observation)) + 1, dtype=np.float32)
        action[0] = 1.0
        return action, None


class BuyAndHoldBaseline:
    """Buy equal weights once and preserve realized weights thereafter."""

    name = "buy_and_hold"

    def __init__(self) -> None:
        self._invested = False

    def reset(self) -> None:
        """Allow the next episode's initial purchase."""
        self._invested = False

    def predict(
        self,
        observation: Observation,
        *,
        deterministic: bool = True,
    ) -> tuple[NDArray[np.float32], None]:
        """Buy once, then request current weights."""
        del deterministic
        if self._invested:
            return (
                np.asarray(observation["portfolio_weights"], dtype=np.float32),
                None,
            )
        self._invested = True
        return _asset_action(_tradable(observation).astype(float)), None


class EqualWeightBaseline:
    """Rebalance equally across currently tradable assets."""

    name = "equal_weight"

    def reset(self) -> None:
        """No state to reset."""

    def predict(
        self,
        observation: Observation,
        *,
        deterministic: bool = True,
    ) -> tuple[NDArray[np.float32], None]:
        """Return equal tradable weights."""
        del deterministic
        return _asset_action(_tradable(observation).astype(float)), None


class RiskParityBaseline:
    """Allocate inverse realized volatility."""

    name = "risk_parity"

    def reset(self) -> None:
        """No state to reset."""

    def predict(
        self,
        observation: Observation,
        *,
        deterministic: bool = True,
    ) -> tuple[NDArray[np.float32], None]:
        """Return inverse-volatility tradable weights."""
        del deterministic
        returns = _returns(observation)
        volatility = (
            returns.std(axis=1, ddof=0)
            if returns.shape[1] > 0
            else np.ones(returns.shape[0])
        )
        scores = _tradable(observation) / np.maximum(volatility, 1e-8)
        return _asset_action(scores), None


class MeanVarianceBaseline:
    """Long-only regularized mean-variance allocation."""

    name = "mean_variance"

    def reset(self) -> None:
        """No state to reset."""

    def predict(
        self,
        observation: Observation,
        *,
        deterministic: bool = True,
    ) -> tuple[NDArray[np.float32], None]:
        """Use a pseudo-inverse covariance solution with a safe fallback."""
        del deterministic
        returns = _returns(observation)
        if returns.shape[1] < 2:
            return _asset_action(_tradable(observation).astype(float)), None
        covariance = np.atleast_2d(np.cov(returns, bias=True))
        covariance += np.eye(covariance.shape[0]) * 1e-6
        scores = np.linalg.pinv(covariance) @ returns.mean(axis=1)
        scores = np.clip(scores, 0.0, None) * _tradable(observation)
        return _asset_action(scores), None


class MomentumBaseline:
    """Allocate to assets with positive lookback momentum."""

    name = "momentum"

    def reset(self) -> None:
        """No state to reset."""

    def predict(
        self,
        observation: Observation,
        *,
        deterministic: bool = True,
    ) -> tuple[NDArray[np.float32], None]:
        """Use positive close-to-close lookback returns."""
        del deterministic
        market = _market_tensor(observation)
        start = np.maximum(market[:, 0, 3], 1e-12)
        scores = np.clip(market[:, -1, 3] / start - 1.0, 0.0, None)
        scores *= _tradable(observation)
        return _asset_action(scores), None


class MinimumVarianceBaseline:
    """Long-only minimum-variance allocation."""

    name = "minimum_variance"

    def reset(self) -> None:
        """No state to reset."""

    def predict(
        self,
        observation: Observation,
        *,
        deterministic: bool = True,
    ) -> tuple[NDArray[np.float32], None]:
        """Solve the regularized inverse-covariance allocation."""
        del deterministic
        returns = _returns(observation)
        if returns.shape[1] < 2:
            return _asset_action(_tradable(observation).astype(float)), None
        covariance = np.atleast_2d(np.cov(returns, bias=True))
        covariance += np.eye(covariance.shape[0]) * 1e-6
        scores = np.asarray(
            np.linalg.pinv(covariance) @ np.ones(covariance.shape[0]),
            dtype=np.float64,
        )
        scores = np.clip(scores, 0.0, None)
        scores *= _tradable(observation).astype(np.float64)
        return _asset_action(scores), None


BASELINES: dict[str, type[BaselineStrategy]] = {
    "cash": CashBaseline,
    "buy_and_hold": BuyAndHoldBaseline,
    "equal_weight": EqualWeightBaseline,
    "risk_parity": RiskParityBaseline,
    "mean_variance": MeanVarianceBaseline,
    "momentum": MomentumBaseline,
    "minimum_variance": MinimumVarianceBaseline,
}


def baseline_by_name(name: str) -> BaselineStrategy:
    """Construct an approved baseline by stable name."""
    try:
        strategy = BASELINES[name]
    except KeyError as error:
        raise ValueError(f"unsupported baseline: {name}") from error
    return strategy()

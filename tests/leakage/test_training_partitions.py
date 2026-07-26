"""Structural leakage tests for training and feature fitting."""

from __future__ import annotations

import numpy as np
import pytest
from tests.helpers import make_us_ohlcv

from crossmarket_agentgym.data import (
    PartitionAccessError,
    PartitionCapability,
    require_partition,
)
from crossmarket_agentgym.environments import (
    CrossMarketPortfolioEnv,
    EnvironmentConfig,
    MarketDataPanel,
)
from crossmarket_agentgym.features import TrainOnlyStandardizer


def _capability(partition: str) -> PartitionCapability:
    return PartitionCapability(
        dataset_id="fixture",
        partition=partition,  # type: ignore[arg-type]
        start_signal_index=0,
        end_execution_index=2,
    )


def test_standardizer_fits_train_and_never_validation_or_test() -> None:
    """Fit authority is carried by the partition, not caller convention."""
    values = np.array([[1.0, 10.0], [3.0, 14.0]])
    standardizer = TrainOnlyStandardizer().fit(values, _capability("train"))
    fitted_mean = standardizer.state.mean.copy()

    transformed = standardizer.transform(values, _capability("validation"))

    np.testing.assert_allclose(transformed.mean(axis=0), 0.0)
    np.testing.assert_array_equal(standardizer.state.mean, fitted_mean)
    with pytest.raises(PartitionAccessError):
        TrainOnlyStandardizer().fit(values, _capability("validation"))
    with pytest.raises(PartitionAccessError):
        TrainOnlyStandardizer().fit(values, _capability("test"))


def test_training_authority_rejects_test_partition() -> None:
    """A test capability cannot be relabeled at the call site."""
    with pytest.raises(PartitionAccessError):
        require_partition(_capability("test"), frozenset({"train", "smoke"}))


def test_environment_stops_at_partition_execution_boundary() -> None:
    """Training transitions cannot cross into the validation outcome interval."""
    panel = MarketDataPanel.from_frame(make_us_ohlcv(days=6))
    capability = PartitionCapability(
        dataset_id="fixture",
        partition="train",
        start_signal_index=0,
        end_execution_index=2,
    )
    env = CrossMarketPortfolioEnv(
        panel,
        EnvironmentConfig(
            lookback=1,
            max_asset_weight=1.0,
            max_market_weight=1.0,
            cash_floor=0.0,
            max_turnover=2.0,
        ),
        partition=capability,
    )
    _, reset_info = env.reset()
    action = np.array([1.0, 0.0], dtype=np.float32)

    _, _, _, first_truncated, _ = env.step(action)
    _, _, _, second_truncated, info = env.step(action)

    assert reset_info["data_partition"] == "train"
    assert not first_truncated
    assert second_truncated
    assert info["execution_date"] == panel.dates[2].isoformat()

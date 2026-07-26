"""Packaged four-market sample acceptance test."""

from pathlib import Path

from crossmarket_agentgym.data.dataset import validate_manifest_dataset


def test_sample_manifest_and_all_markets_validate() -> None:
    """The distributable sample is complete, valid, and hash-verifiable."""
    summary = validate_manifest_dataset(Path("data/sample"))

    assert summary.is_valid
    assert summary.markets == ["CN", "HK", "JP", "US"]
    assert summary.ohlcv_rows == 20

"""Legacy source-adapter tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from crossmarket_agentgym.data.adapters import LegacyYahooCSVAdapter
from crossmarket_agentgym.data.quality import validate_ohlcv_frame


def write_yahoo_csv(path: Path) -> None:
    """Write a minimal Yahoo-style fixture, including one invalid row."""
    frame = pd.DataFrame(
        {
            "Date": ["2024-01-02 00:00:00+08:00", "2024-01-03 00:00:00+08:00"],
            "Open": [10.0, 12.0],
            "High": [11.0, 11.5],
            "Low": [9.0, 10.0],
            "Close": [10.5, 11.0],
            "Adj Close": [10.4, 10.9],
            "Volume": [1000, 1200],
            "Ticker": ["0001.HK", "0001.HK"],
        }
    )
    frame.to_csv(path, index=False)


def test_yahoo_adapter_normalizes_without_dropping_bad_rows(tmp_path: Path) -> None:
    """Normalization preserves source cardinality and delegates errors to quality checks."""
    path = tmp_path / "0001.HK.csv"
    write_yahoo_csv(path)

    result = LegacyYahooCSVAdapter(market="HK").load(path)
    report = validate_ohlcv_frame(result.frame)

    assert len(result.frame) == 2
    assert result.frame.loc[0, "trade_date"].isoformat() == "2024-01-02"
    assert result.frame.loc[0, "currency"] == "HKD"
    assert "invalid_high" in report.codes


def test_yahoo_adapter_rejects_missing_source_columns(tmp_path: Path) -> None:
    """Missing OHLCV inputs are never guessed."""
    path = tmp_path / "broken.csv"
    pd.DataFrame({"Date": ["2024-01-02"], "Open": [1.0]}).to_csv(path, index=False)

    result = LegacyYahooCSVAdapter(market="US").load(path)

    assert result.frame.empty
    assert result.errors

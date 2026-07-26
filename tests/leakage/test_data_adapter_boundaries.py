"""Leakage-oriented source normalization tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from crossmarket_agentgym.data.adapters import LegacyYahooCSVAdapter
from crossmarket_agentgym.data.schemas import CANONICAL_COLUMNS


def test_local_trade_date_is_not_shifted_through_utc(tmp_path: Path) -> None:
    """A Tokyo local midnight remains the same trading date after normalization."""
    path = tmp_path / "1301.T.csv"
    pd.DataFrame(
        {
            "Date": ["2024-01-04 00:00:00+09:00"],
            "Open": [10.0],
            "High": [11.0],
            "Low": [9.0],
            "Close": [10.5],
            "Adj Close": [10.5],
            "Volume": [1000],
            "Ticker": ["1301.T"],
            "MA_5": [999.0],
            "MA_20": [999.0],
            "MACD": [999.0],
        }
    ).to_csv(path, index=False)

    frame = LegacyYahooCSVAdapter(market="JP").load(path).frame

    assert frame.loc[0, "trade_date"].isoformat() == "2024-01-04"
    assert frame.columns.tolist() == list(CANONICAL_COLUMNS)
    assert not {"MA_5", "MA_20", "MACD"} & set(frame.columns)

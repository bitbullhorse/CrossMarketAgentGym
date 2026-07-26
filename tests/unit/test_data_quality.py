"""Vectorized data-quality report tests."""

from __future__ import annotations

import pandas as pd

from crossmarket_agentgym.data.quality import validate_ohlcv_frame
from crossmarket_agentgym.data.schemas import CANONICAL_COLUMNS


def canonical_frame() -> pd.DataFrame:
    """Return two valid, ordered canonical rows."""
    rows = [
        {
            "trade_date": "2024-01-02",
            "symbol": "A",
            "market": "US",
            "exchange": "US_UNSPECIFIED",
            "open": 10.0,
            "high": 11.0,
            "low": 9.0,
            "close": 10.5,
            "volume": 100.0,
            "currency": "USD",
            "timezone": "America/New_York",
            "adjusted": False,
            "source": "test",
            "adjusted_close": 10.5,
            "turnover": None,
            "suspension_flag": None,
            "limit_up": None,
            "limit_down": None,
            "tradable": True,
        },
        {
            "trade_date": "2024-01-03",
            "symbol": "A",
            "market": "US",
            "exchange": "US_UNSPECIFIED",
            "open": 10.5,
            "high": 11.5,
            "low": 10.0,
            "close": 11.0,
            "volume": 120.0,
            "currency": "USD",
            "timezone": "America/New_York",
            "adjusted": False,
            "source": "test",
            "adjusted_close": 11.0,
            "turnover": None,
            "suspension_flag": None,
            "limit_up": None,
            "limit_down": None,
            "tradable": True,
        },
    ]
    return pd.DataFrame(rows, columns=CANONICAL_COLUMNS)


def test_valid_frame_has_no_errors() -> None:
    """A clean frame produces an auditable empty issue list."""
    report = validate_ohlcv_frame(canonical_frame())

    assert report.is_valid
    assert report.row_count == 2
    assert report.issues == []


def test_duplicates_and_unsorted_dates_are_both_reported() -> None:
    """Independent violations are accumulated rather than short-circuited."""
    frame = canonical_frame().iloc[[1, 0, 0]].reset_index(drop=True)
    report = validate_ohlcv_frame(frame)

    assert not report.is_valid
    assert {"duplicate_primary_key", "unsorted_trade_date"} <= report.codes


def test_invalid_ohlc_and_metadata_are_not_silently_removed() -> None:
    """Quality checks retain row counts and expose every material error."""
    frame = canonical_frame()
    frame.loc[0, "high"] = 5.0
    frame.loc[1, "currency"] = "HKD"
    report = validate_ohlcv_frame(frame)

    assert report.row_count == 2
    assert {"invalid_high", "market_metadata_mismatch"} <= report.codes


def test_missing_required_columns_are_reported() -> None:
    """Schema drift returns a report instead of a pandas traceback."""
    report = validate_ohlcv_frame(canonical_frame().drop(columns=["volume"]))

    assert not report.is_valid
    assert "missing_columns" in report.codes

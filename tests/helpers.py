"""Shared deterministic fixtures for environment tests."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from crossmarket_agentgym.data.schemas import CANONICAL_COLUMNS


def make_us_ohlcv(
    *,
    days: int = 5,
    close_multiplier_last: float = 1.0,
    tradable_last: bool = True,
) -> pd.DataFrame:
    """Create one valid US asset with predictable daily prices."""
    start = date(2024, 1, 2)
    rows: list[dict[str, object]] = []
    for offset in range(days):
        open_price = 100.0 + offset
        close_price = open_price
        if offset == days - 1:
            close_price *= close_multiplier_last
        rows.append(
            {
                "trade_date": start + timedelta(days=offset),
                "symbol": "A",
                "market": "US",
                "exchange": "US_UNSPECIFIED",
                "open": open_price,
                "high": max(open_price, close_price) + 1.0,
                "low": min(open_price, close_price) - 1.0,
                "close": close_price,
                "volume": 1000.0 + offset,
                "currency": "USD",
                "timezone": "America/New_York",
                "adjusted": False,
                "source": "test",
                "adjusted_close": close_price,
                "turnover": None,
                "suspension_flag": False,
                "limit_up": False,
                "limit_down": False,
                "tradable": tradable_last if offset == days - 1 else True,
            }
        )
    return pd.DataFrame(rows, columns=CANONICAL_COLUMNS)

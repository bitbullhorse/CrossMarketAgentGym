"""FX-rate validation and as-of lookup tests."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from crossmarket_agentgym.data.fx import FXRateError, FXRateTable


def test_rate_lookup_uses_only_same_or_prior_dates() -> None:
    """A market holiday can use the latest known rate without future leakage."""
    table = FXRateTable(
        pd.DataFrame(
            {
                "trade_date": [date(2024, 1, 2), date(2024, 1, 4)],
                "base_currency": ["CNY", "CNY"],
                "quote_currency": ["USD", "USD"],
                "rate": [0.14, 0.15],
                "source": ["test", "test"],
            }
        ),
        quote_currency="USD",
    )

    assert table.rate_on_or_before(date(2024, 1, 3), "CNY") == pytest.approx(0.14)
    assert table.rate_on_or_before(date(2024, 1, 4), "CNY") == pytest.approx(0.15)
    assert table.rate_on_or_before(date(2024, 1, 1), "USD") == 1.0


def test_missing_or_nonpositive_rates_fail() -> None:
    """Cross-currency prices cannot enter accounting without a valid conversion."""
    with pytest.raises(FXRateError):
        FXRateTable(
            pd.DataFrame(
                {
                    "trade_date": [date(2024, 1, 2)],
                    "base_currency": ["CNY"],
                    "quote_currency": ["USD"],
                    "rate": [0.0],
                    "source": ["test"],
                }
            ),
            quote_currency="USD",
        )

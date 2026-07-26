"""Leakage-safe FX rate validation and as-of lookup."""

from __future__ import annotations

import bisect
import math
from datetime import date
from typing import Any

import pandas as pd

_REQUIRED_FX_COLUMNS = (
    "trade_date",
    "base_currency",
    "quote_currency",
    "rate",
    "source",
)


class FXRateError(ValueError):
    """Raised when currency conversion would be missing, ambiguous, or invalid."""


class FXRateTable:
    """Immutable lookup of local-currency units into one portfolio currency."""

    def __init__(self, frame: pd.DataFrame, *, quote_currency: str) -> None:
        """Validate a rate frame and index it by currency and local date."""
        missing = [column for column in _REQUIRED_FX_COLUMNS if column not in frame.columns]
        if missing:
            raise FXRateError(f"missing FX columns: {', '.join(missing)}")
        normalized = frame.copy()
        normalized["trade_date"] = pd.to_datetime(
            normalized["trade_date"], errors="coerce"
        ).dt.date
        normalized["base_currency"] = (
            normalized["base_currency"].astype(str).str.upper()
        )
        normalized["quote_currency"] = (
            normalized["quote_currency"].astype(str).str.upper()
        )
        normalized["rate"] = pd.to_numeric(normalized["rate"], errors="coerce")
        if normalized["trade_date"].isna().any():
            raise FXRateError("FX trade_date contains invalid values")
        if (normalized["quote_currency"] != quote_currency.upper()).any():
            raise FXRateError("all FX rows must use the configured quote currency")
        numeric_rates = normalized["rate"].astype(float)
        if (~numeric_rates.map(math.isfinite) | (numeric_rates <= 0)).any():
            raise FXRateError("FX rates must be finite and strictly positive")
        if normalized.duplicated(
            ["trade_date", "base_currency", "quote_currency"]
        ).any():
            raise FXRateError("FX primary keys must be unique")

        self.quote_currency = quote_currency.upper()
        self._dates: dict[str, list[date]] = {}
        self._rates: dict[str, list[float]] = {}
        ordered = normalized.sort_values(["base_currency", "trade_date"])
        for currency, group in ordered.groupby("base_currency", sort=True):
            self._dates[str(currency)] = [
                value for value in group["trade_date"].tolist() if isinstance(value, date)
            ]
            self._rates[str(currency)] = [
                float(value) for value in group["rate"].tolist()
            ]

    def rate_on_or_before(self, value: date, base_currency: str) -> float:
        """Return the latest rate known on a date, never a future rate."""
        currency = base_currency.upper()
        if currency == self.quote_currency:
            return 1.0
        dates = self._dates.get(currency)
        rates = self._rates.get(currency)
        if not dates or not rates:
            raise FXRateError(f"no {currency}/{self.quote_currency} rates available")
        index = bisect.bisect_right(dates, value) - 1
        if index < 0:
            raise FXRateError(
                f"no {currency}/{self.quote_currency} rate on or before {value.isoformat()}"
            )
        return rates[index]

    def metadata(self) -> dict[str, Any]:
        """Return credential-free audit metadata for the indexed table."""
        return {
            "quote_currency": self.quote_currency,
            "currencies": sorted(self._dates),
            "row_count": sum(len(values) for values in self._dates.values()),
            "lookup": "latest_on_or_before",
        }

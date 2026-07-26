"""Canonical OHLCV record tests."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from crossmarket_agentgym.data.schemas import OHLCVRecord


def valid_record() -> dict[str, object]:
    """Return a valid HK record suitable for mutation by individual tests."""
    return {
        "trade_date": date(2024, 1, 2),
        "symbol": "0001.HK",
        "market": "HK",
        "exchange": "XHKG",
        "open": 10.0,
        "high": 11.0,
        "low": 9.5,
        "close": 10.5,
        "volume": 1000.0,
        "currency": "HKD",
        "timezone": "Asia/Hong_Kong",
        "adjusted": False,
        "source": "test",
    }


def test_valid_record_round_trips() -> None:
    """A valid row retains its local trading date and market metadata."""
    record = OHLCVRecord.model_validate(valid_record())

    assert record.trade_date == date(2024, 1, 2)
    assert record.currency == "HKD"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("open", -1.0),
        ("high", float("inf")),
        ("low", float("nan")),
        ("volume", -1.0),
    ],
)
def test_non_finite_or_negative_values_are_rejected(field: str, value: float) -> None:
    """Invalid numeric values fail schema validation rather than being repaired."""
    payload = valid_record()
    payload[field] = value

    with pytest.raises(ValidationError):
        OHLCVRecord.model_validate(payload)


def test_ohlc_envelope_is_enforced() -> None:
    """High and low must envelope open and close."""
    payload = valid_record()
    payload["high"] = 9.0

    with pytest.raises(ValidationError, match="high"):
        OHLCVRecord.model_validate(payload)


def test_market_currency_timezone_must_match() -> None:
    """Cross-market metadata mismatches are explicit schema errors."""
    payload = valid_record()
    payload["currency"] = "USD"

    with pytest.raises(ValidationError, match="currency"):
        OHLCVRecord.model_validate(payload)

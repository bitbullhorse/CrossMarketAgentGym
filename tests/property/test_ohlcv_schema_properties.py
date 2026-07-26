"""Property checks for valid OHLC envelopes."""

from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from crossmarket_agentgym.data.schemas import OHLCVRecord


@given(
    low=st.floats(min_value=0.01, max_value=1000, allow_nan=False, allow_infinity=False),
    spread=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
)
def test_valid_envelopes_always_validate(low: float, spread: float) -> None:
    """Schema validation accepts every finite ordered OHLC envelope."""
    high = low + spread
    midpoint = low + spread / 2
    record = OHLCVRecord(
        trade_date=date(2024, 1, 2),
        symbol="A",
        market="US",
        exchange="US_UNSPECIFIED",
        open=midpoint,
        high=high,
        low=low,
        close=midpoint,
        volume=0,
        currency="USD",
        timezone="America/New_York",
        adjusted=False,
        source="property",
    )

    assert record.low <= record.open <= record.high

"""Canonical daily OHLCV schema shared by every market adapter."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Market = Literal["CN", "HK", "JP", "US"]


@dataclass(frozen=True, slots=True)
class MarketMetadata:
    """Stable metadata that can be validated without guessing an exchange."""

    currency: str
    timezone: str
    default_exchange: str


MARKET_METADATA: dict[Market, MarketMetadata] = {
    "CN": MarketMetadata("CNY", "Asia/Shanghai", "CN_UNSPECIFIED"),
    "HK": MarketMetadata("HKD", "Asia/Hong_Kong", "XHKG"),
    "JP": MarketMetadata("JPY", "Asia/Tokyo", "XTKS"),
    "US": MarketMetadata("USD", "America/New_York", "US_UNSPECIFIED"),
}

REQUIRED_COLUMNS: tuple[str, ...] = (
    "trade_date",
    "symbol",
    "market",
    "exchange",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "currency",
    "timezone",
    "adjusted",
    "source",
)
OPTIONAL_COLUMNS: tuple[str, ...] = (
    "adjusted_close",
    "turnover",
    "suspension_flag",
    "limit_up",
    "limit_down",
    "tradable",
)
CANONICAL_COLUMNS: tuple[str, ...] = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


class OHLCVRecord(BaseModel):
    """One local-market daily bar with explicit provenance and adjustment state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    trade_date: date
    symbol: str = Field(min_length=1)
    market: Market
    exchange: str = Field(min_length=1)
    open: float = Field(ge=0.0)
    high: float = Field(ge=0.0)
    low: float = Field(ge=0.0)
    close: float = Field(ge=0.0)
    volume: float = Field(ge=0.0)
    currency: str = Field(min_length=3, max_length=3)
    timezone: str = Field(min_length=1)
    adjusted: bool
    source: str = Field(min_length=1)
    adjusted_close: float | None = Field(default=None, ge=0.0)
    turnover: float | None = Field(default=None, ge=0.0)
    suspension_flag: bool | None = None
    limit_up: bool | None = None
    limit_down: bool | None = None
    tradable: bool | None = None

    @field_validator("open", "high", "low", "close", "volume", "adjusted_close", "turnover")
    @classmethod
    def require_finite_number(cls, value: float | None) -> float | None:
        """Reject NaN and infinities before accounting code can observe them."""
        if value is not None and not math.isfinite(value):
            raise ValueError("numeric values must be finite")
        return value

    @field_validator("symbol", "exchange", "source")
    @classmethod
    def strip_nonempty_text(cls, value: str) -> str:
        """Normalize surrounding whitespace without changing identifiers."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Use uppercase ISO-style currency codes."""
        return value.upper()

    @model_validator(mode="after")
    def validate_envelope_and_market_metadata(self) -> OHLCVRecord:
        """Validate row accounting inputs and stable market metadata."""
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must envelope open, close, and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must envelope open, close, and high")
        metadata = MARKET_METADATA[self.market]
        if self.currency != metadata.currency:
            raise ValueError(
                f"currency {self.currency!r} does not match market {self.market!r}"
            )
        if self.timezone != metadata.timezone:
            raise ValueError(
                f"timezone {self.timezone!r} does not match market {self.market!r}"
            )
        return self

"""Read-only adapters for the mixed local legacy dataset."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from crossmarket_agentgym.data.adapters.base import AdapterResult
from crossmarket_agentgym.data.schemas import (
    CANONICAL_COLUMNS,
    MARKET_METADATA,
    Market,
)

_YAHOO_REQUIRED = ("Date", "Open", "High", "Low", "Close", "Volume")
_LEGACY_DIRECTORIES: dict[str, Market] = {
    "A股": "CN",
    "港股": "HK",
    "日股": "JP",
    "美股": "US",
}


def _empty_frame() -> pd.DataFrame:
    """Return an empty frame with the stable canonical column order."""
    return pd.DataFrame(columns=CANONICAL_COLUMNS)


def _local_trade_date(values: pd.Series[Any]) -> pd.Series[Any]:
    """Parse the date prefix without converting local midnight through UTC."""
    prefixes = values.astype("string").str.slice(0, 10)
    return pd.to_datetime(prefixes, errors="coerce").dt.date


def _canonicalize_optional_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Add absent optional columns and return a stable column projection."""
    for column in CANONICAL_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    return frame.loc[:, list(CANONICAL_COLUMNS)].reset_index(drop=True)


def _cn_exchange(symbol: str) -> str:
    """Infer only exchange prefixes that are deterministic in Chinese ticker rules."""
    if symbol.startswith(("5", "6", "9")):
        return "XSHG"
    if symbol.startswith(("0", "1", "2", "3")):
        return "XSHE"
    if symbol.startswith(("4", "8")):
        return "XBSE"
    return "CN_UNSPECIFIED"


class LegacyYahooCSVAdapter:
    """Normalize the flat Yahoo-style CSV files used by HK, JP, and US data."""

    def __init__(self, market: Market) -> None:
        """Bind stable market metadata before reading a source file."""
        if market == "CN":
            raise ValueError("CN sources require LegacyCNExcelAdapter")
        self.market = market

    def load(self, path: Path) -> AdapterResult:
        """Read one CSV while retaining every source row, including invalid rows."""
        try:
            raw = pd.read_csv(path)
        except Exception as error:  # noqa: BLE001 - converted to an auditable adapter error
            return AdapterResult(
                frame=_empty_frame(),
                source_path=path,
                errors=(f"read_error: {type(error).__name__}: {error}",),
            )
        missing = [column for column in _YAHOO_REQUIRED if column not in raw.columns]
        if missing:
            return AdapterResult(
                frame=_empty_frame(),
                source_path=path,
                errors=(f"missing_source_columns: {', '.join(missing)}",),
            )

        metadata = MARKET_METADATA[self.market]
        symbols = (
            raw["Ticker"].where(raw["Ticker"].notna(), path.stem).astype(str)
            if "Ticker" in raw.columns
            else pd.Series(path.stem, index=raw.index, dtype="string")
        )
        normalized = pd.DataFrame(index=raw.index)
        normalized["trade_date"] = _local_trade_date(raw["Date"])
        normalized["symbol"] = symbols.str.strip()
        normalized["market"] = self.market
        normalized["exchange"] = metadata.default_exchange
        normalized["open"] = pd.to_numeric(raw["Open"], errors="coerce")
        normalized["high"] = pd.to_numeric(raw["High"], errors="coerce")
        normalized["low"] = pd.to_numeric(raw["Low"], errors="coerce")
        normalized["close"] = pd.to_numeric(raw["Close"], errors="coerce")
        normalized["volume"] = pd.to_numeric(raw["Volume"], errors="coerce")
        normalized["currency"] = metadata.currency
        normalized["timezone"] = metadata.timezone
        normalized["adjusted"] = False
        normalized["source"] = "Yahoo Finance"
        if "Adj Close" in raw.columns:
            normalized["adjusted_close"] = pd.to_numeric(
                raw["Adj Close"], errors="coerce"
            )
        return AdapterResult(
            frame=_canonicalize_optional_columns(normalized),
            source_path=path,
        )


def _column_by_suffix(columns: Iterable[object], suffix: str) -> str | None:
    """Find RESSET columns despite year-specific Chinese unit labels."""
    for column in columns:
        name = str(column)
        if name.endswith(suffix):
            return name
    return None


class LegacyCNExcelAdapter:
    """Normalize RESSET A-share `.xls` and `.xlsx` source files."""

    _required_suffixes = {
        "trade_date": "_Date",
        "open": "_Oppr",
        "high": "_Hipr",
        "low": "_Lopr",
        "close": "_Clpr",
        "volume": "_Trdvol",
    }

    def load(self, path: Path) -> AdapterResult:
        """Read the first worksheet and preserve source cardinality."""
        if path.suffix.lower() not in {".xls", ".xlsx"}:
            return AdapterResult(
                frame=_empty_frame(),
                source_path=path,
                errors=(f"unsupported_extension: {path.suffix}",),
            )
        try:
            raw = pd.read_excel(path, sheet_name=0)
        except Exception as error:  # noqa: BLE001 - converted to an auditable adapter error
            return AdapterResult(
                frame=_empty_frame(),
                source_path=path,
                errors=(f"read_error: {type(error).__name__}: {error}",),
            )

        mapping = {
            target: _column_by_suffix(raw.columns, suffix)
            for target, suffix in self._required_suffixes.items()
        }
        missing = [target for target, source in mapping.items() if source is None]
        if missing:
            return AdapterResult(
                frame=_empty_frame(),
                source_path=path,
                errors=(f"missing_source_columns: {', '.join(missing)}",),
            )

        resolved_mapping = {
            target: source for target, source in mapping.items() if source is not None
        }
        symbol = path.parent.name.zfill(6)
        normalized = pd.DataFrame(index=raw.index)
        normalized["trade_date"] = _local_trade_date(
            raw[resolved_mapping["trade_date"]]
        )
        normalized["symbol"] = symbol
        normalized["market"] = "CN"
        normalized["exchange"] = _cn_exchange(symbol)
        for target in ("open", "high", "low", "close", "volume"):
            normalized[target] = pd.to_numeric(
                raw[resolved_mapping[target]], errors="coerce"
            )
        normalized["currency"] = "CNY"
        normalized["timezone"] = "Asia/Shanghai"
        normalized["adjusted"] = False
        normalized["source"] = "RESSET"

        adjusted = _column_by_suffix(raw.columns, "_AdjClpr2")
        turnover = _column_by_suffix(raw.columns, "_Trdsum")
        if adjusted is not None:
            normalized["adjusted_close"] = pd.to_numeric(raw[adjusted], errors="coerce")
        if turnover is not None:
            normalized["turnover"] = pd.to_numeric(raw[turnover], errors="coerce")

        warnings: list[str] = [
            "adjusted_close uses source field AdjClpr2; raw OHLC remains unadjusted"
        ]
        return AdapterResult(
            frame=_canonicalize_optional_columns(normalized),
            source_path=path,
            warnings=tuple(warnings),
        )


def discover_legacy_files(
    root: Path,
    directory_markets: Mapping[str, Market] | None = None,
) -> dict[Market, list[Path]]:
    """Discover supported files per market in deterministic path order."""
    discovered: dict[Market, list[Path]] = {"CN": [], "HK": [], "JP": [], "US": []}
    mapping = directory_markets or _LEGACY_DIRECTORIES
    for directory_name, market in mapping.items():
        directory = root / directory_name
        if market == "CN":
            paths = [*directory.rglob("*.xls"), *directory.rglob("*.xlsx")]
        else:
            paths = list(directory.glob("*.csv"))
        discovered[market] = sorted(paths, key=lambda value: value.as_posix())
    return discovered


def adapter_for(market: Market) -> LegacyCNExcelAdapter | LegacyYahooCSVAdapter:
    """Return the explicit adapter for a configured market."""
    if market == "CN":
        return LegacyCNExcelAdapter()
    return LegacyYahooCSVAdapter(market=market)

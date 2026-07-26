"""Deterministic, redistributable four-market sample generation."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd

from crossmarket_agentgym.data.io import write_canonical
from crossmarket_agentgym.data.manifests import (
    DatasetManifest,
    FileRole,
    build_dataset_manifest,
    write_manifest,
)
from crossmarket_agentgym.data.schemas import CANONICAL_COLUMNS, MARKET_METADATA, Market

_SAMPLE_SPECS: tuple[tuple[Market, str, str, float], ...] = (
    ("CN", "000001", "XSHE", 10.0),
    ("HK", "0001.HK", "XHKG", 50.0),
    ("JP", "1301.T", "XTKS", 1000.0),
    ("US", "A", "US_UNSPECIFIED", 100.0),
)


def _market_frame(
    market: Market,
    symbol: str,
    exchange: str,
    base_price: float,
) -> pd.DataFrame:
    """Create five deterministic valid rows for one market."""
    metadata = MARKET_METADATA[market]
    start = date(2024, 1, 2)
    rows: list[dict[str, object]] = []
    for offset in range(5):
        trade_date = start + timedelta(days=offset)
        open_price = base_price + offset
        close_price = open_price + (0.25 if offset % 2 == 0 else -0.20)
        rows.append(
            {
                "trade_date": trade_date,
                "symbol": symbol,
                "market": market,
                "exchange": exchange,
                "open": open_price,
                "high": max(open_price, close_price) + 0.5,
                "low": min(open_price, close_price) - 0.5,
                "close": close_price,
                "volume": float(1000 + offset * 100),
                "currency": metadata.currency,
                "timezone": metadata.timezone,
                "adjusted": False,
                "source": "synthetic_phase1_fixture",
                "adjusted_close": close_price,
                "turnover": None,
                "suspension_flag": False,
                "limit_up": False,
                "limit_down": False,
                "tradable": True,
            }
        )
    return pd.DataFrame(rows, columns=CANONICAL_COLUMNS)


def generate_sample_dataset(root: Path, *, overwrite: bool = False) -> DatasetManifest:
    """Generate a synthetic sample whose provenance is safe for redistribution."""
    targets = [
        root / f"market={market}" / "year=2024" / f"{symbol}.parquet"
        for market, symbol, _, _ in _SAMPLE_SPECS
    ]
    targets.extend([root / "instruments.parquet", root / "fx_rates.parquet"])
    if not overwrite:
        existing = [path for path in targets if path.exists()]
        if existing:
            raise FileExistsError(f"sample artifacts already exist: {existing[0]}")

    file_roles: dict[Path, FileRole] = {}
    instrument_rows: list[dict[str, object]] = []
    for (market, symbol, exchange, base_price), path in zip(
        _SAMPLE_SPECS, targets[:4], strict=True
    ):
        frame = _market_frame(market, symbol, exchange, base_price)
        write_canonical(frame, path)
        file_roles[path] = "ohlcv"
        metadata = MARKET_METADATA[market]
        instrument_rows.append(
            {
                "symbol": symbol,
                "market": market,
                "exchange": exchange,
                "currency": metadata.currency,
                "timezone": metadata.timezone,
                "name": f"Synthetic {market} instrument",
                "active": True,
            }
        )

    instruments_path = root / "instruments.parquet"
    pd.DataFrame(instrument_rows).to_parquet(instruments_path, index=False)
    file_roles[instruments_path] = "instruments"

    fx_path = root / "fx_rates.parquet"
    rates = {"CNY": 0.14, "HKD": 0.128, "JPY": 0.0069, "USD": 1.0}
    fx_rows = [
        {
            "trade_date": date(2024, 1, 2) + timedelta(days=offset),
            "base_currency": currency,
            "quote_currency": "USD",
            "rate": rate,
            "source": "synthetic_phase1_fixture",
        }
        for offset in range(5)
        for currency, rate in rates.items()
    ]
    pd.DataFrame(fx_rows).to_parquet(fx_path, index=False)
    file_roles[fx_path] = "fx"

    manifest = build_dataset_manifest(
        root=root,
        dataset_name="crossmarket_agentgym_synthetic_sample",
        file_roles=file_roles,
        source="deterministic synthetic data; not for investment use",
        adjustment_rule="raw synthetic OHLC; adjusted_close equals close; no corporate actions",
        created_at=datetime(2026, 7, 26, tzinfo=UTC),
    )
    write_manifest(manifest, root / "dataset_manifest.json")
    return manifest

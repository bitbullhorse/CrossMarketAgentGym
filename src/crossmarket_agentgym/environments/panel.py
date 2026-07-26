"""Union-calendar market panel with base-currency valuation and tradable masks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from crossmarket_agentgym.data.calendars import MarketCalendar
from crossmarket_agentgym.data.fx import FXRateError, FXRateTable
from crossmarket_agentgym.data.io import load_canonical
from crossmarket_agentgym.data.manifests import load_manifest, verify_manifest
from crossmarket_agentgym.data.quality import DataQualityError, validate_ohlcv_frame
from crossmarket_agentgym.data.schemas import Market

MARKET_IDS: dict[Market, int] = {"CN": 0, "HK": 1, "JP": 2, "US": 3}
CURRENCY_IDS = {"CNY": 0, "HKD": 1, "JPY": 2, "USD": 3}
FEATURE_NAMES: tuple[str, ...] = (
    "open_base",
    "high_base",
    "low_base",
    "close_base",
    "volume",
    "log_return_base",
)


@dataclass(frozen=True, slots=True)
class MarketDataPanel:
    """Dense daily arrays aligned on a union calendar."""

    dates: tuple[date, ...]
    symbols: tuple[str, ...]
    markets: tuple[Market, ...]
    currencies: tuple[str, ...]
    market_ids: NDArray[np.int32]
    currency_ids: NDArray[np.int32]
    features: NDArray[np.float32]
    open_prices: NDArray[np.float64]
    close_prices: NDArray[np.float64]
    tradable_mask: NDArray[np.bool_]
    suspension_mask: NDArray[np.bool_]
    limit_up_mask: NDArray[np.bool_]
    limit_down_mask: NDArray[np.bool_]
    first_fully_valued_index: int
    base_currency: str
    feature_names: tuple[str, ...] = FEATURE_NAMES

    @property
    def asset_count(self) -> int:
        """Return the number of unique market-symbol assets."""
        return len(self.symbols)

    @property
    def session_count(self) -> int:
        """Return union-calendar length."""
        return len(self.dates)

    @classmethod
    def from_manifest(
        cls,
        root: Path,
        *,
        base_currency: str = "USD",
    ) -> MarketDataPanel:
        """Load verified OHLCV and FX artifacts from a canonical dataset root."""
        manifest = load_manifest(root / "dataset_manifest.json")
        verification = verify_manifest(root, manifest)
        if not verification.is_valid:
            raise ValueError("dataset manifest integrity verification failed")
        ohlcv_frames = [
            load_canonical(root / entry.path, require_valid=True).frame
            for entry in manifest.files
            if entry.role == "ohlcv"
        ]
        if not ohlcv_frames:
            raise ValueError("manifest contains no OHLCV artifacts")
        fx_entries = [entry for entry in manifest.files if entry.role == "fx"]
        fx_frame = (
            pd.read_parquet(root / fx_entries[0].path) if fx_entries else None
        )
        return cls.from_frame(
            pd.concat(ohlcv_frames, ignore_index=True),
            fx_rates=fx_frame,
            base_currency=base_currency,
        )

    @classmethod
    def from_frame(
        cls,
        frame: pd.DataFrame,
        *,
        fx_rates: pd.DataFrame | None = None,
        base_currency: str = "USD",
        calendar: MarketCalendar | None = None,
    ) -> MarketDataPanel:
        """Build forward-only valuation arrays on a supplied or observed calendar."""
        report = validate_ohlcv_frame(frame)
        if not report.is_valid:
            raise DataQualityError(report)
        normalized = frame.copy()
        normalized["trade_date"] = pd.to_datetime(
            normalized["trade_date"], errors="raise"
        ).dt.date
        asset_rows = (
            normalized.loc[:, ["market", "symbol", "currency"]]
            .drop_duplicates()
            .sort_values(["market", "symbol"])
        )
        if asset_rows.empty:
            raise ValueError("market panel requires at least one asset")
        observed_dates = tuple(sorted(normalized["trade_date"].unique().tolist()))
        dates = (
            tuple(calendar.sessions(observed_dates[0], observed_dates[-1]))
            if calendar is not None
            else observed_dates
        )
        if not dates:
            raise ValueError("selected market calendar contains no observed-range sessions")
        assets = [
            (str(row.market), str(row.symbol), str(row.currency))
            for row in asset_rows.itertuples(index=False)
        ]
        markets = tuple(asset[0] for asset in assets)
        typed_markets: tuple[Market, ...] = tuple(
            market for market in markets  # type: ignore[misc]
        )
        symbols = tuple(asset[1] for asset in assets)
        currencies = tuple(asset[2] for asset in assets)
        base = base_currency.upper()
        required_fx = any(currency != base for currency in currencies)
        if required_fx and fx_rates is None:
            raise FXRateError("cross-currency panel requires an FX rate table")
        fx_table = (
            FXRateTable(fx_rates, quote_currency=base) if fx_rates is not None else None
        )

        session_count = len(dates)
        asset_count = len(assets)
        open_prices = np.full((session_count, asset_count), np.nan, dtype=np.float64)
        close_prices = np.full_like(open_prices, np.nan)
        features = np.zeros(
            (session_count, asset_count, len(FEATURE_NAMES)), dtype=np.float32
        )
        tradable = np.zeros((session_count, asset_count), dtype=bool)
        suspended = np.zeros_like(tradable)
        limit_up = np.zeros_like(tradable)
        limit_down = np.zeros_like(tradable)
        date_index = pd.Index(dates, name="trade_date")

        for asset_index, (market, symbol, currency) in enumerate(assets):
            group = normalized[
                (normalized["market"].astype(str) == market)
                & (normalized["symbol"].astype(str) == symbol)
            ].copy()
            group = group.set_index("trade_date").reindex(date_index)
            observed: pd.Series[bool] = pd.Series(
                date_index.isin(
                    normalized[
                        (normalized["market"].astype(str) == market)
                        & (normalized["symbol"].astype(str) == symbol)
                    ]["trade_date"]
                ),
                index=date_index,
            )
            local: dict[str, pd.Series[Any]] = {
                column: pd.to_numeric(group[column], errors="coerce")
                for column in ("open", "high", "low", "close", "volume")
            }
            close_ffill = local["close"].ffill()
            rates = np.asarray(
                [
                    1.0
                    if currency == base
                    else fx_table.rate_on_or_before(value, currency)  # type: ignore[union-attr]
                    for value in dates
                ],
                dtype=np.float64,
            )
            observed_values = observed.to_numpy(dtype=bool)
            open_local = local["open"].where(observed, close_ffill)
            high_local = local["high"].where(observed, close_ffill)
            low_local = local["low"].where(observed, close_ffill)
            open_base = open_local.to_numpy(dtype=np.float64) * rates
            close_base = close_ffill.to_numpy(dtype=np.float64) * rates
            high_base = high_local.to_numpy(dtype=np.float64) * rates
            low_base = low_local.to_numpy(dtype=np.float64) * rates
            open_prices[:, asset_index] = open_base
            close_prices[:, asset_index] = close_base

            explicit_tradable = group["tradable"]
            allowed_values = (
                explicit_tradable.isna() | explicit_tradable.eq(True)
            ).to_numpy(dtype=bool)
            suspension_values = group["suspension_flag"].eq(True).to_numpy(dtype=bool)
            finite_bar = (
                np.isfinite(open_base)
                & np.isfinite(close_base)
                & (open_base > 0.0)
                & (close_base > 0.0)
            )
            tradable[:, asset_index] = (
                observed_values
                & allowed_values
                & ~suspension_values
                & finite_bar
            )
            suspended[:, asset_index] = suspension_values
            limit_up[:, asset_index] = group["limit_up"].eq(True).to_numpy(dtype=bool)
            limit_down[:, asset_index] = group["limit_down"].eq(True).to_numpy(dtype=bool)

            close_series = pd.Series(close_base)
            log_return = np.log(close_series / close_series.shift(1)).replace(
                [np.inf, -np.inf], np.nan
            )
            feature_columns = (
                open_base,
                high_base,
                low_base,
                close_base,
                local["volume"].fillna(0.0).to_numpy(dtype=np.float64),
                log_return.fillna(0.0).to_numpy(dtype=np.float64),
            )
            features[:, asset_index, :] = np.nan_to_num(
                np.column_stack(feature_columns),
                nan=0.0,
                posinf=0.0,
                neginf=0.0,
            ).astype(np.float32)

        fully_valued = np.isfinite(close_prices).all(axis=1) & (close_prices > 0).all(axis=1)
        candidates = np.flatnonzero(fully_valued)
        if candidates.size == 0:
            raise ValueError("assets never share a fully valued union-calendar session")
        first_index = int(candidates[0])
        if not np.isfinite(open_prices[first_index:]).all():
            raise ValueError("valuation opens contain gaps after the common start")
        if not np.isfinite(close_prices[first_index:]).all():
            raise ValueError("valuation closes contain gaps after the common start")

        return cls(
            dates=dates,
            symbols=symbols,
            markets=typed_markets,
            currencies=currencies,
            market_ids=np.asarray(
                [MARKET_IDS[market] for market in typed_markets], dtype=np.int32
            ),
            currency_ids=np.asarray(
                [CURRENCY_IDS[currency] for currency in currencies], dtype=np.int32
            ),
            features=features,
            open_prices=open_prices,
            close_prices=close_prices,
            tradable_mask=tradable,
            suspension_mask=suspended,
            limit_up_mask=limit_up,
            limit_down_mask=limit_down,
            first_fully_valued_index=first_index,
            base_currency=base,
        )

    def market_window(self, index: int, lookback: int) -> NDArray[np.float32]:
        """Return `[asset, lookback, feature]` data ending at an index."""
        start = index - lookback + 1
        if start < 0:
            raise ValueError("insufficient history for requested lookback")
        return np.transpose(self.features[start : index + 1], (1, 0, 2)).copy()

    def slice_sessions(self, start: int, end: int) -> MarketDataPanel:
        """Return an isolated inclusive session range with copied arrays."""
        if start < 0 or end < start or end >= self.session_count:
            raise ValueError("invalid panel session slice")
        selection = slice(start, end + 1)
        first_fully_valued = max(0, self.first_fully_valued_index - start)
        if first_fully_valued > end - start:
            raise ValueError("panel slice ends before all assets can be valued")
        return MarketDataPanel(
            dates=self.dates[selection],
            symbols=self.symbols,
            markets=self.markets,
            currencies=self.currencies,
            market_ids=self.market_ids.copy(),
            currency_ids=self.currency_ids.copy(),
            features=self.features[selection].copy(),
            open_prices=self.open_prices[selection].copy(),
            close_prices=self.close_prices[selection].copy(),
            tradable_mask=self.tradable_mask[selection].copy(),
            suspension_mask=self.suspension_mask[selection].copy(),
            limit_up_mask=self.limit_up_mask[selection].copy(),
            limit_down_mask=self.limit_down_mask[selection].copy(),
            first_fully_valued_index=first_fully_valued,
            base_currency=self.base_currency,
            feature_names=self.feature_names,
        )

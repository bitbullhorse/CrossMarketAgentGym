"""Dataset-level validation tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from crossmarket_agentgym.data.dataset import validate_legacy_dataset


def _write_yahoo_source(path: Path, ticker: str) -> None:
    """Write two valid source rows."""
    frame = pd.DataFrame(
        {
            "Date": ["2024-01-02 00:00:00+00:00", "2024-01-03 00:00:00+00:00"],
            "Open": [10.0, 10.5],
            "High": [11.0, 11.5],
            "Low": [9.0, 10.0],
            "Close": [10.5, 11.0],
            "Adj Close": [10.5, 11.0],
            "Volume": [1000, 1200],
            "Ticker": [ticker, ticker],
        }
    )
    frame.to_csv(path, index=False)


def _write_cn_source(path: Path) -> None:
    """Write the stable RESSET suffix subset as an xlsx fixture."""
    pd.DataFrame(
        {
            "日期_Date": ["2024-01-02", "2024-01-03"],
            "开盘价(元)_Oppr": [10.0, 10.5],
            "最高价(元)_Hipr": [11.0, 11.5],
            "最低价(元)_Lopr": [9.0, 10.0],
            "收盘价(元)_Clpr": [10.5, 11.0],
            "成交量(股)_Trdvol": [1000, 1200],
            "复权价2(元)_AdjClpr2": [10.5, 11.0],
            "成交金额(元)_Trdsum": [10500, 13200],
        }
    ).to_excel(path, index=False)


def test_mixed_legacy_layout_loads_all_markets(tmp_path: Path) -> None:
    """One configured source per market passes the same quality boundary."""
    cn_dir = tmp_path / "A股" / "000001"
    cn_dir.mkdir(parents=True)
    _write_cn_source(cn_dir / "source.xlsx")
    for directory, ticker in (
        ("港股", "0001.HK"),
        ("日股", "1301.T"),
        ("美股", "A"),
    ):
        market_dir = tmp_path / directory
        market_dir.mkdir()
        _write_yahoo_source(market_dir / f"{ticker}.csv", ticker)

    summary = validate_legacy_dataset(tmp_path, max_files_per_market=1)

    assert summary.is_valid
    assert summary.markets == ["CN", "HK", "JP", "US"]
    assert summary.files_checked == 4
    assert summary.ohlcv_rows == 8


def test_missing_market_directories_are_reported(tmp_path: Path) -> None:
    """An incomplete legacy tree fails with a stable issue code."""
    summary = validate_legacy_dataset(tmp_path, max_files_per_market=1)

    assert not summary.is_valid
    assert summary.quality.codes == {"missing_market_source"}

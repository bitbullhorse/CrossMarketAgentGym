"""Read-only smoke tests against the user-provided source tree."""

from __future__ import annotations

from pathlib import Path

import pytest

from crossmarket_agentgym.data.adapters import (
    LegacyCNExcelAdapter,
    LegacyYahooCSVAdapter,
)
from crossmarket_agentgym.data.quality import validate_ohlcv_frame

ROOT = Path("stock_data")


@pytest.mark.integration
@pytest.mark.skipif(not ROOT.exists(), reason="local source data is not distributed")
def test_one_source_file_from_each_market_loads() -> None:
    """The actual mixed source layout normalizes all four markets."""
    cn_path = next((ROOT / "A股").rglob("*.xls"))
    sources = [
        LegacyCNExcelAdapter().load(cn_path),
        LegacyYahooCSVAdapter(market="HK").load(next((ROOT / "港股").glob("*.csv"))),
        LegacyYahooCSVAdapter(market="JP").load(next((ROOT / "日股").glob("*.csv"))),
        LegacyYahooCSVAdapter(market="US").load(next((ROOT / "美股").glob("*.csv"))),
    ]

    assert [result.frame["market"].iloc[0] for result in sources] == ["CN", "HK", "JP", "US"]
    assert all(len(result.frame) > 100 for result in sources)
    assert all("missing_columns" not in validate_ohlcv_frame(result.frame).codes for result in sources)

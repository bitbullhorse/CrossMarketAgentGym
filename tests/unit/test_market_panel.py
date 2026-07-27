"""Union-calendar and base-currency panel tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from crossmarket_agentgym.data.calendars import StaticMarketCalendar
from crossmarket_agentgym.data.io import write_canonical
from crossmarket_agentgym.data.manifests import (
    build_dataset_manifest,
    write_manifest,
)
from crossmarket_agentgym.environments import MarketDataPanel
from tests.helpers import make_us_ohlcv


def test_manifest_panel_converts_local_prices_before_accounting() -> None:
    """CN and US prices are represented in one configured base currency."""
    panel = MarketDataPanel.from_manifest(Path("data/sample"), base_currency="USD")
    cn_index = panel.symbols.index("000001")
    us_index = panel.symbols.index("A")

    assert panel.open_prices[0, cn_index] == pytest.approx(10.0 * 0.14)
    assert panel.open_prices[0, us_index] == pytest.approx(100.0)


def test_manifest_panel_restores_all_null_optional_control_columns(
    tmp_path: Path,
) -> None:
    """An all-null optional control column keeps its documented default semantics."""
    frame = make_us_ohlcv(days=3)
    controls = ("tradable", "suspension_flag", "limit_up", "limit_down")
    for column in controls:
        frame[column] = pd.Series([pd.NA] * len(frame), dtype="boolean")
    bars = tmp_path / "bars.parquet"
    write_canonical(frame, bars, require_valid=True)
    manifest = build_dataset_manifest(
        root=tmp_path,
        dataset_name="all-null-controls",
        file_roles={bars: "ohlcv"},
        source="unit-test",
        adjustment_rule="none",
    )
    write_manifest(manifest, tmp_path / "dataset_manifest.json")

    panel = MarketDataPanel.from_manifest(tmp_path)

    assert panel.tradable_mask.all()
    assert not panel.suspension_mask.any()
    assert not panel.limit_up_mask.any()
    assert not panel.limit_down_mask.any()


def test_union_calendar_forward_values_but_never_marks_closure_tradable() -> None:
    """Valuation continuity is separate from execution eligibility."""
    first = make_us_ohlcv(days=3)
    second = make_us_ohlcv(days=3).copy()
    second["symbol"] = "B"
    second = second[second["trade_date"] != date(2024, 1, 3)]
    panel = MarketDataPanel.from_frame(
        pd.concat([first, second], ignore_index=True).sort_values(
            ["symbol", "trade_date"]
        )
    )
    b_index = panel.symbols.index("B")
    closure_index = panel.dates.index(date(2024, 1, 3))

    assert panel.close_prices[closure_index, b_index] == pytest.approx(
        panel.close_prices[closure_index - 1, b_index]
    )
    assert not panel.tradable_mask[closure_index, b_index]
    assert not panel.tradable_without_suspension_mask[closure_index, b_index]


def test_panel_separates_suspension_from_other_tradability_causes() -> None:
    frame = make_us_ohlcv(days=3)
    frame.loc[1, "suspension_flag"] = True
    panel = MarketDataPanel.from_frame(frame)

    assert not panel.tradable_mask[1, 0]
    assert panel.tradable_without_suspension_mask[1, 0]


def test_panel_honors_an_explicit_intersection_or_rebalance_calendar() -> None:
    """Panel construction can select a strict subset without changing source bars."""
    frame = make_us_ohlcv(days=3)
    calendar = StaticMarketCalendar(
        name="scheduled",
        all_sessions=(date(2024, 1, 2), date(2024, 1, 4)),
    )

    panel = MarketDataPanel.from_frame(frame, calendar=calendar)

    assert panel.dates == calendar.all_sessions


def test_panel_session_slice_copies_only_authorized_dates() -> None:
    """Partition panels do not retain hidden later arrays by reference."""
    panel = MarketDataPanel.from_frame(make_us_ohlcv(days=5))

    sliced = panel.slice_sessions(1, 3)
    panel.close_prices[2, 0] = 999.0

    assert sliced.dates == panel.dates[1:4]
    assert sliced.session_count == 3
    assert sliced.close_prices[1, 0] != 999.0

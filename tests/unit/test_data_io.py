"""Canonical CSV and Parquet loader tests."""

from __future__ import annotations

from pathlib import Path

from crossmarket_agentgym.data.io import load_canonical, write_canonical
from tests.unit.test_data_quality import canonical_frame


def test_canonical_csv_round_trip(tmp_path: Path) -> None:
    """CSV export reloads through the same quality boundary."""
    path = tmp_path / "sample.csv"
    write_canonical(canonical_frame(), path)

    loaded = load_canonical(path)

    assert loaded.report.is_valid
    assert len(loaded.frame) == 2


def test_canonical_parquet_round_trip(tmp_path: Path) -> None:
    """Parquet preserves canonical data and validation."""
    path = tmp_path / "sample.parquet"
    write_canonical(canonical_frame(), path)

    loaded = load_canonical(path)

    assert loaded.report.is_valid
    assert loaded.frame["symbol"].tolist() == ["A", "A"]

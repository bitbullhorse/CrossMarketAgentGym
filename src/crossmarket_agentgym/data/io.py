"""Canonical CSV and Parquet I/O with mandatory quality reporting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from crossmarket_agentgym.data.quality import (
    DataQualityError,
    DataQualityReport,
    validate_ohlcv_frame,
)
from crossmarket_agentgym.data.schemas import CANONICAL_COLUMNS


@dataclass(frozen=True, slots=True)
class CanonicalLoadResult:
    """A loaded frame and the non-destructive report produced for it."""

    frame: pd.DataFrame
    report: DataQualityReport
    path: Path


def _normalize_loaded_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize storage dtypes while retaining every row and its order."""
    normalized = frame.copy()
    for column in CANONICAL_COLUMNS:
        if column not in normalized.columns and column not in {
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
        }:
            normalized[column] = None
    if "trade_date" in normalized.columns:
        normalized["trade_date"] = pd.to_datetime(
            normalized["trade_date"], errors="coerce"
        ).dt.date
    available = [column for column in CANONICAL_COLUMNS if column in normalized.columns]
    unknown = [column for column in normalized.columns if column not in CANONICAL_COLUMNS]
    return normalized.loc[:, [*available, *unknown]].reset_index(drop=True)


def load_canonical(path: Path, *, require_valid: bool = False) -> CanonicalLoadResult:
    """Load canonical CSV or Parquet and optionally reject its quality report."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        raw = pd.read_csv(path)
    elif suffix in {".parquet", ".pq"}:
        raw = pd.read_parquet(path)
    else:
        raise ValueError(f"unsupported canonical format: {path.suffix}")
    frame = _normalize_loaded_frame(raw)
    report = validate_ohlcv_frame(frame)
    if require_valid and not report.is_valid:
        raise DataQualityError(report)
    return CanonicalLoadResult(frame=frame, report=report, path=path)


def write_canonical(
    frame: pd.DataFrame,
    path: Path,
    *,
    require_valid: bool = True,
) -> DataQualityReport:
    """Validate and write canonical CSV or Parquet without sorting or row deletion."""
    report = validate_ohlcv_frame(frame)
    if require_valid and not report.is_valid:
        raise DataQualityError(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    stable = frame.loc[:, [column for column in CANONICAL_COLUMNS if column in frame.columns]]
    suffix = path.suffix.lower()
    if suffix == ".csv":
        stable.to_csv(path, index=False)
    elif suffix in {".parquet", ".pq"}:
        stable.to_parquet(path, index=False)
    else:
        raise ValueError(f"unsupported canonical format: {path.suffix}")
    return report

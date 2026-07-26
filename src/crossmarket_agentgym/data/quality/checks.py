"""Vectorized, non-mutating OHLCV quality checks."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd

from crossmarket_agentgym.data.quality.report import DataQualityReport, QualityIssue
from crossmarket_agentgym.data.schemas import MARKET_METADATA, REQUIRED_COLUMNS

_NUMERIC_COLUMNS = ("open", "high", "low", "close", "volume")
_PRIMARY_KEY = ("trade_date", "symbol", "market")
_MAX_EXAMPLE_ROWS = 20


def _positions(mask: pd.Series[Any]) -> list[int]:
    """Return bounded positional examples for a boolean mask."""
    values = mask.fillna(False).to_numpy(dtype=bool)
    return [int(value) for value in np.flatnonzero(values)[:_MAX_EXAMPLE_ROWS]]


def _issue(
    *,
    code: str,
    message: str,
    mask: pd.Series[Any],
    columns: Iterable[str],
    severity: str = "error",
) -> QualityIssue | None:
    """Create an issue only when at least one row is affected."""
    normalized = mask.fillna(False).astype(bool)
    count = int(normalized.sum())
    if count == 0:
        return None
    return QualityIssue(
        code=code,
        severity=severity,  # type: ignore[arg-type]
        message=message,
        count=count,
        rows=_positions(normalized),
        columns=list(columns),
    )


def validate_ohlcv_frame(frame: pd.DataFrame) -> DataQualityReport:
    """Inspect a canonical frame and report every detected invariant violation."""
    row_count = len(frame)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        return DataQualityReport(
            row_count=row_count,
            issues=[
                QualityIssue(
                    code="missing_columns",
                    severity="error",
                    message="required canonical columns are missing",
                    count=len(missing),
                    columns=missing,
                )
            ],
        )

    issues: list[QualityIssue] = []
    required_null = frame.loc[:, list(REQUIRED_COLUMNS)].isna().any(axis=1)
    issue = _issue(
        code="null_required_value",
        message="one or more required values are null",
        mask=required_null,
        columns=REQUIRED_COLUMNS,
    )
    if issue is not None:
        issues.append(issue)

    dates = pd.to_datetime(frame["trade_date"], errors="coerce")
    issue = _issue(
        code="invalid_trade_date",
        message="trade_date cannot be parsed",
        mask=dates.isna(),
        columns=["trade_date"],
    )
    if issue is not None:
        issues.append(issue)

    numeric: dict[str, pd.Series[Any]] = {}
    for column in _NUMERIC_COLUMNS:
        values = pd.to_numeric(frame[column], errors="coerce")
        numeric[column] = values
        issue = _issue(
            code="invalid_numeric",
            message=f"{column} contains null, non-numeric, NaN, or infinite values",
            mask=values.isna() | ~np.isfinite(values),
            columns=[column],
        )
        if issue is not None:
            issues.append(issue)
        issue = _issue(
            code="negative_numeric",
            message=f"{column} must be non-negative",
            mask=values < 0,
            columns=[column],
        )
        if issue is not None:
            issues.append(issue)

    envelope_max = pd.concat(
        [numeric["open"], numeric["close"], numeric["low"]], axis=1
    ).max(axis=1)
    issue = _issue(
        code="invalid_high",
        message="high does not envelope open, close, and low",
        mask=numeric["high"] < envelope_max,
        columns=["open", "high", "low", "close"],
    )
    if issue is not None:
        issues.append(issue)

    envelope_min = pd.concat(
        [numeric["open"], numeric["close"], numeric["high"]], axis=1
    ).min(axis=1)
    issue = _issue(
        code="invalid_low",
        message="low does not envelope open, close, and high",
        mask=numeric["low"] > envelope_min,
        columns=["open", "high", "low", "close"],
    )
    if issue is not None:
        issues.append(issue)

    duplicates = frame.duplicated(list(_PRIMARY_KEY), keep=False)
    issue = _issue(
        code="duplicate_primary_key",
        message="(trade_date, symbol, market) must be unique",
        mask=duplicates,
        columns=_PRIMARY_KEY,
    )
    if issue is not None:
        issues.append(issue)

    unsorted = pd.Series(False, index=frame.index, dtype=bool)
    order_frame = pd.DataFrame(
        {
            "market": frame["market"],
            "symbol": frame["symbol"],
            "trade_date": dates,
        },
        index=frame.index,
    )
    for _, group in order_frame.groupby(["market", "symbol"], sort=False, dropna=False):
        backwards = group["trade_date"] < group["trade_date"].shift(1)
        unsorted.loc[group.index] = backwards.fillna(False)
    issue = _issue(
        code="unsorted_trade_date",
        message="dates must be non-decreasing within each market and symbol",
        mask=unsorted,
        columns=["market", "symbol", "trade_date"],
    )
    if issue is not None:
        issues.append(issue)

    expected_currency = frame["market"].map(
        {market: metadata.currency for market, metadata in MARKET_METADATA.items()}
    )
    expected_timezone = frame["market"].map(
        {market: metadata.timezone for market, metadata in MARKET_METADATA.items()}
    )
    metadata_mismatch = expected_currency.isna() | expected_timezone.isna()
    metadata_mismatch |= frame["currency"] != expected_currency
    metadata_mismatch |= frame["timezone"] != expected_timezone
    issue = _issue(
        code="market_metadata_mismatch",
        message="market, currency, and timezone mapping is inconsistent",
        mask=metadata_mismatch,
        columns=["market", "currency", "timezone"],
    )
    if issue is not None:
        issues.append(issue)

    return DataQualityReport(row_count=row_count, issues=issues)


def merge_quality_reports(
    reports: Iterable[tuple[str, DataQualityReport]],
) -> DataQualityReport:
    """Merge file reports while retaining each finding's relative file context."""
    row_count = 0
    issues: list[QualityIssue] = []
    for file_name, report in reports:
        row_count += report.row_count
        issues.extend(
            issue.model_copy(update={"file": issue.file or file_name})
            for issue in report.issues
        )
    return DataQualityReport(row_count=row_count, issues=issues)

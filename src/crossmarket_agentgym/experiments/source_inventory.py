"""Non-mutating inventory and quality-gated universe selection for Phase 12."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from crossmarket_agentgym.data.adapters import adapter_for, discover_legacy_files
from crossmarket_agentgym.data.config import load_data_config
from crossmarket_agentgym.data.manifests import sha256_file
from crossmarket_agentgym.data.quality import validate_ohlcv_frame
from crossmarket_agentgym.data.schemas import Market

SelectionStatus = Literal[
    "training_universe",
    "held_out_unseen",
    "eligible_not_selected",
    "quarantined",
    "superseded_source",
]


class SourceQualityIssue(BaseModel):
    """Compact source-file error with bounded source row examples."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    count: int = Field(ge=1)
    rows: tuple[int, ...] = ()


class SourceFileRecord(BaseModel):
    """One immutable source-file identity and selection decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    market: Market
    symbol: str
    row_count: int = Field(ge=0)
    ohlcv_row_count: int = Field(ge=0)
    date_start: date | None
    date_end: date | None
    quality_valid: bool
    issues: tuple[SourceQualityIssue, ...] = ()
    semantic_exclusion_rows: tuple[int, ...] = ()
    semantic_exclusion_reason: (
        Literal["non_ohlcv_record_with_all_price_volume_fields_missing"] | None
    ) = None
    selection_quality_valid: bool | None = None
    selection_information_cutoff: date | None = None
    selection_row_count: int | None = Field(default=None, ge=0)
    selection_date_start: date | None = None
    selection_date_end: date | None = None
    accepted_ohlcv_row_count: int | None = Field(default=None, ge=0)
    censor_mode: Literal[
        "none",
        "prefix_before_first_invalid_position",
        "selection_window_only",
    ] | None = None
    censored_from_position: int | None = Field(default=None, ge=0)
    censored_from_date: date | None = None
    censored_after_date: date | None = None
    post_cutoff_issue_codes: tuple[str, ...] = ()
    selection_status: SelectionStatus
    selection_reason: str


class SourceInventory(BaseModel):
    """Frozen source inventory without redistribution of raw market data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    inventory_id: Literal[
        "source-inventory-v1",
        "source-inventory-v2",
        "source-inventory-v3",
    ]
    protocol_id: Literal["protocol-v1", "protocol-v2", "protocol-v4"]
    created_at: datetime
    source_root: str
    mutation_policy: Literal["reject"]
    allow_row_repair: Literal[False] = False
    ordering: Literal["sha256_market_symbol_salt"]
    ordering_salt: str
    minimum_coverage_start: date
    minimum_coverage_end: date
    assets_per_market: int = Field(ge=2)
    held_out_assets_per_market: int = Field(ge=1)
    source_file_count: int = Field(ge=1)
    selected_symbol_count: int = Field(ge=1)
    quarantined_file_count: int = Field(ge=0)
    selected_symbols: dict[Market, tuple[str, ...]]
    training_symbols: dict[Market, tuple[str, ...]]
    held_out_symbols: dict[Market, tuple[str, ...]]
    future_data_used_for_source_selection: bool | None = None
    files: tuple[SourceFileRecord, ...]


def _symbol(frame: pd.DataFrame, path: Path) -> str:
    values = tuple(
        str(value)
        for value in sorted(frame["symbol"].dropna().astype(str).unique().tolist())
    )
    if len(values) == 1:
        return values[0]
    if values:
        return "|".join(values)
    return path.parent.name if path.suffix.lower() in {".xls", ".xlsx"} else path.stem


def _date_bounds(frame: pd.DataFrame) -> tuple[date | None, date | None]:
    values = pd.to_datetime(frame["trade_date"], errors="coerce").dropna()
    if values.empty:
        return None, None
    return values.min().date(), values.max().date()


def _ordering_key(salt: str, market: Market, symbol: str) -> str:
    return hashlib.sha256(f"{salt}:{market}:{symbol}".encode()).hexdigest()


def _record_source(
    *,
    root: Path,
    path: Path,
    market: Market,
) -> SourceFileRecord:
    result = adapter_for(market).load(path)
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    ohlcv_frame = result.frame
    semantic_rows: tuple[int, ...] = ()
    if result.errors:
        issues = tuple(
            SourceQualityIssue(code="source_adapter_error", count=1)
            for _ in result.errors
        )
        valid = False
    else:
        numeric_columns = ["open", "high", "low", "close", "volume"]
        all_numeric_missing = result.frame.loc[:, numeric_columns].isna().all(axis=1)
        semantic_rows = tuple(
            int(index)
            for index in result.frame.index[all_numeric_missing].tolist()
        )
        ohlcv_frame = result.frame.loc[~all_numeric_missing].reset_index(drop=True)
        report = validate_ohlcv_frame(ohlcv_frame)
        issues = tuple(
            SourceQualityIssue(
                code=issue.code,
                count=issue.count,
                rows=tuple(issue.rows),
            )
            for issue in report.issues
            if issue.severity == "error"
        )
        valid = report.is_valid
    date_start, date_end = _date_bounds(ohlcv_frame)
    return SourceFileRecord(
        path=relative,
        sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
        market=market,
        symbol=_symbol(ohlcv_frame, path),
        row_count=len(result.frame),
        ohlcv_row_count=len(ohlcv_frame),
        date_start=date_start,
        date_end=date_end,
        quality_valid=valid,
        issues=issues,
        semantic_exclusion_rows=semantic_rows,
        semantic_exclusion_reason=(
            "non_ohlcv_record_with_all_price_volume_fields_missing"
            if semantic_rows
            else None
        ),
        selection_status="quarantined",
        selection_reason=(
            "source contains one or more quality errors"
            if not valid
            else "awaiting deterministic coverage and universe selection"
        ),
    )


def build_source_inventory(
    *,
    data_config: Path,
    output_path: Path,
    ordering_salt: str,
    minimum_coverage_start: date,
    minimum_coverage_end: date,
    assets_per_market: int,
    held_out_assets_per_market: int,
    created_at: datetime,
) -> SourceInventory:
    """Scan every source, quarantine invalid files, and select a fixed universe."""
    if output_path.exists():
        raise FileExistsError(
            f"source inventory already exists; create a new version: {output_path}"
        )
    if created_at.tzinfo is None:
        raise ValueError("inventory created_at must be timezone-aware")
    if held_out_assets_per_market >= assets_per_market:
        raise ValueError("held-out count must be smaller than selected count")

    config = load_data_config(data_config)
    dataset = config.dataset
    if dataset.layout != "legacy_mixed":
        raise ValueError("formal source inventory requires legacy_mixed input")
    root = dataset.root
    discovered = discover_legacy_files(root, dataset.markets or None)
    markets: tuple[Market, ...] = ("CN", "HK", "JP", "US")
    records = [
        _record_source(root=root, path=path, market=market)
        for market in markets
        for path in discovered[market]
    ]

    eligible_by_symbol: dict[tuple[Market, str], list[int]] = {}
    for index, record in enumerate(records):
        covers_window = (
            record.date_start is not None
            and record.date_end is not None
            and record.date_start <= minimum_coverage_start
            and record.date_end >= minimum_coverage_end
        )
        if record.quality_valid and covers_window:
            eligible_by_symbol.setdefault((record.market, record.symbol), []).append(index)
        elif record.quality_valid:
            records[index] = record.model_copy(
                update={
                    "selection_status": "quarantined",
                    "selection_reason": "valid source does not cover the frozen experiment window",
                }
            )

    chosen_sources: dict[tuple[Market, str], int] = {}
    for identity, indexes in eligible_by_symbol.items():
        preferred = min(
            indexes,
            key=lambda index: (-records[index].ohlcv_row_count, records[index].path),
        )
        chosen_sources[identity] = preferred
        for index in indexes:
            if index != preferred:
                records[index] = records[index].model_copy(
                    update={
                        "selection_status": "superseded_source",
                        "selection_reason": (
                            "another valid source for this symbol has greater coverage"
                        ),
                    }
                )

    selected_symbols: dict[Market, tuple[str, ...]] = {}
    training_symbols: dict[Market, tuple[str, ...]] = {}
    held_out_symbols: dict[Market, tuple[str, ...]] = {}
    for market in ("CN", "HK", "JP", "US"):
        typed_market: Market = market
        symbols = sorted(
            (
                symbol
                for candidate_market, symbol in chosen_sources
                if candidate_market == typed_market
            ),
            key=lambda symbol: _ordering_key(ordering_salt, typed_market, symbol),
        )
        if len(symbols) < assets_per_market:
            raise ValueError(
                f"{typed_market} has {len(symbols)} eligible symbols; "
                f"{assets_per_market} required"
            )
        selected = tuple(symbols[:assets_per_market])
        training = selected[:-held_out_assets_per_market]
        held_out = selected[-held_out_assets_per_market:]
        selected_symbols[typed_market] = selected
        training_symbols[typed_market] = training
        held_out_symbols[typed_market] = held_out
        for symbol in symbols:
            index = chosen_sources[(typed_market, symbol)]
            if symbol in training:
                status: SelectionStatus = "training_universe"
                reason = "selected by frozen hash order for model-visible universe"
            elif symbol in held_out:
                status = "held_out_unseen"
                reason = "selected by frozen hash order for unseen-stock evaluation"
            else:
                status = "eligible_not_selected"
                reason = "quality and coverage passed but fixed market budget was filled"
            records[index] = records[index].model_copy(
                update={
                    "selection_status": status,
                    "selection_reason": reason,
                }
            )

    inventory = SourceInventory(
        inventory_id="source-inventory-v1",
        protocol_id="protocol-v1",
        created_at=created_at.astimezone(UTC),
        source_root=root.as_posix(),
        mutation_policy="reject",
        ordering="sha256_market_symbol_salt",
        ordering_salt=ordering_salt,
        minimum_coverage_start=minimum_coverage_start,
        minimum_coverage_end=minimum_coverage_end,
        assets_per_market=assets_per_market,
        held_out_assets_per_market=held_out_assets_per_market,
        source_file_count=len(records),
        selected_symbol_count=sum(len(values) for values in selected_symbols.values()),
        quarantined_file_count=sum(
            record.selection_status == "quarantined" for record in records
        ),
        selected_symbols=selected_symbols,
        training_symbols=training_symbols,
        held_out_symbols=held_out_symbols,
        files=tuple(records),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            inventory.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return inventory


def load_source_inventory(path: Path) -> SourceInventory:
    """Load one strict source inventory."""
    return SourceInventory.model_validate_json(path.read_text(encoding="utf-8"))


def _record_source_v2(
    *,
    root: Path,
    path: Path,
    market: Market,
    experiment_start: date,
    experiment_end: date,
    selection_cutoff: date,
) -> SourceFileRecord:
    """Validate only information available by formation, then audit future censoring."""
    result = adapter_for(market).load(path)
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    if result.errors:
        return SourceFileRecord(
            path=relative,
            sha256=sha256_file(path),
            size_bytes=path.stat().st_size,
            market=market,
            symbol=_symbol(result.frame, path),
            row_count=len(result.frame),
            ohlcv_row_count=0,
            date_start=None,
            date_end=None,
            quality_valid=False,
            selection_quality_valid=False,
            selection_information_cutoff=selection_cutoff,
            selection_row_count=0,
            accepted_ohlcv_row_count=0,
            issues=tuple(
                SourceQualityIssue(code="source_adapter_error", count=1)
                for _ in result.errors
            ),
            selection_status="quarantined",
            selection_reason="source adapter failed before universe selection",
        )

    numeric_columns = ["open", "high", "low", "close", "volume"]
    all_numeric_missing = result.frame.loc[:, numeric_columns].isna().all(axis=1)
    semantic_rows = tuple(
        int(index) for index in result.frame.index[all_numeric_missing].tolist()
    )
    clean = result.frame.loc[~all_numeric_missing].reset_index(drop=True)
    dates = pd.to_datetime(clean["trade_date"], errors="coerce").dt.date
    in_experiment = (dates >= experiment_start) & (dates <= experiment_end)
    experiment = clean.loc[in_experiment].reset_index(drop=True)
    experiment_dates = pd.to_datetime(
        experiment["trade_date"], errors="coerce"
    ).dt.date
    selection = experiment.loc[
        experiment_dates <= selection_cutoff
    ].reset_index(drop=True)
    selection_date_start, selection_date_end = _date_bounds(selection)
    selection_report = validate_ohlcv_frame(selection)
    selection_issues = tuple(
        SourceQualityIssue(
            code=issue.code,
            count=issue.count,
            rows=tuple(issue.rows),
        )
        for issue in selection_report.issues
        if issue.severity == "error"
    )
    selection_valid = selection_report.is_valid
    full_report = validate_ohlcv_frame(experiment)
    post_codes: tuple[str, ...] = ()
    accepted = experiment
    censored_from_position: int | None = None
    censored_from_date: date | None = None
    if selection_valid and not full_report.is_valid:
        error_issues = [
            issue for issue in full_report.issues if issue.severity == "error"
        ]
        first_invalid = min(
            row
            for issue in error_issues
            for row in issue.rows
        )
        censored_from_position = first_invalid
        accepted = experiment.iloc[:first_invalid].reset_index(drop=True)
        accepted_report = validate_ohlcv_frame(accepted)
        if not accepted_report.is_valid:
            raise ValueError(
                f"prefix censoring did not produce valid data: {relative}"
            )
        invalid_date = pd.to_datetime(
            experiment.iloc[first_invalid]["trade_date"],
            errors="coerce",
        )
        censored_from_date = (
            None if pd.isna(invalid_date) else invalid_date.date()
        )
        post_codes = tuple(sorted({issue.code for issue in error_issues}))
    date_start, date_end = _date_bounds(accepted)
    symbol = _symbol(selection if not selection.empty else experiment, path)
    return SourceFileRecord(
        path=relative,
        sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
        market=market,
        symbol=symbol,
        row_count=len(result.frame),
        ohlcv_row_count=len(experiment),
        date_start=date_start,
        date_end=date_end,
        quality_valid=full_report.is_valid,
        issues=selection_issues,
        semantic_exclusion_rows=semantic_rows,
        semantic_exclusion_reason=(
            "non_ohlcv_record_with_all_price_volume_fields_missing"
            if semantic_rows
            else None
        ),
        selection_quality_valid=selection_valid,
        selection_information_cutoff=selection_cutoff,
        selection_row_count=len(selection),
        selection_date_start=selection_date_start,
        selection_date_end=selection_date_end,
        accepted_ohlcv_row_count=len(accepted),
        censored_from_position=censored_from_position,
        censored_from_date=censored_from_date,
        post_cutoff_issue_codes=post_codes,
        selection_status="quarantined",
        selection_reason=(
            "awaiting cutoff-safe coverage and hash selection"
            if selection_valid
            else "source has a quality error at or before universe formation"
        ),
    )


def build_source_inventory_v2(
    *,
    data_config: Path,
    output_path: Path,
    ordering_salt: str,
    experiment_start: date,
    experiment_end: date,
    selection_cutoff: date,
    assets_per_market: int,
    held_out_assets_per_market: int,
    created_at: datetime,
) -> SourceInventory:
    """Freeze a universe without observing post-formation availability or quality."""
    if output_path.exists():
        raise FileExistsError(
            f"source inventory already exists; create a new version: {output_path}"
        )
    if created_at.tzinfo is None:
        raise ValueError("inventory created_at must be timezone-aware")
    if not experiment_start <= selection_cutoff < experiment_end:
        raise ValueError("selection cutoff must lie inside the experiment window")
    config = load_data_config(data_config)
    dataset = config.dataset
    if dataset.layout != "legacy_mixed":
        raise ValueError("formal source inventory requires legacy_mixed input")
    root = dataset.root
    discovered = discover_legacy_files(root, dataset.markets or None)
    markets: tuple[Market, ...] = ("CN", "HK", "JP", "US")
    records = [
        _record_source_v2(
            root=root,
            path=path,
            market=market,
            experiment_start=experiment_start,
            experiment_end=experiment_end,
            selection_cutoff=selection_cutoff,
        )
        for market in markets
        for path in discovered[market]
    ]

    eligible_by_symbol: dict[tuple[Market, str], list[int]] = {}
    for index, record in enumerate(records):
        covers_known_window = (
            record.selection_date_start is not None
            and record.selection_date_end is not None
            and record.selection_row_count is not None
            and record.selection_row_count > 0
            and record.selection_date_start <= experiment_start
            and record.selection_date_end >= selection_cutoff
            and record.selection_quality_valid is True
        )
        if covers_known_window:
            eligible_by_symbol.setdefault((record.market, record.symbol), []).append(index)
        elif record.selection_quality_valid:
            records[index] = record.model_copy(
                update={
                    "selection_reason": (
                        "cutoff-safe source does not cover the formation window"
                    )
                }
            )

    chosen_sources: dict[tuple[Market, str], int] = {}
    for identity, indexes in eligible_by_symbol.items():
        preferred = min(
            indexes,
            key=lambda index: (
                -(records[index].selection_row_count or 0),
                records[index].path,
            ),
        )
        chosen_sources[identity] = preferred
        for index in indexes:
            if index != preferred:
                records[index] = records[index].model_copy(
                    update={
                        "selection_status": "superseded_source",
                        "selection_reason": (
                            "another source has greater pre-cutoff coverage"
                        ),
                    }
                )

    selected_symbols: dict[Market, tuple[str, ...]] = {}
    training_symbols: dict[Market, tuple[str, ...]] = {}
    held_out_symbols: dict[Market, tuple[str, ...]] = {}
    for market in markets:
        symbols = sorted(
            (
                symbol
                for candidate_market, symbol in chosen_sources
                if candidate_market == market
            ),
            key=lambda symbol: _ordering_key(ordering_salt, market, symbol),
        )
        if len(symbols) < assets_per_market:
            raise ValueError(
                f"{market} has {len(symbols)} cutoff-safe symbols; "
                f"{assets_per_market} required"
            )
        selected = tuple(symbols[:assets_per_market])
        training = selected[:-held_out_assets_per_market]
        held_out = selected[-held_out_assets_per_market:]
        selected_symbols[market] = selected
        training_symbols[market] = training
        held_out_symbols[market] = held_out
        for symbol in symbols:
            index = chosen_sources[(market, symbol)]
            if symbol in training:
                status: SelectionStatus = "training_universe"
                reason = "selected using cutoff-safe hash order for model-visible universe"
            elif symbol in held_out:
                status = "held_out_unseen"
                reason = "selected using cutoff-safe hash order for unseen-stock evaluation"
            else:
                status = "eligible_not_selected"
                reason = "pre-cutoff eligibility passed but fixed budget was filled"
            records[index] = records[index].model_copy(
                update={"selection_status": status, "selection_reason": reason}
            )

    inventory = SourceInventory(
        inventory_id="source-inventory-v2",
        protocol_id="protocol-v2",
        created_at=created_at.astimezone(UTC),
        source_root=root.as_posix(),
        mutation_policy="reject",
        ordering="sha256_market_symbol_salt",
        ordering_salt=ordering_salt,
        minimum_coverage_start=experiment_start,
        minimum_coverage_end=selection_cutoff,
        assets_per_market=assets_per_market,
        held_out_assets_per_market=held_out_assets_per_market,
        source_file_count=len(records),
        selected_symbol_count=sum(len(values) for values in selected_symbols.values()),
        quarantined_file_count=sum(
            record.selection_status == "quarantined" for record in records
        ),
        selected_symbols=selected_symbols,
        training_symbols=training_symbols,
        held_out_symbols=held_out_symbols,
        future_data_used_for_source_selection=False,
        files=tuple(records),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            inventory.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return inventory

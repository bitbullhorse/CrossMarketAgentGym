"""Build the immutable, quality-gated Phase 12 canonical dataset snapshot."""

from __future__ import annotations

import csv
import json
import shutil
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from crossmarket_agentgym.data.adapters import adapter_for
from crossmarket_agentgym.data.fx import FXRateTable
from crossmarket_agentgym.data.io import write_canonical
from crossmarket_agentgym.data.manifests import (
    build_dataset_manifest,
    sha256_file,
    verify_manifest,
    write_manifest,
)
from crossmarket_agentgym.data.quality import validate_ohlcv_frame
from crossmarket_agentgym.data.schemas import Market
from crossmarket_agentgym.experiments.models import FormalExperimentProtocol
from crossmarket_agentgym.experiments.protocol import load_protocol
from crossmarket_agentgym.experiments.source_inventory import (
    SourceFileRecord,
    SourceInventory,
    load_source_inventory,
)


class DatasetSnapshotSummary(BaseModel):
    """Structured result for the formal dataset acquisition/build gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_id: str
    output_root: str
    source_inventory_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fx_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_source_count: int = Field(ge=1)
    selected_symbol_count: int = Field(ge=1)
    ohlcv_row_count: int = Field(ge=1)
    semantic_excluded_row_count: int = Field(ge=0)
    training_symbols: dict[Market, tuple[str, ...]]
    held_out_symbols: dict[Market, tuple[str, ...]]
    quality_valid: bool
    manifest_integrity_valid: bool
    future_data_used_for_source_selection: bool
    source_rows_repaired: bool


def _validate_inventory_contract(
    protocol: FormalExperimentProtocol,
    inventory: SourceInventory,
) -> None:
    selection = protocol.dataset.selection
    expected = {
        "ordering": selection.ordering,
        "ordering_salt": selection.ordering_salt,
        "minimum_coverage_start": selection.minimum_source_coverage.start,
        "minimum_coverage_end": selection.minimum_source_coverage.end,
        "assets_per_market": selection.assets_per_market,
        "held_out_assets_per_market": selection.held_out_assets_per_market,
    }
    actual = {
        "ordering": inventory.ordering,
        "ordering_salt": inventory.ordering_salt,
        "minimum_coverage_start": inventory.minimum_coverage_start,
        "minimum_coverage_end": inventory.minimum_coverage_end,
        "assets_per_market": inventory.assets_per_market,
        "held_out_assets_per_market": inventory.held_out_assets_per_market,
    }
    if actual != expected:
        raise ValueError("source inventory selection contract differs from protocol")
    if inventory.mutation_policy != "reject" or inventory.allow_row_repair:
        raise ValueError("formal inventory must reject mutation and row repair")


def _selected_records(inventory: SourceInventory) -> tuple[SourceFileRecord, ...]:
    selected = tuple(
        record
        for record in inventory.files
        if record.selection_status in {"training_universe", "held_out_unseen"}
    )
    expected = inventory.assets_per_market * 4
    if len(selected) != expected:
        raise ValueError(f"inventory contains {len(selected)} selected sources; {expected} required")
    return selected


def _canonical_selected_frame(
    *,
    source_path: Path,
    record: SourceFileRecord,
    start: date,
    end: date,
) -> pd.DataFrame:
    if sha256_file(source_path) != record.sha256:
        raise ValueError(f"source changed after inventory: {record.path}")
    result = adapter_for(record.market).load(source_path)
    if result.errors:
        raise ValueError(f"selected source no longer loads: {record.path}: {result.errors}")
    numeric = ["open", "high", "low", "close", "volume"]
    exclusion_mask = result.frame.loc[:, numeric].isna().all(axis=1)
    observed_rows = tuple(int(index) for index in result.frame.index[exclusion_mask])
    if observed_rows != record.semantic_exclusion_rows:
        raise ValueError(f"semantic exclusion rows changed after inventory: {record.path}")
    frame = result.frame.loc[~exclusion_mask].reset_index(drop=True)
    dates = pd.to_datetime(frame["trade_date"], errors="raise").dt.date
    within = (dates >= start) & (dates <= end)
    projected = frame.loc[within].reset_index(drop=True)
    if projected.empty:
        raise ValueError(f"selected source is empty in experiment window: {record.path}")
    if record.censor_mode == "selection_window_only":
        if record.censored_after_date is None:
            raise ValueError(f"selection-window censor lacks boundary: {record.path}")
        accepted_dates = pd.to_datetime(
            projected["trade_date"], errors="raise"
        ).dt.date
        accepted = projected.loc[
            accepted_dates <= record.censored_after_date
        ].reset_index(drop=True)
        if len(accepted) != record.accepted_ohlcv_row_count:
            raise ValueError(f"selection-window censor count changed: {record.path}")
    elif record.accepted_ohlcv_row_count is None:
        accepted = projected
    else:
        accepted_count = record.accepted_ohlcv_row_count
        if accepted_count > len(projected):
            raise ValueError(f"frozen accepted prefix exceeds source rows: {record.path}")
        if record.censored_from_position is not None:
            if record.censored_from_position != accepted_count:
                raise ValueError(f"frozen censor position is inconsistent: {record.path}")
            if accepted_count >= len(projected):
                raise ValueError(f"frozen censor row is absent: {record.path}")
            observed_censor_date = pd.to_datetime(
                projected.iloc[accepted_count]["trade_date"], errors="raise"
            ).date()
            if observed_censor_date != record.censored_from_date:
                raise ValueError(f"frozen censor date changed: {record.path}")
        elif accepted_count != len(projected):
            raise ValueError(f"uncensored frozen prefix is incomplete: {record.path}")
        accepted = projected.iloc[:accepted_count].reset_index(drop=True)
    if accepted.empty:
        raise ValueError(f"accepted source prefix is empty: {record.path}")
    projected_report = validate_ohlcv_frame(accepted)
    if not projected_report.is_valid:
        raise ValueError(f"window projection fails quality gate: {record.path}")
    identities = set(
        zip(
            accepted["market"].astype(str),
            accepted["symbol"].astype(str),
            strict=True,
        )
    )
    if identities != {(record.market, record.symbol)}:
        raise ValueError(f"selected source identity changed: {record.path}")
    return accepted


def transform_ecb_snapshot(
    snapshot_path: Path,
    *,
    currencies: tuple[str, ...],
    quote_currency: str,
) -> pd.DataFrame:
    """Convert ECB currency-per-EUR observations into currency-to-USD rates."""
    raw = pd.read_csv(snapshot_path, quoting=csv.QUOTE_MINIMAL)
    required = {"CURRENCY", "CURRENCY_DENOM", "TIME_PERIOD", "OBS_VALUE"}
    if not required.issubset(raw.columns):
        raise ValueError("ECB snapshot does not contain the required EXR fields")
    filtered = raw.loc[
        raw["CURRENCY"].astype(str).isin(currencies)
        & (raw["CURRENCY_DENOM"].astype(str) == "EUR"),
        ["CURRENCY", "TIME_PERIOD", "OBS_VALUE"],
    ].copy()
    filtered["TIME_PERIOD"] = pd.to_datetime(
        filtered["TIME_PERIOD"], errors="raise"
    ).dt.date
    filtered["OBS_VALUE"] = pd.to_numeric(filtered["OBS_VALUE"], errors="raise")
    if filtered.duplicated(["CURRENCY", "TIME_PERIOD"]).any():
        raise ValueError("ECB snapshot has duplicate currency/date observations")
    usd = filtered.loc[
        filtered["CURRENCY"] == quote_currency,
        ["TIME_PERIOD", "OBS_VALUE"],
    ].rename(columns={"OBS_VALUE": "USD_PER_EUR"})
    if usd.empty:
        raise ValueError("ECB snapshot lacks the USD/EUR denominator series")
    joined = filtered.merge(usd, on="TIME_PERIOD", how="inner", validate="many_to_one")
    joined["rate"] = joined["USD_PER_EUR"] / joined["OBS_VALUE"]
    output = pd.DataFrame(
        {
            "trade_date": joined["TIME_PERIOD"],
            "base_currency": joined["CURRENCY"].astype(str),
            "quote_currency": quote_currency,
            "rate": joined["rate"].astype(float),
            "source": "European Central Bank Data Portal EXR snapshot",
        }
    ).sort_values(["base_currency", "trade_date"], ignore_index=True)
    missing = set(currencies) - set(output["base_currency"])
    if missing:
        raise ValueError(f"ECB snapshot lacks converted currencies: {sorted(missing)}")
    FXRateTable(output, quote_currency=quote_currency)
    return output


def _write_instruments(
    path: Path,
    records: tuple[SourceFileRecord, ...],
) -> None:
    roles = {
        (record.market, record.symbol): record.selection_status for record in records
    }
    rows: list[dict[str, Any]] = []
    for market, symbol in sorted(roles):
        rows.append(
            {
                "symbol": symbol,
                "market": market,
                "universe_role": roles[(market, symbol)],
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def build_dataset_snapshot(
    *,
    workspace_root: Path,
    protocol_path: Path,
) -> DatasetSnapshotSummary:
    """Build once into a sibling temporary directory and atomically publish."""
    root = workspace_root.resolve()
    protocol = load_protocol(protocol_path)
    inventory_path = root / protocol.dataset.source_inventory
    if sha256_file(inventory_path) != protocol.dataset.source_inventory_sha256:
        raise ValueError("source inventory hash does not match the protocol")
    inventory = load_source_inventory(inventory_path)
    _validate_inventory_contract(protocol, inventory)
    records = _selected_records(inventory)

    fx_snapshot = root / protocol.fx.raw_snapshot
    if sha256_file(fx_snapshot) != protocol.fx.raw_snapshot_sha256:
        raise ValueError("ECB FX snapshot hash does not match the protocol")

    output_root = root / protocol.dataset.processed_root
    if output_root.exists():
        raise FileExistsError(
            f"formal dataset is immutable; create a new protocol version: {output_root}"
        )
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}-building-", dir=output_root.parent)
    )
    file_roles: dict[Path, str] = {}
    total_rows = 0
    try:
        for record in sorted(records, key=lambda value: (value.market, value.symbol)):
            source_path = root / protocol.dataset.source_root / record.path
            frame = _canonical_selected_frame(
                source_path=source_path,
                record=record,
                start=protocol.dataset.selection.experiment_window.start,
                end=protocol.dataset.selection.experiment_window.end,
            )
            safe_symbol = record.symbol.replace("/", "_").replace("\\", "_")
            destination = (
                temporary
                / "ohlcv"
                / f"market={record.market}"
                / f"symbol={safe_symbol}.parquet"
            )
            write_canonical(frame, destination, require_valid=True)
            file_roles[destination] = "ohlcv"
            total_rows += len(frame)

        instruments_path = temporary / "instruments.csv"
        _write_instruments(instruments_path, records)
        file_roles[instruments_path] = "instruments"

        fx_path = temporary / "fx_rates.csv"
        fx_frame = transform_ecb_snapshot(
            fx_snapshot,
            currencies=protocol.fx.currencies,
            quote_currency=protocol.fx.quote_currency,
        )
        fx_frame.to_csv(fx_path, index=False)
        file_roles[fx_path] = "fx"

        manifest = build_dataset_manifest(
            root=temporary,
            dataset_name=(
                "CrossMarketAgentGym "
                f"formal_{protocol.dataset.dataset_version[-2:]}"
            ),
            file_roles=file_roles,  # type: ignore[arg-type]
            source=(
                f"source_inventory_sha256={protocol.dataset.source_inventory_sha256};"
                f"ecb_snapshot_sha256={protocol.fx.raw_snapshot_sha256}"
            ),
            adjustment_rule=protocol.dataset.corporate_action_policy,
            created_at=inventory.created_at,
        )
        if not manifest.quality.is_valid:
            raise ValueError("formal canonical snapshot failed its aggregate quality gate")
        manifest_path = temporary / "dataset_manifest.json"
        write_manifest(manifest, manifest_path)
        if (
            protocol.status == "frozen"
            and sha256_file(manifest_path)
            != protocol.dataset.processed_manifest_sha256
        ):
            raise ValueError(
                "rebuilt dataset manifest does not match the frozen protocol"
            )
        verification = verify_manifest(temporary, manifest)
        if not verification.is_valid:
            raise ValueError("formal dataset manifest failed immediate integrity verification")
        temporary.rename(output_root)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    manifest_path = root / protocol.dataset.processed_manifest
    return DatasetSnapshotSummary(
        protocol_id=protocol.protocol_id,
        output_root=output_root.relative_to(root).as_posix(),
        source_inventory_sha256=protocol.dataset.source_inventory_sha256,
        fx_snapshot_sha256=protocol.fx.raw_snapshot_sha256,
        dataset_manifest_sha256=sha256_file(manifest_path),
        selected_source_count=len(records),
        selected_symbol_count=len({(value.market, value.symbol) for value in records}),
        ohlcv_row_count=total_rows,
        semantic_excluded_row_count=sum(
            len(record.semantic_exclusion_rows) for record in records
        ),
        training_symbols=inventory.training_symbols,
        held_out_symbols=inventory.held_out_symbols,
        quality_valid=True,
        manifest_integrity_valid=True,
        future_data_used_for_source_selection=bool(
            inventory.future_data_used_for_source_selection
        ),
        source_rows_repaired=False,
    )


def write_snapshot_summary(summary: DatasetSnapshotSummary, path: Path) -> None:
    """Persist the immutable snapshot build result beside the protocol evidence."""
    if path.exists():
        raise FileExistsError(f"snapshot summary already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

"""Dataset-manifest construction, serialization, and verification."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from crossmarket_agentgym import __version__
from crossmarket_agentgym.data.io import load_canonical
from crossmarket_agentgym.data.manifests.models import (
    DatasetManifest,
    FileRole,
    ManifestFile,
    ManifestVerification,
    QualitySummary,
)
from crossmarket_agentgym.data.quality import merge_quality_reports
from crossmarket_agentgym.data.schemas import CANONICAL_COLUMNS

_HASH_CHUNK_BYTES = 1024 * 1024


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(_HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_path(root: Path, path: Path) -> str:
    """Return a POSIX relative path and reject traversal outside the dataset root."""
    return path.resolve().relative_to(root.resolve()).as_posix()


def _date_bounds(values: pd.Series[Any]) -> tuple[str | None, str | None]:
    """Return ISO date bounds for parseable values."""
    dates = pd.to_datetime(values, errors="coerce").dropna()
    if dates.empty:
        return None, None
    return dates.min().date().isoformat(), dates.max().date().isoformat()


def _read_auxiliary(path: Path) -> pd.DataFrame:
    """Read an instruments or FX artifact for row-count metadata."""
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError(f"unsupported manifest format: {path.suffix}")


def build_dataset_manifest(
    *,
    root: Path,
    dataset_name: str,
    file_roles: Mapping[Path, FileRole],
    source: str,
    adjustment_rule: str,
    created_at: datetime | None = None,
) -> DatasetManifest:
    """Build a manifest from existing files and their recomputed quality metadata."""
    manifest_files: list[ManifestFile] = []
    quality_reports = []
    all_markets: set[str] = set()
    all_symbols: set[str] = set()
    all_dates: list[pd.Series[Any]] = []
    ohlcv_rows = 0

    ordered = sorted(file_roles.items(), key=lambda item: _relative_path(root, item[0]))
    for path, role in ordered:
        relative = _relative_path(root, path)
        if role == "ohlcv":
            loaded = load_canonical(path)
            frame = loaded.frame
            quality_reports.append((relative, loaded.report))
            markets = sorted(frame["market"].dropna().astype(str).unique().tolist())
            symbols = sorted(frame["symbol"].dropna().astype(str).unique().tolist())
            date_start, date_end = _date_bounds(frame["trade_date"])
            ohlcv_rows += len(frame)
            all_markets.update(markets)
            all_symbols.update(symbols)
            all_dates.append(frame["trade_date"])
        else:
            frame = _read_auxiliary(path)
            markets = []
            symbols = []
            date_start, date_end = (
                _date_bounds(frame["trade_date"])
                if "trade_date" in frame.columns
                else (None, None)
            )
        file_format: Literal["csv", "parquet"] = (
            "parquet" if path.suffix.lower() in {".parquet", ".pq"} else "csv"
        )
        manifest_files.append(
            ManifestFile(
                path=relative,
                role=role,
                format=file_format,
                size_bytes=path.stat().st_size,
                sha256=sha256_file(path),
                row_count=len(frame),
                markets=markets,
                symbols=symbols,
                date_start=date_start,
                date_end=date_end,
            )
        )

    merged = merge_quality_reports(quality_reports)
    if all_dates:
        combined_dates = pd.concat(all_dates, ignore_index=True)
        dataset_start, dataset_end = _date_bounds(combined_dates)
    else:
        dataset_start, dataset_end = None, None
    timestamp = created_at or datetime.now(tz=UTC)
    if timestamp.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    return DatasetManifest(
        dataset_name=dataset_name,
        created_at=timestamp,
        software_version=__version__,
        source=source,
        adjustment_rule=adjustment_rule,
        row_count=ohlcv_rows,
        markets=sorted(all_markets),
        symbols=sorted(all_symbols),
        date_start=dataset_start,
        date_end=dataset_end,
        schema_columns=list(CANONICAL_COLUMNS),
        files=manifest_files,
        quality=QualitySummary(
            is_valid=merged.is_valid,
            error_count=merged.error_count,
            warning_count=merged.warning_count,
        ),
    )


def write_manifest(manifest: DatasetManifest, path: Path) -> None:
    """Write stable, human-readable UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = manifest.model_dump(mode="json")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_manifest(path: Path) -> DatasetManifest:
    """Load and validate a dataset manifest."""
    return DatasetManifest.model_validate_json(path.read_text(encoding="utf-8"))


def verify_manifest(root: Path, manifest: DatasetManifest) -> ManifestVerification:
    """Recompute sizes and hashes without changing recorded metadata."""
    missing: list[str] = []
    hash_mismatches: list[str] = []
    size_mismatches: list[str] = []
    for entry in manifest.files:
        path = root / entry.path
        try:
            resolved = path.resolve()
            resolved.relative_to(root.resolve())
        except ValueError:
            missing.append(entry.path)
            continue
        if not resolved.is_file():
            missing.append(entry.path)
            continue
        if resolved.stat().st_size != entry.size_bytes:
            size_mismatches.append(entry.path)
        if sha256_file(resolved) != entry.sha256:
            hash_mismatches.append(entry.path)
    return ManifestVerification(
        missing_files=missing,
        hash_mismatches=hash_mismatches,
        size_mismatches=size_mismatches,
    )

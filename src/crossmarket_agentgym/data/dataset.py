"""Dataset-level validation for canonical manifests and mixed legacy inputs."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from crossmarket_agentgym.data.adapters import adapter_for, discover_legacy_files
from crossmarket_agentgym.data.config import DataValidationConfig
from crossmarket_agentgym.data.io import load_canonical
from crossmarket_agentgym.data.manifests import load_manifest, verify_manifest
from crossmarket_agentgym.data.quality import (
    DataQualityReport,
    QualityIssue,
    merge_quality_reports,
    validate_ohlcv_frame,
)
from crossmarket_agentgym.data.schemas import Market


class DatasetValidationSummary(BaseModel):
    """Auditable validation status across all inspected source files."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    is_valid: bool
    root: str
    layout: str
    markets: list[str]
    files_checked: int = Field(ge=0)
    ohlcv_rows: int = Field(ge=0)
    quality: DataQualityReport
    manifest_missing: list[str] = Field(default_factory=list)
    manifest_hash_mismatches: list[str] = Field(default_factory=list)
    manifest_size_mismatches: list[str] = Field(default_factory=list)


def validate_manifest_dataset(root: Path) -> DatasetValidationSummary:
    """Validate every OHLCV artifact and recompute every manifest digest."""
    manifest = load_manifest(root / "dataset_manifest.json")
    verification = verify_manifest(root, manifest)
    reports: list[tuple[str, DataQualityReport]] = []
    files_checked = 0
    markets: set[str] = set()
    for entry in manifest.files:
        if entry.role != "ohlcv":
            continue
        loaded = load_canonical(root / entry.path)
        reports.append((entry.path, loaded.report))
        markets.update(loaded.frame["market"].dropna().astype(str).unique().tolist())
        files_checked += 1
    quality = merge_quality_reports(reports)
    is_valid = verification.is_valid and quality.is_valid and manifest.quality.is_valid
    return DatasetValidationSummary(
        is_valid=is_valid,
        root=str(root),
        layout="canonical_manifest",
        markets=sorted(markets),
        files_checked=files_checked,
        ohlcv_rows=quality.row_count,
        quality=quality,
        manifest_missing=verification.missing_files,
        manifest_hash_mismatches=verification.hash_mismatches,
        manifest_size_mismatches=verification.size_mismatches,
    )


def validate_legacy_dataset(
    root: Path,
    *,
    max_files_per_market: int | None = None,
    directory_markets: Mapping[str, Market] | None = None,
) -> DatasetValidationSummary:
    """Normalize and inspect legacy sources without editing or dropping their rows."""
    discovered = discover_legacy_files(root, directory_markets)
    reports: list[tuple[str, DataQualityReport]] = []
    markets_loaded: set[str] = set()
    files_checked = 0
    markets: tuple[Market, ...] = ("CN", "HK", "JP", "US")
    for typed_market in markets:
        market = typed_market
        paths = discovered[typed_market]
        selected = paths[:max_files_per_market] if max_files_per_market else paths
        if not selected:
            reports.append(
                (
                    f"market={market}",
                    DataQualityReport(
                        row_count=0,
                        issues=[
                            QualityIssue(
                                code="missing_market_source",
                                severity="error",
                                message=f"no supported source files found for {market}",
                                count=1,
                            )
                        ],
                    ),
                )
            )
            continue
        adapter = adapter_for(typed_market)
        for path in selected:
            relative = path.resolve().relative_to(root.resolve()).as_posix()
            result = adapter.load(path)
            files_checked += 1
            if result.errors:
                report = DataQualityReport(
                    row_count=len(result.frame),
                    issues=[
                        QualityIssue(
                            code="source_adapter_error",
                            severity="error",
                            message=message,
                            count=1,
                            file=relative,
                        )
                        for message in result.errors
                    ],
                )
            else:
                report = validate_ohlcv_frame(result.frame)
                if not result.frame.empty:
                    markets_loaded.add(typed_market)
            reports.append((relative, report))
    quality = merge_quality_reports(reports)
    return DatasetValidationSummary(
        is_valid=quality.is_valid,
        root=str(root),
        layout="legacy_mixed",
        markets=sorted(markets_loaded),
        files_checked=files_checked,
        ohlcv_rows=quality.row_count,
        quality=quality,
    )


def validate_configured_dataset(
    config: DataValidationConfig,
    *,
    max_files_per_market: int | None = None,
) -> DatasetValidationSummary:
    """Dispatch validation according to a strict data configuration."""
    dataset = config.dataset
    if dataset.layout == "canonical_manifest":
        return validate_manifest_dataset(dataset.root)
    limit = (
        max_files_per_market
        if max_files_per_market is not None
        else dataset.max_files_per_market
    )
    return validate_legacy_dataset(
        dataset.root,
        max_files_per_market=limit,
        directory_markets=dataset.markets or None,
    )

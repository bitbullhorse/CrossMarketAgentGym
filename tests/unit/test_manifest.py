"""Dataset-manifest integrity tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from crossmarket_agentgym.data.io import write_canonical
from crossmarket_agentgym.data.manifests import (
    build_dataset_manifest,
    verify_manifest,
    write_manifest,
)
from tests.unit.test_data_quality import canonical_frame


def test_manifest_hashes_can_be_recomputed(tmp_path: Path) -> None:
    """Every manifest file hash verifies against the on-disk bytes."""
    data_path = tmp_path / "market=US" / "year=2024" / "A.parquet"
    data_path.parent.mkdir(parents=True)
    write_canonical(canonical_frame(), data_path)
    manifest = build_dataset_manifest(
        root=tmp_path,
        dataset_name="fixture",
        file_roles={data_path: "ohlcv"},
        source="synthetic",
        adjustment_rule="none",
        created_at=datetime(2026, 7, 26, tzinfo=UTC),
    )
    write_manifest(manifest, tmp_path / "dataset_manifest.json")

    verification = verify_manifest(tmp_path, manifest)

    assert verification.is_valid
    assert manifest.row_count == 2
    assert manifest.markets == ["US"]


def test_manifest_detects_changed_bytes(tmp_path: Path) -> None:
    """A modified artifact is reported and never silently re-hashed."""
    data_path = tmp_path / "data.csv"
    write_canonical(canonical_frame(), data_path)
    manifest = build_dataset_manifest(
        root=tmp_path,
        dataset_name="fixture",
        file_roles={data_path: "ohlcv"},
        source="synthetic",
        adjustment_rule="none",
        created_at=datetime(2026, 7, 26, tzinfo=UTC),
    )
    data_path.write_bytes(data_path.read_bytes() + b"\n")

    verification = verify_manifest(tmp_path, manifest)

    assert not verification.is_valid
    assert verification.hash_mismatches == ["data.csv"]


def test_manifest_verification_rejects_path_traversal(tmp_path: Path) -> None:
    """A recorded path cannot escape the declared dataset root."""
    data_path = tmp_path / "data.csv"
    write_canonical(canonical_frame(), data_path)
    manifest = build_dataset_manifest(
        root=tmp_path,
        dataset_name="fixture",
        file_roles={data_path: "ohlcv"},
        source="synthetic",
        adjustment_rule="none",
        created_at=datetime(2026, 7, 26, tzinfo=UTC),
    )
    escaped_entry = manifest.files[0].model_copy(update={"path": "../escape.csv"})
    escaped_manifest = manifest.model_copy(update={"files": [escaped_entry]})

    verification = verify_manifest(tmp_path, escaped_manifest)

    assert not verification.is_valid
    assert verification.missing_files == ["../escape.csv"]

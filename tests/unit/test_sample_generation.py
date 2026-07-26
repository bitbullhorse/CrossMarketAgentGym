"""Synthetic sample generator tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from crossmarket_agentgym.data.dataset import validate_manifest_dataset
from crossmarket_agentgym.data.sample import generate_sample_dataset


def test_sample_generation_is_complete_and_hash_valid(tmp_path: Path) -> None:
    """Generation creates all semantic roles and a verifiable four-market manifest."""
    manifest = generate_sample_dataset(tmp_path)
    summary = validate_manifest_dataset(tmp_path)

    assert manifest.row_count == 20
    assert {entry.role for entry in manifest.files} == {"ohlcv", "instruments", "fx"}
    assert summary.is_valid
    assert summary.markets == ["CN", "HK", "JP", "US"]


def test_sample_generation_refuses_unrequested_overwrite(tmp_path: Path) -> None:
    """Existing binary artifacts are not overwritten without an explicit flag."""
    generate_sample_dataset(tmp_path)

    with pytest.raises(FileExistsError):
        generate_sample_dataset(tmp_path)

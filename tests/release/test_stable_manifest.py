from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from crossmarket_agentgym.release.stable_manifest import (
    BENCHMARK_ID,
    DATASET_MANIFEST_ID,
    PROTOCOL_ID,
    STABLE_TAG,
    STABLE_VERSION,
    build_stable_release_manifest,
    verify_stable_release_manifest,
    write_stable_release_manifest,
)

PROJECT_ROOT = Path(__file__).parents[2]


def test_stable_release_manifest_binds_accepted_formal_inputs() -> None:
    manifest = build_stable_release_manifest(PROJECT_ROOT)
    assert manifest["release"]["version"] == STABLE_VERSION
    assert manifest["release"]["tag"] == STABLE_TAG
    assert manifest["benchmark"]["benchmark_id"] == BENCHMARK_ID
    assert manifest["benchmark"]["run_count"] == 215
    assert (
        manifest["formal_experiment_inputs"]["dataset"]["manifest_id"]
        == DATASET_MANIFEST_ID
    )
    assert (
        manifest["formal_experiment_inputs"]["protocol"]["protocol_id"]
        == PROTOCOL_ID
    )
    assert manifest["public_sample"]["contains_formal_market_data"] is False
    valid, problems = verify_stable_release_manifest(PROJECT_ROOT)
    assert valid is True
    assert problems == ()


def test_stable_release_manifest_checksum_fails_closed(tmp_path: Path) -> None:
    target = tmp_path / "release_manifest_v1.0.0.json"
    manifest_path, checksum_path = write_stable_release_manifest(
        PROJECT_ROOT,
        output=target,
    )
    assert manifest_path == target
    assert checksum_path.is_file()
    document = json.loads(target.read_text(encoding="utf-8"))
    document["release"]["tag"] = "v0.0.0"
    target.write_text(json.dumps(document), encoding="utf-8")
    valid, problems = verify_stable_release_manifest(
        PROJECT_ROOT,
        manifest=target,
    )
    assert valid is False
    assert problems


def test_manifest_builder_rejects_mutated_benchmark_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    shutil.copytree(PROJECT_ROOT / "benchmarks", workspace / "benchmarks")
    shutil.copytree(PROJECT_ROOT / "data", workspace / "data")
    immutable = workspace / "benchmarks" / "v1" / "IMMUTABLE.json"
    immutable.chmod(0o644)
    document = json.loads(immutable.read_text(encoding="utf-8"))
    document["code_commit"] = "0" * 40
    immutable.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(
        "crossmarket_agentgym.release.stable_manifest.verify_benchmark",
        lambda _path: type(
            "Result",
            (),
            {"is_valid": True, "checks": ()},
        )(),
    )
    with pytest.raises(ValueError, match="benchmark identity mismatch"):
        build_stable_release_manifest(workspace)

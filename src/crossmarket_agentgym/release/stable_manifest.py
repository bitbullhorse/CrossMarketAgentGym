"""Build and verify the stable release-to-benchmark consistency manifest."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from crossmarket_agentgym import __version__
from crossmarket_agentgym.benchmarking.core import verify_benchmark

STABLE_VERSION = "1.0.0"
STABLE_TAG = "v1.0.0"
BENCHMARK_ID = "benchmark-v1"
DATASET_MANIFEST_ID = "dataset-manifest-v3"
PROTOCOL_ID = "protocol-v4"
FORMAL_CODE_COMMIT = "6f03d3da3ed6ecbe918c5a7f9aa35cb9abfb2b83"
DATASET_MANIFEST_SHA256 = (
    "0ed9091f1ab96d24ef5fbd41d0d080668623e954e4f15e4a277f1c217e825eb9"
)
PROTOCOL_SHA256 = "90e40d212b5faaff644e0041eeef92c0b0056ce9a834095a047948a1d5e42529"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _git_is_ancestor(root: Path, ancestor: str) -> bool | None:
    if not (root / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def build_stable_release_manifest(workspace_root: str | Path = ".") -> dict[str, Any]:
    """Return a deterministic manifest after revalidating frozen Phase 13 inputs."""
    root = Path(workspace_root).resolve()
    benchmark_root = root / "benchmarks" / "v1"
    verification = verify_benchmark(benchmark_root)
    if not verification.is_valid:
        failed = [check.name for check in verification.checks if not check.passed]
        raise ValueError(f"benchmark-v1 verification failed: {failed}")
    if __version__ != STABLE_VERSION:
        raise ValueError(
            f"package version {__version__!r} does not match stable version {STABLE_VERSION!r}"
        )

    immutable = _json(benchmark_root / "IMMUTABLE.json")
    expected_immutable = {
        "benchmark_id": BENCHMARK_ID,
        "code_commit": FORMAL_CODE_COMMIT,
        "dataset_manifest_sha256": DATASET_MANIFEST_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "filesystem_sealed": True,
        "overwrite_allowed": False,
    }
    mismatches = {
        key: {"expected": expected, "actual": immutable.get(key)}
        for key, expected in expected_immutable.items()
        if immutable.get(key) != expected
    }
    if mismatches:
        raise ValueError(f"benchmark identity mismatch: {mismatches}")

    actual_protocol_hash = _sha256(benchmark_root / "protocol.yaml")
    actual_dataset_hash = _sha256(benchmark_root / "dataset_manifest.json")
    if actual_protocol_hash != PROTOCOL_SHA256:
        raise ValueError("benchmark protocol hash does not match protocol-v4")
    if actual_dataset_hash != DATASET_MANIFEST_SHA256:
        raise ValueError("benchmark dataset manifest hash does not match dataset-manifest-v3")

    checksum_manifest = benchmark_root / "checksums.json"
    checksum_document = _json(checksum_manifest)
    checksummed_count = int(checksum_document.get("file_count", -1))
    formal_ancestor = _git_is_ancestor(root, FORMAL_CODE_COMMIT)
    if formal_ancestor is False:
        raise ValueError("formal experiment commit is not an ancestor of the release source")

    return {
        "schema_version": "1.0",
        "package": "crossmarket-agent-gym",
        "release": {
            "version": STABLE_VERSION,
            "tag": STABLE_TAG,
            "release_commit_resolution": "tag_target",
            "formal_experiment_commit_is_ancestor": formal_ancestor,
        },
        "benchmark": {
            "benchmark_id": BENCHMARK_ID,
            "path": "benchmarks/v1",
            "checksums_file": "benchmarks/v1/checksums.json",
            "checksums_sha256": _sha256(checksum_manifest),
            "checksummed_file_count": checksummed_count,
            "run_count": int(immutable["run_count"]),
            "formal_code_commit": FORMAL_CODE_COMMIT,
        },
        "formal_experiment_inputs": {
            "dataset": {
                "manifest_id": DATASET_MANIFEST_ID,
                "release_file": "benchmarks/v1/dataset_manifest.json",
                "sha256": DATASET_MANIFEST_SHA256,
            },
            "protocol": {
                "protocol_id": PROTOCOL_ID,
                "release_file": "benchmarks/v1/protocol.yaml",
                "sha256": PROTOCOL_SHA256,
            },
        },
        "public_sample": {
            "manifest": "data/sample/dataset_manifest.json",
            "checkpoint": "data/sample/checkpoints/equal_weight_policy.json",
            "checkpoint_sha256": _sha256(
                root / "data" / "sample" / "checkpoints" / "equal_weight_policy.json"
            ),
            "contains_formal_market_data": False,
        },
        "publication": {
            "pypi": {
                "identifier": "crossmarket-agent-gym==1.0.0",
                "status": "pending_publication",
            },
            "container": {
                "identifier": "ghcr.io/bitbullhorse/crossmarket-agent-gym:1.0.0",
                "status": "pending_publication",
            },
            "documentation": {
                "aliases": ["v1.0.0", "stable", "latest"],
                "status": "pending_publication",
            },
            "doi": {
                "identifier": None,
                "status": "pending_reservation",
            },
        },
        "data_policy": {
            "license_statement": "DATA_LICENSE.md",
            "formal_raw_data_redistributed": False,
            "restricted_paths_excluded": [
                "stock_data",
                "data/processed",
                "runs",
                "reports",
                "results",
            ],
        },
    }


def write_stable_release_manifest(
    workspace_root: str | Path = ".",
    *,
    output: str | Path = "release/release_manifest_v1.0.0.json",
) -> tuple[Path, Path]:
    """Write the deterministic stable manifest and adjacent checksum."""
    root = Path(workspace_root).resolve()
    target = Path(output)
    if not target.is_absolute():
        target = root / target
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        build_stable_release_manifest(root),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )
    target.write_text(text + "\n", encoding="utf-8", newline="\n")
    checksum_path = target.with_suffix(".sha256")
    checksum_path.write_text(
        f"{_sha256(target)}  {target.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    return target, checksum_path


def verify_stable_release_manifest(
    workspace_root: str | Path = ".",
    *,
    manifest: str | Path = "release/release_manifest_v1.0.0.json",
) -> tuple[bool, tuple[str, ...]]:
    """Compare checked-in stable release evidence with a fresh deterministic build."""
    root = Path(workspace_root).resolve()
    path = Path(manifest)
    if not path.is_absolute():
        path = root / path
    problems: list[str] = []
    if not path.is_file():
        return False, (f"missing stable release manifest: {path}",)
    try:
        actual = _json(path)
        expected = build_stable_release_manifest(root)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        return False, (str(error),)
    if actual != expected:
        problems.append("stable release manifest differs from frozen release inputs")
    checksum_path = path.with_suffix(".sha256")
    if not checksum_path.is_file():
        problems.append(f"missing checksum file: {checksum_path}")
    else:
        declared = checksum_path.read_text(encoding="utf-8").split(maxsplit=1)[0]
        if declared != _sha256(path):
            problems.append("stable release manifest checksum mismatch")
    return not problems, tuple(problems)

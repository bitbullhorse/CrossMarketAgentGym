"""Create and finalize protocol-v2 while preserving frozen protocol-v1."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from crossmarket_agentgym.data.manifests import sha256_file
from crossmarket_agentgym.experiments.models import FormalExperimentProtocol

_ZERO_SHA256 = "0" * 64


def _load_mapping(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"protocol root must be a mapping: {path}")
    return raw


def _write_new(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to replace versioned protocol: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _draft(args: argparse.Namespace) -> None:
    source = _load_mapping(args.base_protocol)
    if source.get("protocol_id") != "protocol-v1" or source.get("status") != "frozen":
        raise ValueError("protocol-v2 must be derived from frozen protocol-v1")
    if args.source_inventory.name != "source_inventory_v2.json":
        raise ValueError("protocol-v2 requires a versioned v2 source inventory")
    payload = deepcopy(source)
    payload["protocol_id"] = "protocol-v2"
    payload["supersedes_protocol"] = "protocol-v1"
    payload["status"] = "draft"
    dataset = payload["dataset"]
    dataset.update(
        {
            "dataset_version": "dataset-manifest-v2",
            "source_inventory": args.source_inventory.as_posix(),
            "source_inventory_sha256": sha256_file(args.source_inventory),
            "processed_root": "data/processed/formal_v2",
            "processed_manifest": "data/processed/formal_v2/dataset_manifest.json",
            "processed_manifest_sha256": _ZERO_SHA256,
            "source_mutation_policy": (
                "reject_invalid_observation_and_censor_all_later_observations"
            ),
        }
    )
    selection = dataset["selection"]
    selection.update(
        {
            "ordering_salt": "CrossMarketAgentGym-protocol-v2",
            "minimum_source_coverage": {
                "start": "2021-01-04",
                "end": "2021-02-01",
            },
            "universe_formation_date": "2021-02-01",
            "selection_information_cutoff": "2021-02-01",
            "post_cutoff_quality_policy": (
                "retain_symbol_censor_from_first_invalid_observation"
            ),
        }
    )
    payload["partitions"]["train"]["start"] = "2021-02-02"
    for fold in payload["partitions"]["walk_forward"]:
        fold["train"]["start"] = "2021-02-02"
    FormalExperimentProtocol.model_validate(payload)
    _write_new(args.output, payload)


def _finalize(args: argparse.Namespace) -> None:
    if args.checksum.exists():
        raise FileExistsError("protocol-v2 already has a checksum and is immutable")
    payload = _load_mapping(args.output)
    protocol = FormalExperimentProtocol.model_validate(payload)
    if protocol.protocol_id != "protocol-v2" or protocol.status != "draft":
        raise ValueError("only an unfrozen protocol-v2 draft may be finalized")
    expected_manifest = Path(payload["dataset"]["processed_manifest"])
    if expected_manifest != args.processed_manifest:
        raise ValueError("processed manifest path differs from protocol-v2 draft")
    payload["dataset"]["processed_manifest_sha256"] = sha256_file(
        args.processed_manifest
    )
    payload["status"] = "frozen"
    FormalExperimentProtocol.model_validate(payload)
    temporary = args.output.with_suffix(".yaml.finalizing")
    if temporary.exists():
        raise FileExistsError(f"stale finalization file exists: {temporary}")
    temporary.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    temporary.replace(args.output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("draft", "finalize"))
    parser.add_argument(
        "--base-protocol",
        type=Path,
        default=Path("experiments/protocol_v1.yaml"),
    )
    parser.add_argument(
        "--source-inventory",
        type=Path,
        default=Path("experiments/data/source_inventory_v2.json"),
    )
    parser.add_argument(
        "--processed-manifest",
        type=Path,
        default=Path("data/processed/formal_v2/dataset_manifest.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiments/protocol_v2.yaml"),
    )
    parser.add_argument(
        "--checksum",
        type=Path,
        default=Path("experiments/protocol_v2.sha256"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.stage == "draft":
        _draft(args)
    else:
        _finalize(args)


if __name__ == "__main__":
    main()

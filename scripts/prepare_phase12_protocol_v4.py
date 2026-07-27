"""Create and finalize protocol-v4 with corrected global-censor semantics."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from crossmarket_agentgym.data.manifests import sha256_file
from crossmarket_agentgym.experiments.models import FormalExperimentProtocol

_ZERO_SHA256 = "0" * 64


def _mapping(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"protocol root must be a mapping: {path}")
    return raw


def _draft(args: argparse.Namespace) -> None:
    if args.output.exists() or args.checksum.exists():
        raise FileExistsError("protocol-v4 is versioned and cannot be replaced")
    source = _mapping(args.base_protocol)
    if source.get("protocol_id") != "protocol-v3" or source.get("status") != "frozen":
        raise ValueError("protocol-v4 must derive from frozen protocol-v3")
    payload = deepcopy(source)
    payload["protocol_id"] = "protocol-v4"
    payload["supersedes_protocol"] = "protocol-v3"
    payload["status"] = "draft"
    payload["dataset"].update(
        {
            "dataset_version": "dataset-manifest-v3",
            "source_inventory": args.source_inventory.as_posix(),
            "source_inventory_sha256": sha256_file(args.source_inventory),
            "processed_root": "data/processed/formal_v3",
            "processed_manifest": "data/processed/formal_v3/dataset_manifest.json",
            "processed_manifest_sha256": _ZERO_SHA256,
        }
    )
    FormalExperimentProtocol.model_validate(payload)
    args.output.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _finalize(args: argparse.Namespace) -> None:
    if args.checksum.exists():
        raise FileExistsError("protocol-v4 already has a checksum and is immutable")
    payload = _mapping(args.output)
    protocol = FormalExperimentProtocol.model_validate(payload)
    if protocol.protocol_id != "protocol-v4" or protocol.status != "draft":
        raise ValueError("only an unfrozen protocol-v4 draft may be finalized")
    expected = Path(payload["dataset"]["processed_manifest"])
    if expected != args.processed_manifest:
        raise ValueError("processed manifest path differs from protocol-v4 draft")
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
        default=Path("experiments/protocol_v3.yaml"),
    )
    parser.add_argument(
        "--source-inventory",
        type=Path,
        default=Path("experiments/data/source_inventory_v3.json"),
    )
    parser.add_argument(
        "--processed-manifest",
        type=Path,
        default=Path("data/processed/formal_v3/dataset_manifest.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiments/protocol_v4.yaml"),
    )
    parser.add_argument(
        "--checksum",
        type=Path,
        default=Path("experiments/protocol_v4.sha256"),
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

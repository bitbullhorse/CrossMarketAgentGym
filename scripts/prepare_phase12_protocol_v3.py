"""Create frozen protocol-v3 with a verifiable Prompt source binding."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from crossmarket_agentgym.data.manifests import sha256_file
from crossmarket_agentgym.experiments.models import FormalExperimentProtocol


def _mapping(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"protocol root must be a mapping: {path}")
    return raw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-protocol",
        type=Path,
        default=Path("experiments/protocol_v2.yaml"),
    )
    parser.add_argument(
        "--prompt-source",
        type=Path,
        default=Path("experiments/agents/prompt_bundle_v1.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiments/protocol_v3.yaml"),
    )
    parser.add_argument(
        "--checksum",
        type=Path,
        default=Path("experiments/protocol_v3.sha256"),
    )
    args = parser.parse_args()
    if args.output.exists() or args.checksum.exists():
        raise FileExistsError("protocol-v3 is versioned and cannot be replaced")
    source = _mapping(args.base_protocol)
    if source.get("protocol_id") != "protocol-v2" or source.get("status") != "frozen":
        raise ValueError("protocol-v3 must derive from frozen protocol-v2")
    payload = deepcopy(source)
    payload["protocol_id"] = "protocol-v3"
    payload["supersedes_protocol"] = "protocol-v2"
    payload["agents"]["prompt_source"] = args.prompt_source.as_posix()
    payload["agents"]["prompt_source_sha256"] = sha256_file(args.prompt_source)
    protocol = FormalExperimentProtocol.model_validate(payload)
    if protocol.status != "frozen":
        raise ValueError("protocol-v3 must be frozen at creation")
    args.output.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

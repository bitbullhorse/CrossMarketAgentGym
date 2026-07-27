"""Freeze or verify the immutable Phase 12 protocol."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from crossmarket_agentgym.experiments.protocol import (
    freeze_protocol,
    verify_protocol,
)


def parse_args() -> argparse.Namespace:
    """Parse explicit freeze/verify mode."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("experiments/protocol_v4.yaml"),
    )
    parser.add_argument(
        "--checksum",
        type=Path,
        default=Path("experiments/protocol_v4.sha256"),
    )
    parser.add_argument("--workspace-root", type=Path, default=Path("."))
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Freeze once or report all readiness blockers."""
    args = parse_args()
    if args.write:
        digest = freeze_protocol(args.protocol, args.checksum)
        print(json.dumps({"protocol_sha256": digest, "frozen": True}, indent=2))
        return
    result = verify_protocol(
        args.protocol,
        args.checksum,
        workspace_root=args.workspace_root,
    )
    print(result.model_dump_json(indent=2))
    if not result.is_ready_to_execute:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

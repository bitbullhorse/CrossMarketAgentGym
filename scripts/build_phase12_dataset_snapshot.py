"""Build and verify an immutable Phase 12 canonical dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from crossmarket_agentgym.experiments.dataset_snapshot import (
    build_dataset_snapshot,
    write_snapshot_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("experiments/protocol_v4.yaml"),
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("experiments/data/dataset_snapshot_v3.json"),
    )
    args = parser.parse_args()
    root = args.workspace_root.resolve()
    protocol = args.protocol if args.protocol.is_absolute() else root / args.protocol
    summary_path = args.summary if args.summary.is_absolute() else root / args.summary
    result = build_dataset_snapshot(workspace_root=root, protocol_path=protocol)
    write_snapshot_summary(result, summary_path)
    print(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

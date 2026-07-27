"""Run one immutable Phase 12 task by run ID."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from crossmarket_agentgym.experiments.runner import execute_formal_task


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--protocol", type=Path, default=Path("experiments/protocol_v4.yaml"))
    parser.add_argument(
        "--protocol-checksum",
        type=Path,
        default=Path("experiments/protocol_v4.sha256"),
    )
    parser.add_argument(
        "--matrix",
        type=Path,
        default=Path("experiments/run_matrix_v5.json"),
    )
    parser.add_argument(
        "--matrix-checksum",
        type=Path,
        default=Path("experiments/run_matrix_v5.sha256"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("results/formal/protocol-v4-matrix-v5"),
    )
    args = parser.parse_args()
    root = args.workspace_root.resolve()

    def resolved(path: Path) -> Path:
        return path if path.is_absolute() else root / path

    record = execute_formal_task(
        workspace_root=root,
        run_id=args.run_id,
        protocol_path=resolved(args.protocol),
        protocol_checksum_path=resolved(args.protocol_checksum),
        matrix_path=resolved(args.matrix),
        matrix_checksum_path=resolved(args.matrix_checksum),
        output_root=resolved(args.output_root),
    )
    print(json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

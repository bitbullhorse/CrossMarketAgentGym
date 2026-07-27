"""Freeze the Phase 12 Groups A–F run matrix after the driver commit exists."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from crossmarket_agentgym.experiments.matrix import freeze_run_matrix


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--protocol", type=Path, default=Path("experiments/protocol_v4.yaml"))
    parser.add_argument(
        "--protocol-checksum",
        type=Path,
        default=Path("experiments/protocol_v4.sha256"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiments/run_matrix_v4.json"),
    )
    parser.add_argument(
        "--checksum",
        type=Path,
        default=Path("experiments/run_matrix_v4.sha256"),
    )
    args = parser.parse_args()
    root = args.workspace_root.resolve()

    def resolved(path: Path) -> Path:
        return path if path.is_absolute() else root / path

    matrix = freeze_run_matrix(
        workspace_root=root,
        protocol_path=resolved(args.protocol),
        protocol_checksum_path=resolved(args.protocol_checksum),
        output_path=resolved(args.output),
        checksum_path=resolved(args.checksum),
    )
    counts = {
        group: sum(task.group == group for task in matrix.tasks)
        for group in ("A", "B", "C", "D", "E", "F")
    }
    print(
        json.dumps(
            {
                "matrix_id": matrix.matrix_id,
                "code_commit": matrix.code_commit,
                "task_count": len(matrix.tasks),
                "tasks_by_group": counts,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

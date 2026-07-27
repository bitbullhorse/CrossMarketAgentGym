"""Run or enumerate one Phase 12 group from the frozen matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from crossmarket_agentgym.experiments.audit import FormalRunRecord
from crossmarket_agentgym.experiments.matrix import load_run_matrix
from crossmarket_agentgym.experiments.runner import execute_formal_task


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", choices=list("ABCDEF"), required=True)
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("experiments/protocol_v4.yaml"),
    )
    parser.add_argument(
        "--protocol-checksum",
        type=Path,
        default=Path("experiments/protocol_v4.sha256"),
    )
    parser.add_argument(
        "--matrix",
        type=Path,
        default=Path("experiments/run_matrix_v6.json"),
    )
    parser.add_argument(
        "--matrix-checksum",
        type=Path,
        default=Path("experiments/run_matrix_v6.sha256"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("results/formal/protocol-v4-matrix-v6"),
    )
    parser.add_argument("--method")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--skip-completed", action="store_true")
    args = parser.parse_args()
    root = args.workspace_root.resolve()

    def resolved(path: Path) -> Path:
        return path if path.is_absolute() else root / path

    matrix_path = resolved(args.matrix)
    checksum_path = resolved(args.matrix_checksum)
    output_root = resolved(args.output_root)
    matrix = load_run_matrix(matrix_path)
    tasks = [
        task
        for task in matrix.tasks
        if task.group == args.group
        and (args.method is None or task.method == args.method)
        and (args.seed is None or task.seed == args.seed)
    ]
    if args.list_only:
        for task in tasks:
            print(task.run_id)
        return 0
    failures: list[str] = []
    for task in tasks:
        record_path = output_root / task.run_id / "formal_run.json"
        if args.skip_completed and record_path.is_file():
            record = FormalRunRecord.model_validate_json(
                record_path.read_text(encoding="utf-8")
            )
            if record.status == "completed":
                continue
        try:
            execute_formal_task(
                workspace_root=root,
                run_id=task.run_id,
                protocol_path=resolved(args.protocol),
                protocol_checksum_path=resolved(args.protocol_checksum),
                matrix_path=matrix_path,
                matrix_checksum_path=checksum_path,
                output_root=output_root,
            )
        except BaseException:
            failures.append(task.run_id)
    print(
        json.dumps(
            {
                "group": args.group,
                "selected": len(tasks),
                "failed": failures,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

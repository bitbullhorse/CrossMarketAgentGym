"""Generate Phase 12 tables, figures, tests, and exit-gate status."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from crossmarket_agentgym.experiments.aggregation import generate_phase12_summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--matrix",
        type=Path,
        default=Path("experiments/run_matrix_v4.json"),
    )
    parser.add_argument(
        "--matrix-checksum",
        type=Path,
        default=Path("experiments/run_matrix_v4.sha256"),
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=Path("results/formal/protocol-v4"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/formal/protocol-v4/summary"),
    )
    parser.add_argument(
        "--independent-review",
        type=Path,
        default=Path("experiments/review/phase12_independent_review.md"),
    )
    args = parser.parse_args()
    root = args.workspace_root.resolve()

    def resolved(path: Path) -> Path:
        return path if path.is_absolute() else root / path

    payload = generate_phase12_summary(
        matrix_path=resolved(args.matrix),
        matrix_checksum_path=resolved(args.matrix_checksum),
        results_root=resolved(args.results_root),
        output_dir=resolved(args.output_dir),
        independent_review_path=resolved(args.independent_review),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["phase12_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Execute and gate one isolated Phase 11 CPU training replay."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from crossmarket_agentgym.audit.run_manifest import verify_run_manifest
from crossmarket_agentgym.release.reproduction import (
    execute_training_replay,
    load_reproduction_tolerance_config,
)

_CPU_ACCEPTED_LEVELS = frozenset(
    {
        "bitwise_reproduced",
        "numerically_reproduced",
    }
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Retrain one source run without test/network/account access and compare "
            "the isolated replay."
        )
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--workspace-root", type=Path, default=Path("."))
    parser.add_argument("--runs-root", type=Path, default=Path("runs"))
    parser.add_argument(
        "--tolerance-config",
        type=Path,
        default=Path("configs/reproduction/phase11_cpu.yaml"),
    )
    parser.add_argument("--replay-run-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = execute_training_replay(
        args.workspace_root,
        args.runs_root,
        args.run_id,
        tolerance=load_reproduction_tolerance_config(args.tolerance_config),
        replay_run_id=args.replay_run_id,
    )
    print(report.model_dump_json(indent=2))
    if report.replay_relative_path is not None:
        replay_dir = args.workspace_root.resolve() / report.replay_relative_path
        verify_run_manifest(replay_dir)
    cpu_gate_passed = (
        report.is_valid
        and report.computational_replay_executed
        and report.reproduction_level in _CPU_ACCEPTED_LEVELS
        and report.test_partition_accessed_by_replay is False
        and report.network_used is False
        and report.account_state_mutated is False
    )
    return 0 if cpu_gate_passed else 1


if __name__ == "__main__":
    sys.exit(main())

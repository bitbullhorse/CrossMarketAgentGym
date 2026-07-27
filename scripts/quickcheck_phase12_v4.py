"""Run a non-formal CPU/accounting quickcheck without reading test metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from crossmarket_agentgym.environments import MarketDataPanel
from crossmarket_agentgym.environments.checks import (
    EnvironmentCheckConfig,
    run_environment_checks,
)
from crossmarket_agentgym.environments.observations import ObservationConfig
from crossmarket_agentgym.experiments.environment_validation import (
    _VALIDATORS,
    run_environment_validation,
)
from crossmarket_agentgym.experiments.protocol import load_protocol, verify_protocol
from crossmarket_agentgym.experiments.strategy_runs import (
    environment_config,
    formal_train_config,
)
from crossmarket_agentgym.experiments.training import (
    formal_train_start_signal_index,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("runs/phase12-v4-cpu-quickcheck/summary.json"),
    )
    args = parser.parse_args()
    root = args.workspace_root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    protocol_path = root / "experiments" / "protocol_v4.yaml"
    checksum_path = root / "experiments" / "protocol_v4.sha256"
    protocol = load_protocol(protocol_path)
    verification = verify_protocol(
        protocol_path,
        checksum_path,
        workspace_root=root,
    )
    if not verification.is_ready_to_execute:
        raise RuntimeError(f"protocol input gate failed: {verification.blockers}")
    environment = run_environment_checks(
        EnvironmentCheckConfig(
            dataset_root=root / protocol.dataset.processed_root,
            seed=protocol.compute.seeds[0],
            smoke_steps=64,
            observation=ObservationConfig(
                market_window_layout=protocol.drl.observation_layout
            ),
            environment=environment_config(protocol),
        )
    )
    hand_cases = tuple(
        run_environment_validation(method)
        for method in sorted(_VALIDATORS)
    )
    train_config = formal_train_config(
        protocol,
        workspace_root=root,
        run_name="phase12_v4_quickcheck_context",
        output_dir=output.parent,
        algorithm="PPO",
        seed=protocol.compute.seeds[0],
        total_timesteps=1,
    )
    panel = MarketDataPanel.from_manifest(
        root / protocol.dataset.processed_root,
        base_currency=protocol.execution.base_currency,
    )
    start_signal = formal_train_start_signal_index(
        panel,
        train_start=protocol.partitions.train.start,
        lookback=train_config.environment.lookback,
    )
    if start_signal + 1 >= panel.session_count:
        raise RuntimeError("formal training start signal is absent or out of range")
    first_training_execution_date = panel.dates[start_signal + 1]
    training_start_valid = (
        first_training_execution_date >= protocol.partitions.train.start
        and panel.dates[start_signal] < protocol.partitions.train.start
    )
    max_hand_error = max(case.absolute_error for case in hand_cases)
    passed = (
        environment.is_valid
        and environment.max_accounting_error
        <= protocol.execution.accounting_tolerance
        and all(case.passed for case in hand_cases)
        and max_hand_error <= protocol.execution.accounting_tolerance
        and training_start_valid
    )
    payload = {
        "formal": False,
        "development_results_eligible_for_formal_use": False,
        "protocol_id": protocol.protocol_id,
        "protocol_sha256": verification.protocol_sha256,
        "test_metrics_accessed": False,
        "hpo_executed": False,
        "passed": passed,
        "environment": environment.model_dump(mode="json"),
        "hand_computable_cases": [
            case.model_dump(mode="json") for case in hand_cases
        ],
        "max_hand_computable_error": max_hand_error,
        "training_start_boundary": {
            "start_signal_date": panel.dates[start_signal].isoformat(),
            "first_execution_date": first_training_execution_date.isoformat(),
            "protocol_train_start": protocol.partitions.train.start.isoformat(),
            "passed": training_start_valid,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

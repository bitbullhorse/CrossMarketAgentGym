from __future__ import annotations

import json
from pathlib import Path


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, allow_nan=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_training_run(
    workspace: Path,
    run_id: str,
    *,
    algorithm: str = "PPO",
    seed: int = 1,
    mean_return: float = 0.03,
    values: tuple[float, ...] = (101.0, 100.0, 103.0),
) -> Path:
    run_dir = workspace / "runs" / run_id
    write_json(
        run_dir / "run_summary.json",
        {
            "run_id": run_id,
            "algorithm": algorithm,
            "requested_timesteps": 10,
            "trained_timesteps": 12,
            "validation_metrics": {"mean_return": mean_return},
            "private_token": "must-not-be-indexed",
        },
    )
    write_json(
        run_dir / "training_artifact.json",
        {"algorithm": algorithm, "seed": seed},
    )
    write_json(
        run_dir / "resolved_config.json",
        {"environment": {"initial_cash": 100.0}},
    )
    write_json(
        run_dir / "validation" / "metrics.json",
        {
            "algorithm": algorithm,
            "partition": "validation",
            "metrics": {
                "mean_return": mean_return,
                "max_drawdown": 0.02,
                "mean_turnover": 0.1,
                "total_cost": 2.0,
            },
        },
    )
    write_json(
        run_dir / "validation" / "weights.json",
        [
            {
                "episode": 0,
                "step": index,
                "portfolio_value": value,
            }
            for index, value in enumerate(values, start=1)
        ],
    )
    (run_dir / "resources.jsonl").write_text(
        '{"timesteps": 4, "wall_seconds": 0.5}\n'
        '{"timesteps": 12, "wall_seconds": 1.25}\n',
        encoding="utf-8",
    )
    return run_dir


def write_phase7_run(workspace: Path, run_id: str = "phase7-fixture") -> Path:
    run_dir = workspace / "runs" / run_id
    write_json(
        run_dir / "phase7_summary.json",
        {
            "run_id": run_id,
            "preset": "full_stack",
            "provider_runtimes_started": 3,
            "network_used": False,
            "directive_replay_verified": True,
            "research": {
                "team": {
                    "configured_instances": 1,
                    "succeeded": 1,
                    "fallback": 0,
                }
            },
            "risk": {
                "team": {
                    "configured_instances": 3,
                    "succeeded": 3,
                    "fallback": 0,
                }
            },
            "hierarchical": {
                "team": {
                    "configured_instances": 1,
                    "succeeded": 1,
                    "fallback": 0,
                }
            },
            "fusion": {
                "constraints": {
                    "cash_floor": 0.5,
                    "max_asset_weight": 0.15,
                    "max_turnover": 0.2,
                    "risk_budget": 0.5,
                    "allow_new_positions": False,
                }
            },
        },
    )
    return run_dir


def write_agent_run(workspace: Path, run_id: str = "agent-fixture") -> Path:
    run_dir = workspace / "runs" / run_id
    write_json(
        run_dir / "agent" / "team_summary.json",
        {
            "run_id": run_id,
            "topology": "committee_vote",
            "configured_instances": 3,
            "succeeded": 2,
            "fallback": 1,
            "network_used": False,
            "aggregate": {"status": "resolved"},
        },
    )
    return run_dir


def write_tuning_run(workspace: Path, run_id: str = "tuning-fixture") -> Path:
    run_dir = workspace / "runs" / "tuning" / run_id
    write_json(
        run_dir / "tuning_summary.json",
        {
            "study_name": run_id,
            "trial_count": 4,
            "completed_count": 4,
            "failed_count": 0,
            "best_trial_id": 2,
            "test_set_accessed": False,
        },
    )
    write_json(
        run_dir / "study_report.json",
        {
            "best_trial": {
                "metrics": {"validation_median_sharpe": 0.4},
                "objectives": [0.3],
            },
            "test_metrics_present": False,
        },
    )
    return run_dir


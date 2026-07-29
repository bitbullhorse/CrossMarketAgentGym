from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from crossmarket_agentgym.benchmarking.core import (
    build_benchmark,
    export_paper_artifacts,
    verify_benchmark,
)
from crossmarket_agentgym.cli.app import app


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _json(path: Path, value: Any) -> None:
    _write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _source_package(
    tmp_path: Path,
    *,
    leak: bool = False,
    visual: bool = False,
) -> tuple[Path, Path]:
    source = tmp_path / "review"
    protocol = {
        "schema_version": "1.0",
        "protocol_id": "protocol-v4",
        "status": "frozen",
        "partitions": {
            "train": {"start": "2020-01-01", "end": "2020-12-31"},
            "validation": {"start": "2021-01-01", "end": "2021-06-30"},
            "test": {"start": "2021-07-01", "end": "2021-12-31"},
        },
        "compute": {"seeds": [7]},
    }
    protocol_path = tmp_path / "protocol_v4.yaml"
    text = yaml.safe_dump(protocol, sort_keys=True)
    _write(protocol_path, text)
    _write(source / "inputs/experiments/protocol_v4.yaml", text)
    protocol_hash = _sha256(protocol_path)
    dataset = {
        "schema_version": "1.0.0",
        "date_start": "2020-01-01",
        "date_end": "2021-12-31",
        "markets": ["US"],
        "symbols": ["AAA"],
        "row_count": 500,
        "files": [
            {
                "path": "ohlcv/AAA.parquet",
                "role": "ohlcv",
                "markets": ["US"],
                "symbols": ["AAA"],
                "row_count": 500,
            }
        ],
    }
    dataset_path = (
        source / "inputs/data/processed/formal_v3/dataset_manifest.json"
    )
    _json(dataset_path, dataset)
    dataset_hash = _sha256(dataset_path)
    commit = "1" * 40
    tasks = [
        {
            "run_id": "fixture-E-research_only-s7",
            "group": "E",
            "method": "research_only",
            "required_metrics": ["tool_call_accuracy"],
            "seed": 7,
            "protocol_id": "protocol-v4",
            "protocol_sha256": protocol_hash,
            "dataset_manifest_sha256": dataset_hash,
            "code_commit": commit,
            "formal": True,
            "development_input_run_ids": [],
            "allowed_selection_partitions": ["train", "validation"],
            "test_access": "locked_final_once",
            "objective_seeds": [7],
            "walk_forward_folds": [],
        },
        {
            "run_id": "fixture-F-random-s7",
            "group": "F",
            "method": "random",
            "required_metrics": ["validation_score"],
            "seed": 7,
            "protocol_id": "protocol-v4",
            "protocol_sha256": protocol_hash,
            "dataset_manifest_sha256": dataset_hash,
            "code_commit": commit,
            "formal": True,
            "development_input_run_ids": [],
            "allowed_selection_partitions": ["train", "validation"],
            "test_access": "locked_final_once",
            "objective_seeds": [7],
            "walk_forward_folds": ["fold_01"],
        },
    ]
    if visual:
        tasks.append(
            {
                "run_id": "p12v4m6-B-ppo-s1024",
                "group": "B",
                "method": "PPO",
                "required_metrics": ["mean_return"],
                "seed": 1024,
                "protocol_id": "protocol-v4",
                "protocol_sha256": protocol_hash,
                "dataset_manifest_sha256": dataset_hash,
                "code_commit": commit,
                "formal": True,
                "development_input_run_ids": [],
                "allowed_selection_partitions": ["train", "validation"],
                "test_access": "locked_final_once",
                "objective_seeds": [1024],
                "walk_forward_folds": [],
            }
        )
    matrix = {
        "schema_version": "1.0",
        "matrix_id": "fixture-matrix-v6",
        "protocol_id": "protocol-v4",
        "protocol_sha256": protocol_hash,
        "dataset_manifest_sha256": dataset_hash,
        "code_commit": commit,
        "tasks": tasks,
    }
    _json(source / "inputs/experiments/run_matrix_v6.json", matrix)
    for task in tasks:
        run_root = source / "runs" / task["run_id"]
        result = {
            "method": task["method"],
            "seed": 7,
            "runtime_seconds": 1.5,
        }
        if task["group"] == "F":
            result.update(
                {
                    "convergence": [
                        {
                            "trial_id": 0,
                            "objectives": [0.5],
                            "status": "completed",
                        }
                    ],
                    "test_partition_visible_during_search": leak,
                    "test_evaluation_count": 1,
                    "scheduler_role": "resource_only",
                    "trial_budget": 1,
                }
            )
            _json(
                run_root / "study_report.json",
                {
                    "partition_policy": "train_and_validation_only",
                    "test_metrics_present": leak,
                    "trials": [],
                },
            )
        else:
            _write(
                run_root / "stack/research/agent/replay.jsonl",
                '{"request_hash":"a","response_hash":"b"}\n',
            )
        _json(run_root / "result.json", result)
        artifact_rows = [
            {
                "path": "configuration_lock.json",
                "sha256": "2" * 64,
                "size_bytes": 10,
            },
            {
                "path": "model/test/trades.json",
                "sha256": "3" * 64,
                "size_bytes": 100,
            },
            {
                "path": "model/test/weights.json",
                "sha256": "4" * 64,
                "size_bytes": 200,
            },
            {
                "path": "result.json",
                "sha256": _sha256(run_root / "result.json"),
                "size_bytes": (run_root / "result.json").stat().st_size,
            },
        ]
        if task["run_id"] == "p12v4m6-B-ppo-s1024":
            visual_root = tmp_path / "visual" / task["run_id"]
            visual_files = {
                "model/training/training_metrics.jsonl": (
                    '{"mean_reward":0.1,"portfolio_values":[101.0],"timesteps":10}\n'
                    '{"mean_reward":0.2,"portfolio_values":[103.0],"timesteps":20}\n'
                ),
                "model/training/test/trades.json": "[]\n",
                "model/training/test/weights.json": json.dumps(
                    [
                        {
                            "execution_date": "2021-07-01",
                            "realized": [0.6, 0.4],
                            "portfolio_value": 100.0,
                            "drawdown": 0.0,
                        },
                        {
                            "execution_date": "2021-07-02",
                            "realized": [0.5, 0.5],
                            "portfolio_value": 102.0,
                            "drawdown": 0.01,
                        },
                    ]
                )
                + "\n",
            }
            artifact_rows = artifact_rows[:1]
            for relative, content in visual_files.items():
                path = visual_root / relative
                _write(path, content)
                artifact_rows.append(
                    {
                        "path": relative,
                        "sha256": _sha256(path),
                        "size_bytes": path.stat().st_size,
                    }
                )
            artifact_rows.append(
                {
                    "path": "result.json",
                    "sha256": _sha256(run_root / "result.json"),
                    "size_bytes": (run_root / "result.json").stat().st_size,
                }
            )
        _json(
            run_root / "formal_run.json",
            {
                "schema_version": "1.0",
                "task": task,
                "status": "completed",
                "failure_reason": None,
                "wall_time_seconds": 1.5,
                "test_partition_access_count": 1,
                "development_result_accessed": False,
                "artifacts": artifact_rows,
            },
        )
    summary = source / "evidence/summary"
    metric_rows = [
        {
            "run_id": task["run_id"],
            "group": task["group"],
            "method": task["method"],
            "seed": 7,
            "metric": "validation_score",
            "value": 0.5,
            "protocol_sha256": protocol_hash,
            "dataset_manifest_sha256": dataset_hash,
            "code_commit": commit,
        }
        for task in tasks
    ]
    descriptive_rows = [
        {
            "group": task["group"],
            "method": task["method"],
            "metric": "validation_score",
            "n": 1,
            "mean": 0.5,
            "std": 0.0,
            "median": 0.5,
            "ci95_low": 0.5,
            "ci95_high": 0.5,
            "best": 0.5,
            "worst": 0.5,
        }
        for task in tasks
    ]
    _csv(summary / "run_metrics.csv", metric_rows)
    _csv(summary / "descriptive_statistics.csv", descriptive_rows)
    _json(summary / "phase12_summary.json", {"completed_run_count": 2})
    _json(summary / "additional_safety_audit.json", {"passed": True})
    _json(summary / "statistical_output_audit.json", {"passed": True})
    _csv(
        summary / "paired_tests.csv",
        [
            {
                "group": "F",
                "metric": "validation_score",
                "reference": "default",
                "method": "random",
                "n": 1,
                "statistic": 0,
                "p_value": 1,
                "rank_biserial": 0,
                "holm_adjusted_p": 1,
            }
        ],
    )
    _write(summary / "paired_tests.md", "# Paired tests\n")
    checksums = {
        path.relative_to(source).as_posix(): _sha256(path)
        for path in source.rglob("*")
        if path.is_file() and path.name != "checksums.json"
    }
    _json(
        source / "checksums.json",
        {"file_count": len(checksums), "files": checksums},
    )
    return source, protocol_path


def test_build_verify_export_and_no_overwrite(tmp_path: Path) -> None:
    source, protocol = _source_package(tmp_path)
    benchmark = tmp_path / "benchmarks/v1"
    result = build_benchmark(
        protocol,
        source_root=source,
        output=benchmark,
        seal=False,
    )
    assert result.is_valid
    assert result.run_count == 2
    assert (benchmark / "tables/strategy_comparison.tex").is_file()
    assert len(list((benchmark / "figures").glob("*.svg"))) == 10
    assert "payload_in_benchmark" in (
        benchmark / "trades/artifact_index.csv"
    ).read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        build_benchmark(protocol, source_root=source, output=benchmark)
    export = export_paper_artifacts(
        benchmark,
        "tables",
        output=tmp_path / "paper-tables",
    )
    assert export.is_valid
    assert export.file_count >= 37


def test_hash_tampering_is_detected(tmp_path: Path) -> None:
    source, protocol = _source_package(tmp_path)
    benchmark = tmp_path / "benchmark"
    build_benchmark(protocol, source_root=source, output=benchmark, seal=False)
    with (benchmark / "tables/hpo_comparison.csv").open(
        "a", encoding="utf-8"
    ) as stream:
        stream.write("tampered\n")
    result = verify_benchmark(benchmark)
    assert not result.is_valid
    assert not next(
        check for check in result.checks if check.name == "file_hashes"
    ).passed


def test_hpo_test_visibility_blocks_build(tmp_path: Path) -> None:
    source, protocol = _source_package(tmp_path, leak=True)
    with pytest.raises(ValueError, match="hpo_test_isolation"):
        build_benchmark(
            protocol,
            source_root=source,
            output=tmp_path / "benchmark",
            seal=False,
        )
    assert not (tmp_path / "benchmark").exists()


def test_phase13_cli_surface() -> None:
    runner = CliRunner()
    root_help = runner.invoke(app, ["--help"])
    assert root_help.exit_code == 0
    assert "benchmark" in root_help.stdout
    assert "paper" in root_help.stdout
    benchmark_help = runner.invoke(app, ["benchmark", "--help"])
    assert benchmark_help.exit_code == 0
    assert "build" in benchmark_help.stdout
    assert "verify" in benchmark_help.stdout
    paper_help = runner.invoke(app, ["paper", "--help"])
    assert paper_help.exit_code == 0
    assert "export-tables" in paper_help.stdout
    assert "export-figures" in paper_help.stdout


def test_hash_verified_visual_payload_build_and_tamper_rejection(
    tmp_path: Path,
) -> None:
    source, protocol = _source_package(tmp_path, visual=True)
    visual = tmp_path / "visual"
    benchmark = tmp_path / "benchmark-visual"
    result = build_benchmark(
        protocol,
        source_root=source,
        visual_payload_root=visual,
        output=benchmark,
        seal=False,
    )
    assert result.is_valid
    assert result.run_count == 3
    assert len(
        list(
            csv.DictReader(
                (benchmark / "figures/training_curve.data.csv").open(
                    encoding="utf-8"
                )
            )
        )
    ) == 2
    market_rows = list(
        csv.DictReader(
            (benchmark / "figures/market_exposure.data.csv").open(
                encoding="utf-8"
            )
        )
    )
    assert market_rows[0]["market"] == "US"
    assert float(market_rows[0]["mean_realized_weight"]) == pytest.approx(0.45)
    assert next(
        check
        for check in result.checks
        if check.name == "representative_visual_payload"
    ).passed

    tampered = (
        visual
        / "p12v4m6-B-ppo-s1024"
        / "model/training/test/weights.json"
    )
    _write(tampered, "[]\n")
    with pytest.raises(ValueError, match="visual payload hash mismatch"):
        build_benchmark(
            protocol,
            source_root=source,
            visual_payload_root=visual,
            output=tmp_path / "tampered-benchmark",
            seal=False,
        )

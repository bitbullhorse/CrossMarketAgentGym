"""Formal result collection, statistics, reporting, and task dispatch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from crossmarket_agentgym.experiments.aggregation import (
    _independent_review_blockers,
    _missing_required_metrics,
    _result_metrics,
    collect_formal_results,
    generate_phase12_summary,
    paired_tests,
    summarize_metrics,
)
from crossmarket_agentgym.experiments.audit import FormalRunAudit
from crossmarket_agentgym.experiments.matrix import build_run_matrix
from crossmarket_agentgym.experiments.protocol import sha256_file
from crossmarket_agentgym.experiments.runner import (
    _test_access_count,
    execute_formal_task,
)


@pytest.mark.parametrize(
    ("group", "result", "metric"),
    [
        ("A", {"passed": True, "absolute_error": 0.0}, "passed"),
        (
            "B",
            {"test_metrics": {"mean_return": 0.1}, "runtime_seconds": 1.0},
            "mean_return",
        ),
        (
            "C",
            {"subruns": {"x": {"test_metrics": {"sharpe": 1.0}}}},
            "sharpe",
        ),
        (
            "D",
            {
                "base_metrics": {"mean_return": 0.1},
                "variant_metrics": {"mean_return": 0.2},
                "runtime_seconds": 1.0,
            },
            "delta_mean_return",
        ),
        (
            "E",
            {
                "portfolio_metrics": {"sharpe": 1.0},
                "task_success_rate": 1.0,
                "config_validity_rate": 1.0,
                "tool_call_accuracy": 1.0,
                "leakage_violation_rate": 0.0,
                "risk_directive_validity_rate": 1.0,
                "conflict_resolution_rate": 1.0,
                "report_completeness_rate": 1.0,
                "additional_runtime_seconds": 1.0,
            },
            "task_success_rate",
        ),
        (
            "F",
            {
                "validation_score": 1.0,
                "locked_test_score": 0.9,
                "runtime_seconds": 1.0,
                "stability": 0.1,
                "tuning_overfit_gap": 0.1,
            },
            "locked_test_score",
        ),
    ],
)
def test_result_metric_normalization(
    group: str,
    result: dict[str, Any],
    metric: str,
) -> None:
    assert metric in _result_metrics(group, result)


def test_required_metric_gate_checks_nested_group_results() -> None:
    assert _missing_required_metrics(
        "B",
        ("mean_return", "runtime_seconds"),
        {"test_metrics": {"mean_return": 0.1}, "runtime_seconds": 1.0},
    ) == ()
    assert _missing_required_metrics(
        "C",
        ("mean_return", "sharpe"),
        {"subruns": {"US": {"test_metrics": {"mean_return": 0.1}}}},
    ) == ("sharpe",)


def test_independent_review_gate_requires_identity_hashes_and_clearance(
    formal_sample: tuple[Path, object],
    tmp_path: Path,
) -> None:
    _, protocol = formal_sample
    matrix = build_run_matrix(
        protocol,
        protocol_sha256="a" * 64,
        code_commit="b" * 40,
    )
    review = tmp_path / "review.md"
    checks = "\n".join(f"- [x] check {index}" for index in range(10))
    review.write_text(
        "\n".join(
            [
                "- Reviewer identity: Independent Reviewer",
                "- Affiliation or independent role: external",
                "- Review date: 2026-07-27",
                f"- Protocol SHA-256: {matrix.protocol_sha256}",
                (
                    "- Dataset Manifest SHA-256: "
                    f"{matrix.dataset_manifest_sha256}"
                ),
                f"- Run-matrix SHA-256: {'c' * 64}",
                f"- Code commit: {matrix.code_commit}",
                checks,
                "P0: 0",
                "P1: 0",
                "Decision: `approved`",
            ]
        ),
        encoding="utf-8",
    )
    assert _independent_review_blockers(
        review,
        matrix=matrix,
        matrix_sha256="c" * 64,
    ) == []


@pytest.mark.parametrize(
    ("group", "result", "expected"),
    [
        ("A", {}, 0),
        ("B", {"test_evaluation_count": 1}, 1),
        (
            "C",
            {
                "subruns": {
                    "CN": {"test_evaluation_count": 1},
                    "US": {"test_evaluation_count": 1},
                }
            },
            2,
        ),
        ("D", {"test_evaluation_count_per_arm": 1}, 2),
        ("E", {"test_evaluation_count": 1}, 1),
        ("F", {"test_evaluation_count": 1}, 1),
    ],
)
def test_formal_test_access_count_is_explicit(
    group: str,
    result: dict[str, Any],
    expected: int,
) -> None:
    assert _test_access_count(group, result) == expected


def _statistics_frame() -> pd.DataFrame:
    rows = []
    for group, reference, comparison in (
        ("B", "cash", "PPO"),
        ("E", "no_llm", "risk_only"),
        ("F", "default", "random"),
    ):
        for seed in (1, 2, 3, 4, 5):
            for method, offset in ((reference, 0.0), (comparison, 0.1)):
                rows.append(
                    {
                        "run_id": f"{group}-{method}-{seed}",
                        "group": group,
                        "method": method,
                        "seed": seed,
                        "metric": "mean_return",
                        "value": seed / 100.0 + offset,
                    }
                )
    return pd.DataFrame(rows)


def test_descriptive_and_paired_statistics() -> None:
    frame = _statistics_frame()
    summary = summarize_metrics(frame)
    assert set(
        ["mean", "std", "median", "ci95_low", "ci95_high", "best", "worst"]
    ).issubset(summary.columns)
    assert summary["n"].eq(5).all()
    tests = paired_tests(frame)
    assert len(tests) == 3
    assert tests["holm_adjusted_p"].between(0.0, 1.0).all()
    assert tests["rank_biserial"].eq(1.0).all()


def _write_matrix(
    tmp_path: Path,
    protocol: Any,
) -> tuple[Any, Path, Path]:
    matrix = build_run_matrix(
        protocol,
        protocol_sha256="a" * 64,
        code_commit="b" * 40,
    )
    path = tmp_path / "matrix.json"
    path.write_text(matrix.model_dump_json(indent=2), encoding="utf-8")
    checksum = tmp_path / "matrix.sha256"
    checksum.write_text(f"{sha256_file(path)}  {path.name}\n", encoding="utf-8")
    return matrix, path, checksum


def test_collection_summary_and_runner_dispatch(
    formal_sample: tuple[Path, object],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, protocol = formal_sample
    matrix, matrix_path, matrix_checksum = _write_matrix(tmp_path, protocol)
    results = tmp_path / "results"
    task = next(task for task in matrix.tasks if task.group == "A")
    audit = FormalRunAudit(task, results)
    audit.start()
    validation = {
        "method": task.method,
        "passed": True,
        "expected": {},
        "observed": {},
        "absolute_error": 0.0,
        "accounting_tolerance": 1e-8,
    }
    (audit.run_dir / "result.json").write_text(
        json.dumps(validation),
        encoding="utf-8",
    )
    audit.complete()
    raw, blockers = collect_formal_results(matrix=matrix, results_root=results)
    assert task.run_id in set(raw["run_id"])
    assert any(value.startswith("MISSING_RUN") for value in blockers)

    payload = generate_phase12_summary(
        matrix_path=matrix_path,
        matrix_checksum_path=matrix_checksum,
        results_root=results,
        output_dir=tmp_path / "summary",
        independent_review_path=tmp_path / "missing-review.md",
    )
    assert payload["phase12_complete"] is False
    assert "INDEPENDENT_REVIEW_MISSING" in payload["blockers"]
    assert (tmp_path / "summary" / "phase12_summary.md").is_file()

    fresh_results = tmp_path / "fresh"
    monkeypatch.setattr(
        "crossmarket_agentgym.experiments.runner._preflight",
        lambda **kwargs: None,
    )
    record = execute_formal_task(
        workspace_root=workspace,
        run_id=task.run_id,
        protocol_path=Path("experiments/protocol_v4.yaml"),
        protocol_checksum_path=Path("experiments/protocol_v4.sha256"),
        matrix_path=matrix_path,
        matrix_checksum_path=matrix_checksum,
        output_root=fresh_results,
    )
    assert record.status == "completed"
    assert record.test_partition_accessed is False
    assert record.test_partition_access_count == 0
    assert (fresh_results / task.run_id / "result.json").is_file()

    c_task = next(task for task in matrix.tasks if task.group == "C")
    monkeypatch.setattr(
        "crossmarket_agentgym.experiments.runner.run_group_c",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("formal failure")),
    )
    with pytest.raises(RuntimeError, match="formal failure"):
        execute_formal_task(
            workspace_root=workspace,
            run_id=c_task.run_id,
            protocol_path=Path("experiments/protocol_v4.yaml"),
            protocol_checksum_path=Path("experiments/protocol_v4.sha256"),
            matrix_path=matrix_path,
            matrix_checksum_path=matrix_checksum,
            output_root=fresh_results,
        )
    failed = json.loads(
        (fresh_results / c_task.run_id / "formal_run.json").read_text(encoding="utf-8")
    )
    assert failed["status"] == "failed"

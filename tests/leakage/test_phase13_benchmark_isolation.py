from __future__ import annotations

import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = PROJECT_ROOT / "benchmarks" / "v1"


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_frozen_hpo_never_reads_test_during_search() -> None:
    rows = _rows(BENCHMARK / "tuning_logs" / "hpo_audit.csv")
    assert len(rows) == 40
    assert {row["partition_policy"] for row in rows} == {
        "train_and_validation_only"
    }
    assert {row["test_metrics_present_during_search"] for row in rows} == {
        "False"
    }
    assert {row["test_partition_visible_during_search"] for row in rows} == {
        "False"
    }
    assert {row["test_evaluation_count"] for row in rows} == {"1"}
    assert {row["scheduler_role"] for row in rows} == {"resource_only"}


def test_benchmark_contains_formal_results_only() -> None:
    rows = _rows(BENCHMARK / "runs.csv")
    assert len(rows) == 215
    assert {row["formal"] for row in rows} == {"True"}
    assert {row["development_result_accessed"] for row in rows} == {"False"}

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from crossmarket_agentgym.reporting.indexer import build_run_index
from crossmarket_agentgym.reporting.io import read_bounded_json, resolve_inside
from crossmarket_agentgym.reporting.models import (
    ExperimentDeclaration,
    SoftwareXReportConfig,
)
from tests.reporting.helpers import (
    write_agent_run,
    write_phase7_run,
    write_training_run,
    write_tuning_run,
)


def _experiments() -> tuple[ExperimentDeclaration, ...]:
    categories = (
        "environment_correctness",
        "algorithm_benchmark",
        "cross_stock_zero_shot",
        "leave_one_market_out",
        "market_mechanism_ablation",
        "agent_hpo_ablation",
    )
    return tuple(
        ExperimentDeclaration(
            category=category,  # type: ignore[arg-type]
            label=category,
            status="planned",
        )
        for category in categories
    )


def test_report_config_requires_all_six_unique_categories() -> None:
    config = SoftwareXReportConfig(
        experiments=_experiments(),
        include_run_ids=("one", "two"),
    )
    assert len(config.experiments) == 6
    with pytest.raises(ValidationError, match="all six"):
        SoftwareXReportConfig(experiments=_experiments()[:-1])
    with pytest.raises(ValidationError, match="requires evidence"):
        ExperimentDeclaration(
            category="environment_correctness",
            label="done",
            status="completed",
        )


def test_bounded_json_and_path_helpers_fail_closed(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"value": NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        read_bounded_json(invalid, max_bytes=100)
    with pytest.raises(ValueError, match="exceeds"):
        read_bounded_json(invalid, max_bytes=2)
    with pytest.raises(PermissionError):
        resolve_inside("../outside", tmp_path)


def test_indexer_classifies_whitelisted_artifacts_without_raw_secrets(
    tmp_path: Path,
) -> None:
    write_training_run(tmp_path, "train-one")
    write_phase7_run(tmp_path)
    write_agent_run(tmp_path)
    write_tuning_run(tmp_path)
    index = build_run_index(tmp_path, "runs")

    assert [(item.kind, item.run_id) for item in index.runs] == [
        ("agent", "agent-fixture"),
        ("phase7", "phase7-fixture"),
        ("training", "train-one"),
        ("tuning", "tuning-fixture"),
    ]
    serialized = index.model_dump_json()
    assert "must-not-be-indexed" not in serialized
    training = next(item for item in index.runs if item.kind == "training")
    assert training.metrics["validation"]["mean_return"] == 0.03
    assert training.attributes["runtime_seconds"] == 1.25
    assert len(index.fingerprint) == 64


def test_index_selection_preserves_requested_order_and_rejects_missing(
    tmp_path: Path,
) -> None:
    write_training_run(tmp_path, "first")
    write_phase7_run(tmp_path, "second")
    index = build_run_index(
        tmp_path,
        "runs",
        include_run_ids=("second", "first"),
    )
    assert [item.run_id for item in index.runs] == ["second", "first"]
    with pytest.raises(FileNotFoundError, match="missing"):
        build_run_index(tmp_path, "runs", include_run_ids=("unknown",))


def test_index_rejects_duplicate_run_identity(tmp_path: Path) -> None:
    write_training_run(tmp_path, "duplicate")
    run_dir = write_tuning_run(tmp_path, "study-dir")
    summary = json.loads((run_dir / "tuning_summary.json").read_text(encoding="utf-8"))
    summary["study_name"] = "duplicate"
    (run_dir / "tuning_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        build_run_index(tmp_path, "runs")


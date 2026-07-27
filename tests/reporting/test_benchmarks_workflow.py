from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from crossmarket_agentgym.cli.app import app
from crossmarket_agentgym.reporting.benchmarks import build_benchmark_comparison
from crossmarket_agentgym.reporting.indexer import build_run_index
from crossmarket_agentgym.reporting.models import (
    ExperimentDeclaration,
    ReportManifest,
    SoftwareXReportConfig,
)
from crossmarket_agentgym.reporting.workflow import build_softwarex_report
from tests.reporting.helpers import (
    write_agent_run,
    write_json,
    write_phase7_run,
    write_training_run,
    write_tuning_run,
)


def _report_config(workspace: Path) -> SoftwareXReportConfig:
    evidence = workspace / "evidence.json"
    write_json(evidence, {"status": "passed"})
    categories = (
        "environment_correctness",
        "algorithm_benchmark",
        "cross_stock_zero_shot",
        "leave_one_market_out",
        "market_mechanism_ablation",
        "agent_hpo_ablation",
    )
    return SoftwareXReportConfig(
        report_id="fixture-report",
        workspace_root=workspace,
        runs_root=Path("runs"),
        output_dir=Path("reports"),
        include_run_ids=(
            "ppo-seed-1",
            "ppo-seed-2",
            "agent-fixture",
            "phase7-fixture",
            "tuning-fixture",
        ),
        experiments=tuple(
            ExperimentDeclaration(
                category=category,  # type: ignore[arg-type]
                label=category,
                status="completed",
                evidence_paths=("evidence.json",),
            )
            for category in categories
        ),
    )


def _workspace(tmp_path: Path) -> SoftwareXReportConfig:
    write_training_run(
        tmp_path,
        "ppo-seed-1",
        seed=1,
        mean_return=0.03,
        values=(101.0, 100.0, 103.0),
    )
    write_training_run(
        tmp_path,
        "ppo-seed-2",
        seed=2,
        mean_return=0.05,
        values=(102.0, 101.0, 105.0),
    )
    write_agent_run(tmp_path)
    write_phase7_run(tmp_path)
    write_tuning_run(tmp_path)
    return _report_config(tmp_path)


def test_benchmark_derives_risk_metrics_and_cross_seed_variance(
    tmp_path: Path,
) -> None:
    _workspace(tmp_path)
    index = build_run_index(tmp_path, "runs")
    comparison = build_benchmark_comparison(index, tmp_path)

    assert comparison.selection_authority is False
    assert len(comparison.rows) == 2
    assert all(row.sharpe is not None for row in comparison.rows)
    assert all(row.cvar_95 is not None for row in comparison.rows)
    assert all(row.calmar is not None for row in comparison.rows)
    assert all(row.cross_seed_variance is not None for row in comparison.rows)
    assert comparison.rows[0].runtime_seconds == 0.5


def test_workflow_generates_reproducible_tables_figures_and_browser(
    tmp_path: Path,
) -> None:
    config = _workspace(tmp_path)
    first = build_softwarex_report(config)
    manifest_path = Path(first.manifest)
    first_manifest_hash = manifest_path.read_bytes()
    second = build_softwarex_report(config)

    assert first.model_dump() == second.model_dump()
    assert manifest_path.read_bytes() == first_manifest_hash
    report_dir = Path(first.report_dir)
    manifest = ReportManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    assert first.run_count == 5
    assert first.benchmark_rows == 2
    assert first.figure_count == 4
    assert len(manifest.artifacts) == 13
    assert (report_dir / "tables" / "benchmark_comparison.csv").exists()
    assert (report_dir / "figures" / "benchmark_return.svg").read_text(
        encoding="utf-8"
    ).startswith("<svg")
    html = (report_dir / "report.html").read_text(encoding="utf-8")
    assert "selection authority" in html
    assert "must-not-be-indexed" not in html
    assert "<script" not in html
    data = json.loads((report_dir / "report_data.json").read_text(encoding="utf-8"))
    assert data["selection_authority"] is False


def test_workflow_rejects_report_output_inside_runs(tmp_path: Path) -> None:
    config = _workspace(tmp_path).model_copy(update={"output_dir": Path("runs/reports")})
    with pytest.raises(ValueError, match="cannot be inside"):
        build_softwarex_report(config)


def test_phase8_cli_builds_report_from_config(tmp_path: Path) -> None:
    config = _workspace(tmp_path)
    config_path = tmp_path / "report.yaml"
    config_path.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app,
        ["report", "softwarex", "--config", str(config_path)],
    )
    assert result.exit_code == 0
    assert '"figure_count": 4' in result.stdout

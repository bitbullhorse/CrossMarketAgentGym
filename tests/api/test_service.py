from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from crossmarket_agentgym.api import ServiceConfig, create_app
from crossmarket_agentgym.reporting.workflow import build_softwarex_report
from tests.reporting.helpers import write_training_run
from tests.reporting.test_benchmarks_workflow import _report_config

TestClient = pytest.importorskip("fastapi.testclient").TestClient


def test_service_config_requires_remote_opt_in() -> None:
    with pytest.raises(ValidationError, match="allow_remote"):
        ServiceConfig(host="0.0.0.0")
    assert ServiceConfig(host="0.0.0.0", allow_remote=True).allow_remote


def test_read_only_service_lists_runs_reports_and_safe_assets(
    tmp_path: Path,
) -> None:
    write_training_run(tmp_path, "served-run")
    config = _report_config(tmp_path).model_copy(
        update={"include_run_ids": ("served-run",)}
    )
    build_softwarex_report(config)
    client = TestClient(
        create_app(
            ServiceConfig(
                workspace_root=tmp_path,
                runs_root=Path("runs"),
                reports_root=Path("reports"),
            )
        )
    )

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["read_only"] is True
    assert health.headers["x-content-type-options"] == "nosniff"
    listing = client.get("/api/runs")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert "must-not-be-indexed" not in listing.text
    detail = client.get("/api/runs/served-run")
    assert detail.status_code == 200
    assert detail.json()["kind"] == "training"
    assert client.get("/api/runs/unknown").status_code == 404

    reports = client.get("/api/reports")
    assert reports.status_code == 200
    assert reports.json()["reports"][0]["report_id"] == "fixture-report"
    assert reports.json()["reports"][0]["url"] == "/reports/fixture-report/"
    redirect = client.get("/reports/fixture-report", follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"] == "/reports/fixture-report/"
    page = client.get("/reports/fixture-report")
    assert page.status_code == 200
    assert str(page.url).endswith("/reports/fixture-report/")
    assert "selection authority" in page.text
    svg = client.get(
        "/reports/fixture-report/figures/benchmark_return.svg"
    )
    assert svg.status_code == 200
    assert svg.headers["content-type"].startswith("image/svg+xml")
    assert client.get("/reports/fixture-report/unknown.zip").status_code == 404

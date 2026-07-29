from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from crossmarket_agentgym.api import ServiceConfig, create_app
from crossmarket_agentgym.api.config import GUIServiceConfig
from crossmarket_agentgym.api.jobs import (
    ConfigValidationRequest,
    JobManager,
    JobRequest,
    list_configurations,
    read_configuration,
    validate_configuration,
)
from crossmarket_agentgym.rl.workflow import _evaluate_saved_run

TestClient = pytest.importorskip("fastapi.testclient").TestClient
PROJECT_ROOT = Path(__file__).parents[2]


def _write_data_config(workspace: Path) -> Path:
    target = workspace / "configs" / "data" / "sample.yaml"
    target.parent.mkdir(parents=True)
    target.write_text(
        "\n".join(
            [
                "dataset:",
                "  root: data/sample",
                "  layout: canonical_manifest",
                "  mutation_policy: reject",
                "  max_files_per_market: null",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def test_execution_service_is_loopback_only_and_cors_is_exact() -> None:
    with pytest.raises(ValidationError, match="loopback"):
        ServiceConfig(
            host="0.0.0.0",
            allow_remote=False,
        )
    with pytest.raises(ValidationError, match="loopback"):
        GUIServiceConfig(
            host="0.0.0.0",
            allow_remote=True,
        )
    with pytest.raises(ValidationError, match="credential-free"):
        GUIServiceConfig(
            cors_origins=("http://user:password@localhost:3000",)
        )
    assert GUIServiceConfig(
        cors_origins=("http://localhost:3000",),
    ).execution_enabled


def test_config_catalog_content_validation_and_secret_rejection(
    tmp_path: Path,
) -> None:
    path = _write_data_config(tmp_path)
    entries = list_configurations(tmp_path, kind="data_validate")
    assert [entry.path for entry in entries] == ["configs/data/sample.yaml"]
    content = read_configuration(
        tmp_path,
        kind="data_validate",
        config_path="configs/data/sample.yaml",
    )
    assert content.content == path.read_text(encoding="utf-8")
    assert len(content.sha256) == 64

    result = validate_configuration(
        tmp_path,
        ConfigValidationRequest(
            kind="data_validate",
            config_path="configs/data/sample.yaml",
            config_yaml=content.content,
        ),
    )
    assert result.valid
    assert result.safety_checks["strict_schema"]

    rejected = validate_configuration(
        tmp_path,
        ConfigValidationRequest(
            kind="data_validate",
            config_path="configs/data/sample.yaml",
            config_yaml=f"{content.content}password: do-not-store\n",
        ),
    )
    assert not rejected.valid
    assert "credentials are forbidden" in rejected.errors[0]

    escaped = validate_configuration(
        tmp_path,
        ConfigValidationRequest(
            kind="data_validate",
            config_path="configs/data/sample.yaml",
            config_yaml="\n".join(
                [
                    "dataset:",
                    "  root: ../outside",
                    "  layout: canonical_manifest",
                ]
            ),
        ),
    )
    assert not escaped.valid

    with pytest.raises((OSError, ValueError)):
        read_configuration(
            tmp_path,
            kind="data_validate",
            config_path="../outside.yaml",
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"kind": "train"}, "requires config_path"),
        (
            {
                "kind": "backtest",
                "run_id": "saved-run",
                "partition": "test",
            },
            "explicit acknowledgement",
        ),
        (
            {
                "kind": "formal_experiment",
                "formal_group": "A",
            },
            "frozen-protocol acknowledgement",
        ),
        (
            {
                "kind": "tune",
                "config_path": "configs/tune/sample.yaml",
                "acknowledge_locked_test": True,
            },
            "locked-test acknowledgement",
        ),
    ],
)
def test_job_request_rejects_unsafe_or_incomplete_shapes(
    payload: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        JobRequest.model_validate(payload)


def test_job_manager_materializes_and_queues_allowlisted_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_data_config(tmp_path)
    manager = JobManager(tmp_path)
    monkeypatch.setattr(manager._pool, "submit", lambda *args, **kwargs: None)
    record = manager.submit(
        JobRequest(
            kind="data_validate",
            config_path="configs/data/sample.yaml",
        )
    )
    assert record.status == "queued"
    assert record.command[:3] == (
        record.command[0],
        "-m",
        "crossmarket_agentgym",
    )
    assert record.command[3:5] == ("data", "validate")
    assert record.config_path is not None
    assert (tmp_path / record.config_path).is_file()
    assert manager.get(record.job_id).job_id == record.job_id
    assert manager.log_tail(record.job_id) == ""
    assert manager.cancel(record.job_id).status == "cancelled"
    manager.shutdown()


def test_all_shipped_gui_templates_pass_current_runtime_models() -> None:
    entries = list_configurations(PROJECT_ROOT)
    assert {entry.kind for entry in entries} == {
        "data_validate",
        "environment_check",
        "train",
        "agent",
        "tune",
        "report",
    }
    assert all("provider_" not in entry.path for entry in entries)
    assert all("service.yaml" not in entry.path for entry in entries)
    for entry in entries:
        result = validate_configuration(
            PROJECT_ROOT,
            ConfigValidationRequest(
                kind=entry.kind,
                config_path=entry.path,
            ),
        )
        assert result.valid, (entry.path, result.errors)


def test_job_manager_builds_every_allowlisted_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = JobManager(tmp_path)
    config_kinds = (
        "data_validate",
        "environment_check",
        "train",
        "agent",
        "tune",
        "report",
    )
    commands = {
        kind: manager._build_command(
            JobRequest(kind=kind, config_path=f"configs/{kind}/sample.yaml"),
            job_id="gui-command-test",
            materialized_config="logs/gui/config.yaml",
        )
        for kind in config_kinds
    }
    assert commands["data_validate"][3:5] == ("data", "validate")
    assert commands["environment_check"][3:5] == ("env", "check")
    assert commands["train"][3] == "train"
    assert commands["agent"][3:5] == ("agent", "run")
    assert commands["tune"][3] == "tune"
    assert commands["report"][3:5] == ("report", "softwarex")

    validation = manager._build_command(
        JobRequest(kind="backtest", run_id="source-run"),
        job_id="gui-command-test",
        materialized_config=None,
    )
    assert "crossmarket_agentgym.api.job_worker" in validation
    locked_test = manager._build_command(
        JobRequest(
            kind="backtest",
            run_id="source-run",
            partition="test",
            acknowledge_locked_test=True,
        ),
        job_id="gui-command-test",
        materialized_config=None,
    )
    assert locked_test[3:] == ("evaluate", "--run-id", "source-run")
    verify = manager._build_command(
        JobRequest(kind="reproduce", run_id="source-run"),
        job_id="gui-command-test",
        materialized_config=None,
    )
    assert verify[-1] == "--verify-only"
    replay = manager._build_command(
        JobRequest(
            kind="reproduce",
            run_id="source-run",
            reproduce_mode="execute_compare",
        ),
        job_id="gui-command-test",
        materialized_config=None,
    )
    assert replay[-2:] == ("--execute", "--compare")

    monkeypatch.setattr(manager, "_validate_formal_gate", lambda request: None)
    formal = manager._build_command(
        JobRequest(
            kind="formal_experiment",
            formal_group="F",
            formal_method="random",
            formal_seed=42,
            acknowledge_frozen_protocol=True,
        ),
        job_id="gui-command-test",
        materialized_config=None,
    )
    assert formal[-4:] == ("--method", "random", "--seed", "42")
    manager.shutdown()


def test_formal_gate_requires_commit_and_frozen_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    matrix = tmp_path / "experiments" / "run_matrix_v6.json"
    matrix.parent.mkdir(parents=True)
    matrix.write_text(
        json.dumps(
            {
                "code_commit": "a" * 40,
                "tasks": [{"group": "A", "method": "accounting", "seed": 7}],
            }
        ),
        encoding="utf-8",
    )
    manager = JobManager(tmp_path)
    request = JobRequest(
        kind="formal_experiment",
        formal_group="A",
        formal_method="accounting",
        formal_seed=7,
        acknowledge_frozen_protocol=True,
    )
    monkeypatch.setenv("CMAG_CODE_COMMIT", "a" * 40)
    manager._validate_formal_gate(request)
    monkeypatch.setenv("CMAG_CODE_COMMIT", "b" * 40)
    with pytest.raises(ValueError, match="does not match"):
        manager._validate_formal_gate(request)
    monkeypatch.setenv("CMAG_CODE_COMMIT", "a" * 40)
    with pytest.raises(ValueError, match="matches no frozen task"):
        manager._validate_formal_gate(
            request.model_copy(update={"formal_method": "missing"})
        )
    manager.shutdown()


def test_job_manager_executes_success_and_failure_in_isolated_processes(
    tmp_path: Path,
) -> None:
    _write_data_config(tmp_path)
    shutil.copytree(PROJECT_ROOT / "data" / "sample", tmp_path / "data" / "sample")
    manager = JobManager(tmp_path, max_concurrent_jobs=1)
    success = manager.submit(
        JobRequest(
            kind="data_validate",
            config_path="configs/data/sample.yaml",
        )
    )

    def wait(job_id: str) -> str:
        for _ in range(200):
            status = manager.get(job_id).status
            if status in {"completed", "failed", "cancelled"}:
                return status
            time.sleep(0.05)
        raise AssertionError(f"job did not terminate: {job_id}")

    assert wait(success.job_id) == "completed"
    assert '"is_valid": true' in manager.log_tail(success.job_id)
    failure = manager.submit(
        JobRequest(kind="reproduce", run_id="missing-run")
    )
    assert wait(failure.job_id) == "failed"
    assert manager.get(failure.job_id).return_code not in {None, 0}
    manager.shutdown()


def test_control_api_is_opt_in_and_exposes_job_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_data_config(tmp_path)
    read_only_client = TestClient(
        create_app(ServiceConfig(workspace_root=tmp_path))
    )
    assert read_only_client.get("/health").json()["execution_enabled"] is False
    assert read_only_client.post(
        "/api/jobs",
        json={
            "kind": "data_validate",
            "config_path": "configs/data/sample.yaml",
        },
    ).status_code == 404

    app = create_app(
        GUIServiceConfig(
            workspace_root=tmp_path,
            cors_origins=("http://localhost:3000",),
        )
    )
    manager = app.state.job_manager
    monkeypatch.setattr(manager._pool, "submit", lambda *args, **kwargs: None)
    client = TestClient(app)
    health = client.get("/health").json()
    assert health["read_only"] is False
    assert health["execution_enabled"] is True
    configs = client.get("/api/configs", params={"kind": "data_validate"})
    assert configs.status_code == 200
    assert configs.json()["configs"][0]["path"] == "configs/data/sample.yaml"
    validation = client.post(
        "/api/configs/validate",
        json={
            "kind": "data_validate",
            "config_path": "configs/data/sample.yaml",
        },
    )
    assert validation.json()["valid"] is True
    created = client.post(
        "/api/jobs",
        json={
            "kind": "data_validate",
            "config_path": "configs/data/sample.yaml",
        },
    )
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "queued"
    assert client.get(f"/api/jobs/{job_id}/log").json()["output"] == ""
    assert client.delete(f"/api/jobs/{job_id}").json()["status"] == "cancelled"
    assert client.get("/api/capabilities").json()["agent_model"] == "deepseek-v4-pro"


def test_independent_output_is_forbidden_for_locked_test(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="locked test"):
        _evaluate_saved_run(
            tmp_path / "source-run",
            partition="test",
            config_override=None,
            output_dir_override=tmp_path / "independent-test",
        )

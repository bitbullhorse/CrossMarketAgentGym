"""Local-only, allow-listed job execution for the optional GUI service."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from crossmarket_agentgym.reporting.io import resolve_inside

JobKind = Literal[
    "data_validate",
    "environment_check",
    "train",
    "backtest",
    "agent",
    "tune",
    "reproduce",
    "report",
    "formal_experiment",
]
JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
ConfigKind = Literal[
    "data_validate",
    "environment_check",
    "train",
    "agent",
    "tune",
    "report",
]

_PORTABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_CONFIG_DIRECTORIES: dict[ConfigKind, str] = {
    "data_validate": "configs/data",
    "environment_check": "configs/env",
    "train": "configs/train",
    "agent": "configs/agents",
    "tune": "configs/tune",
    "report": "configs/reporting",
}
_CONFIG_REQUIRED = frozenset(_CONFIG_DIRECTORIES)
_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
_MAX_CONFIG_BYTES = 512_000


def _utc_now() -> datetime:
    return datetime.now(UTC)


class StrictAPIModel(BaseModel):
    """Reject unknown fields at the browser/service boundary."""

    model_config = ConfigDict(extra="forbid")


class ConfigCatalogEntry(StrictAPIModel):
    """One credential-free YAML configuration available to the GUI."""

    kind: ConfigKind
    path: str
    name: str
    size_bytes: int = Field(ge=1)


class ConfigContent(StrictAPIModel):
    """Bounded YAML returned for explicit user editing."""

    kind: ConfigKind
    path: str
    content: str
    sha256: str


class ConfigValidationRequest(StrictAPIModel):
    """A selected template plus an optional edited YAML body."""

    kind: ConfigKind
    config_path: str
    config_yaml: str | None = Field(default=None, max_length=_MAX_CONFIG_BYTES)


class ConfigValidationResult(StrictAPIModel):
    """Structured, non-throwing validation response for the editor."""

    valid: bool
    kind: ConfigKind
    config_path: str
    errors: tuple[str, ...] = ()
    safety_checks: dict[str, bool] = Field(default_factory=dict)


class JobRequest(StrictAPIModel):
    """One allow-listed GUI action; arbitrary commands are impossible."""

    kind: JobKind
    config_path: str | None = None
    config_yaml: str | None = Field(default=None, max_length=_MAX_CONFIG_BYTES)
    run_id: str | None = None
    partition: Literal["validation", "test"] = "validation"
    acknowledge_locked_test: bool = False
    reproduce_mode: Literal["verify_only", "execute_compare"] = "verify_only"
    formal_group: Literal["A", "B", "C", "D", "E", "F"] | None = None
    formal_method: str | None = None
    formal_seed: int | None = Field(default=None, ge=0, le=2**32 - 1)
    acknowledge_frozen_protocol: bool = False

    @model_validator(mode="after")
    def validate_action_shape(self) -> JobRequest:
        """Require only the fields meaningful for the selected workflow."""
        if self.kind in _CONFIG_REQUIRED:
            if self.config_path is None:
                raise ValueError(f"{self.kind} requires config_path")
        elif self.config_yaml is not None:
            raise ValueError("config_yaml is only valid for config-based jobs")
        if self.config_yaml is not None and self.config_path is None:
            raise ValueError("config_yaml requires config_path")
        if self.kind in {"backtest", "reproduce"} and self.run_id is None:
            raise ValueError(f"{self.kind} requires run_id")
        if self.run_id is not None and _PORTABLE_ID.fullmatch(self.run_id) is None:
            raise ValueError("run_id contains unsupported path characters")
        if self.kind == "backtest" and self.partition == "test":
            if not self.acknowledge_locked_test:
                raise ValueError("locked test evaluation requires explicit acknowledgement")
        elif self.acknowledge_locked_test:
            raise ValueError("locked-test acknowledgement is only valid for a test backtest")
        if self.kind == "formal_experiment":
            if self.formal_group is None:
                raise ValueError("formal_experiment requires formal_group")
            if not self.acknowledge_frozen_protocol:
                raise ValueError("formal experiment requires frozen-protocol acknowledgement")
        elif any(
            value is not None
            for value in (self.formal_group, self.formal_method, self.formal_seed)
        ) or self.acknowledge_frozen_protocol:
            raise ValueError("formal experiment fields require kind=formal_experiment")
        return self


class JobRecord(StrictAPIModel):
    """Persisted state for one independently auditable GUI launch."""

    job_id: str
    kind: JobKind
    status: JobStatus
    command: tuple[str, ...]
    config_path: str | None = None
    run_id: str | None = None
    partition: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    return_code: int | None = None
    pid: int | None = None
    log_path: str
    error: str | None = None


def _sha256_text(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_relative_config(
    workspace: Path,
    *,
    kind: ConfigKind,
    config_path: str,
) -> Path:
    expected_root = resolve_inside(_CONFIG_DIRECTORIES[kind], workspace)
    selected = resolve_inside(config_path, workspace)
    try:
        selected.relative_to(expected_root)
    except ValueError as error:
        raise ValueError(f"configuration must be inside {_CONFIG_DIRECTORIES[kind]}") from error
    if selected.suffix.lower() not in {".yaml", ".yml"} or not selected.is_file():
        raise FileNotFoundError("configuration file not found")
    if selected.stat().st_size > _MAX_CONFIG_BYTES:
        raise ValueError("configuration exceeds GUI size limit")
    return selected


def list_configurations(
    workspace_root: Path,
    *,
    kind: ConfigKind | None = None,
) -> tuple[ConfigCatalogEntry, ...]:
    """List only YAML files from the six allow-listed configuration trees."""
    workspace = workspace_root.resolve()
    kinds = (kind,) if kind is not None else tuple(_CONFIG_DIRECTORIES)
    entries: list[ConfigCatalogEntry] = []
    for config_kind in kinds:
        directory = resolve_inside(_CONFIG_DIRECTORIES[config_kind], workspace)
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.y*ml"), key=lambda item: item.name):
            if not path.is_file() or path.stat().st_size > _MAX_CONFIG_BYTES:
                continue
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError):
                continue
            if not isinstance(raw, dict) or not _is_runnable_template(
                config_kind,
                cast(dict[str, Any], raw),
            ):
                continue
            relative = path.relative_to(workspace).as_posix()
            entries.append(
                ConfigCatalogEntry(
                    kind=config_kind,
                    path=relative,
                    name=path.stem,
                    size_bytes=path.stat().st_size,
                )
            )
    return tuple(entries)


def _is_runnable_template(kind: ConfigKind, raw: dict[str, Any]) -> bool:
    required_keys: dict[ConfigKind, frozenset[str]] = {
        "data_validate": frozenset({"dataset"}),
        "environment_check": frozenset({"dataset_root", "smoke_steps"}),
        "train": frozenset({"dataset_root", "split", "trainer"}),
        "agent": frozenset(),
        "tune": frozenset({"study_name", "search_space"}),
        "report": frozenset({"report_id", "experiments"}),
    }
    if kind == "agent":
        return "preset" in raw or "team" in raw
    return required_keys[kind].issubset(raw)


def read_configuration(
    workspace_root: Path,
    *,
    kind: ConfigKind,
    config_path: str,
) -> ConfigContent:
    """Read one explicitly selected, credential-free YAML template."""
    path = _safe_relative_config(
        workspace_root.resolve(),
        kind=kind,
        config_path=config_path,
    )
    content = path.read_text(encoding="utf-8")
    return ConfigContent(
        kind=kind,
        path=path.relative_to(workspace_root.resolve()).as_posix(),
        content=content,
        sha256=_sha256_text(content),
    )


def _parse_yaml(content: str) -> dict[str, Any]:
    if len(content.encode("utf-8")) > _MAX_CONFIG_BYTES:
        raise ValueError("configuration exceeds GUI size limit")
    raw = yaml.safe_load(content)
    if not isinstance(raw, dict):
        raise TypeError("configuration must be a YAML mapping")
    return cast(dict[str, Any], raw)


def _reject_embedded_secrets(value: Any, path: str = "") -> None:
    """Refuse common credential fields while allowing environment-variable names."""
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower()
            child_path = f"{path}.{key}" if path else str(key)
            if (
                normalized in {"api_key", "password", "access_token", "secret"}
                or normalized.endswith("_password")
            ):
                raise ValueError(f"credentials are forbidden in GUI YAML: {child_path}")
            _reject_embedded_secrets(nested, child_path)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_embedded_secrets(nested, f"{path}[{index}]")


def _normalize_gui_yaml(
    *,
    kind: ConfigKind,
    source_path: Path,
    content: str,
) -> tuple[str, dict[str, Any]]:
    raw = _parse_yaml(content)
    _reject_embedded_secrets(raw)
    if kind == "tune":
        objective = raw.get("objective")
        if isinstance(objective, dict):
            base_value = objective.get("base_train_config")
            if isinstance(base_value, str):
                base_path = Path(base_value)
                if not base_path.is_absolute():
                    objective["base_train_config"] = str(
                        (source_path.parent / base_path).resolve()
                    )
    normalized = yaml.safe_dump(raw, sort_keys=False, allow_unicode=True)
    return normalized, raw


def _validate_raw_config(kind: ConfigKind, raw: dict[str, Any]) -> None:
    if kind == "data_validate":
        from crossmarket_agentgym.data.config import DataValidationConfig

        DataValidationConfig.model_validate(raw)
    elif kind == "environment_check":
        from crossmarket_agentgym.environments.checks import EnvironmentCheckConfig

        EnvironmentCheckConfig.model_validate(raw)
    elif kind == "train":
        from crossmarket_agentgym.rl.config import TrainRunConfig

        TrainRunConfig.model_validate(raw)
    elif kind == "agent":
        if "preset" in raw:
            from crossmarket_agentgym.agents.layer_config import Phase7RunConfig

            Phase7RunConfig.model_validate(raw)
        else:
            from crossmarket_agentgym.agents.models import AgentRuntimeConfig

            AgentRuntimeConfig.model_validate(raw)
    elif kind == "tune":
        from crossmarket_agentgym.tuning.config import (
            TuningRunConfig,
            _normalize_search_space,
        )

        TuningRunConfig.model_validate(_normalize_search_space(raw))
    else:
        from crossmarket_agentgym.reporting.models import SoftwareXReportConfig

        SoftwareXReportConfig.model_validate(raw)


def _sandbox_path(
    workspace: Path,
    value: Any,
    *,
    label: str,
    allow_workspace: bool = False,
) -> Path:
    if not isinstance(value, str | Path):
        raise TypeError(f"{label} must be a filesystem path")
    path = resolve_inside(Path(value), workspace)
    if not allow_workspace and path == workspace:
        raise ValueError(f"{label} cannot target the workspace root")
    return path


def _enforce_workspace_paths(
    workspace: Path,
    *,
    kind: ConfigKind,
    raw: dict[str, Any],
) -> None:
    """Keep all GUI-selected inputs and outputs inside the configured workspace."""
    if kind == "data_validate":
        dataset = raw.get("dataset")
        if isinstance(dataset, dict):
            _sandbox_path(workspace, dataset.get("root"), label="dataset.root")
        return
    if kind == "environment_check":
        _sandbox_path(workspace, raw.get("dataset_root"), label="dataset_root")
        return
    if kind == "train":
        _sandbox_path(workspace, raw.get("dataset_root"), label="dataset_root")
        _sandbox_path(workspace, raw.get("output_dir", "runs"), label="output_dir")
        return
    if kind == "agent":
        configured_workspace = _sandbox_path(
            workspace,
            raw.get("workspace_root", "."),
            label="workspace_root",
            allow_workspace=True,
        )
        if configured_workspace != workspace:
            raise ValueError("workspace_root must resolve to the service workspace")
        _sandbox_path(workspace, raw.get("output_dir", "runs"), label="output_dir")
        return
    if kind == "tune":
        _sandbox_path(
            workspace,
            raw.get("output_dir", "runs/tuning"),
            label="output_dir",
        )
        _sandbox_path(
            workspace,
            raw.get("storage_path", "runs/tuning/study.sqlite3"),
            label="storage_path",
        )
        objective = raw.get("objective")
        if isinstance(objective, dict) and objective.get("base_train_config") is not None:
            base_path = _sandbox_path(
                workspace,
                objective["base_train_config"],
                label="objective.base_train_config",
            )
            if not base_path.is_file():
                raise FileNotFoundError("objective.base_train_config not found")
        return
    configured_workspace = _sandbox_path(
        workspace,
        raw.get("workspace_root", "."),
        label="workspace_root",
        allow_workspace=True,
    )
    if configured_workspace != workspace:
        raise ValueError("workspace_root must resolve to the service workspace")
    _sandbox_path(workspace, raw.get("runs_root", "runs"), label="runs_root")
    _sandbox_path(workspace, raw.get("output_dir", "reports"), label="output_dir")
    experiments = raw.get("experiments")
    if isinstance(experiments, list):
        for index, experiment in enumerate(experiments):
            if not isinstance(experiment, dict):
                continue
            for evidence_index, evidence in enumerate(
                experiment.get("evidence_paths", [])
            ):
                _sandbox_path(
                    workspace,
                    evidence,
                    label=f"experiments[{index}].evidence_paths[{evidence_index}]",
                )


def validate_configuration(
    workspace_root: Path,
    request: ConfigValidationRequest,
) -> ConfigValidationResult:
    """Validate edited YAML without writing it or starting any workflow."""
    workspace = workspace_root.resolve()
    try:
        source = _safe_relative_config(
            workspace,
            kind=request.kind,
            config_path=request.config_path,
        )
        content = (
            request.config_yaml
            if request.config_yaml is not None
            else source.read_text(encoding="utf-8")
        )
        _, raw = _normalize_gui_yaml(
            kind=request.kind,
            source_path=source,
            content=content,
        )
        _validate_raw_config(request.kind, raw)
        _enforce_workspace_paths(workspace, kind=request.kind, raw=raw)
    except (OSError, TypeError, ValueError) as error:
        return ConfigValidationResult(
            valid=False,
            kind=request.kind,
            config_path=request.config_path,
            errors=(str(error),),
            safety_checks={
                "strict_schema": False,
                "credentials_absent": "credential" not in str(error).lower(),
                "test_partition_isolated_from_hpo": request.kind != "tune",
            },
        )
    return ConfigValidationResult(
        valid=True,
        kind=request.kind,
        config_path=request.config_path,
        safety_checks={
            "strict_schema": True,
            "credentials_absent": True,
            "test_partition_isolated_from_hpo": True,
        },
    )


class JobManager:
    """Thread-safe subprocess supervisor with a strict command allow-list."""

    def __init__(
        self,
        workspace_root: Path,
        *,
        max_concurrent_jobs: int = 2,
        max_log_bytes: int = 200_000,
    ) -> None:
        self.workspace = workspace_root.resolve()
        self.root = self.workspace / "logs" / "gui-jobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_log_bytes = max_log_bytes
        self._lock = threading.RLock()
        self._records: dict[str, JobRecord] = {}
        self._processes: dict[str, subprocess.Popen[bytes]] = {}
        self._pool = ThreadPoolExecutor(
            max_workers=max_concurrent_jobs,
            thread_name_prefix="cmag-gui-job",
        )
        self._load_existing_records()

    def _load_existing_records(self) -> None:
        for path in sorted(self.root.glob("*/job.json")):
            try:
                record = JobRecord.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if record.status not in _TERMINAL_STATUSES:
                record = record.model_copy(
                    update={
                        "status": "failed",
                        "finished_at": _utc_now(),
                        "error": "service restarted before job completion",
                    }
                )
                self._persist(record)
            self._records[record.job_id] = record

    def _persist(self, record: JobRecord) -> None:
        directory = self.root / record.job_id
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "job.json"
        temporary = directory / "job.json.tmp"
        temporary.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(target)

    def _materialize_config(
        self,
        request: JobRequest,
        *,
        job_id: str,
    ) -> str | None:
        if request.kind not in _CONFIG_REQUIRED:
            return None
        kind = cast(ConfigKind, request.kind)
        assert request.config_path is not None
        source = _safe_relative_config(
            self.workspace,
            kind=kind,
            config_path=request.config_path,
        )
        content = (
            request.config_yaml
            if request.config_yaml is not None
            else source.read_text(encoding="utf-8")
        )
        normalized, raw = _normalize_gui_yaml(
            kind=kind,
            source_path=source,
            content=content,
        )
        _validate_raw_config(kind, raw)
        _enforce_workspace_paths(self.workspace, kind=kind, raw=raw)
        destination = self.root / job_id / "config.resolved.yaml"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(normalized, encoding="utf-8")
        return destination.relative_to(self.workspace).as_posix()

    def _build_command(
        self,
        request: JobRequest,
        *,
        job_id: str,
        materialized_config: str | None,
    ) -> tuple[str, ...]:
        prefix = (sys.executable, "-m", "crossmarket_agentgym")
        if request.kind == "data_validate":
            return (*prefix, "data", "validate", "--config", cast(str, materialized_config))
        if request.kind == "environment_check":
            return (*prefix, "env", "check", "--config", cast(str, materialized_config))
        if request.kind == "train":
            return (*prefix, "train", "--config", cast(str, materialized_config))
        if request.kind == "agent":
            return (*prefix, "agent", "run", "--config", cast(str, materialized_config))
        if request.kind == "tune":
            return (*prefix, "tune", "--config", cast(str, materialized_config))
        if request.kind == "report":
            return (*prefix, "report", "softwarex", "--config", cast(str, materialized_config))
        if request.kind == "backtest":
            if request.partition == "validation":
                return (
                    sys.executable,
                    "-m",
                    "crossmarket_agentgym.api.job_worker",
                    "validation-backtest",
                    "--workspace-root",
                    ".",
                    "--run-id",
                    cast(str, request.run_id),
                    "--output-dir",
                    f"runs/backtests/{job_id}",
                )
            return (*prefix, "evaluate", "--run-id", cast(str, request.run_id))
        if request.kind == "reproduce":
            command = [
                *prefix,
                "reproduce",
                "--run-id",
                cast(str, request.run_id),
                "--workspace-root",
                ".",
                "--runs-root",
                "runs",
            ]
            if request.reproduce_mode == "verify_only":
                command.append("--verify-only")
            else:
                command.extend(("--execute", "--compare"))
            return tuple(command)
        self._validate_formal_gate(request)
        command = [
            sys.executable,
            "scripts/run_phase12_group.py",
            "--group",
            cast(str, request.formal_group),
            "--workspace-root",
            ".",
            "--skip-completed",
        ]
        if request.formal_method is not None:
            if _PORTABLE_ID.fullmatch(request.formal_method) is None:
                raise ValueError("formal_method contains unsupported characters")
            command.extend(("--method", request.formal_method))
        if request.formal_seed is not None:
            command.extend(("--seed", str(request.formal_seed)))
        return tuple(command)

    def _validate_formal_gate(self, request: JobRequest) -> None:
        """Refuse frozen tasks unless commit and matrix selection both match."""
        matrix_path = self.workspace / "experiments" / "run_matrix_v6.json"
        if not matrix_path.is_file() or matrix_path.stat().st_size > 5_000_000:
            raise FileNotFoundError("frozen Phase 12 matrix is unavailable")
        raw = json.loads(matrix_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise TypeError("frozen Phase 12 matrix must be a JSON object")
        expected_commit = str(raw.get("code_commit", ""))
        current_commit = os.getenv("CMAG_CODE_COMMIT", "")
        if not current_commit:
            try:
                completed = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.workspace,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                current_commit = completed.stdout.strip()
            except (OSError, subprocess.SubprocessError) as error:
                raise ValueError("cannot establish current Git commit") from error
        if not expected_commit or current_commit != expected_commit:
            raise ValueError(
                "current Git commit does not match the frozen Phase 12 matrix"
            )
        tasks = raw.get("tasks")
        if not isinstance(tasks, list):
            raise TypeError("frozen Phase 12 matrix has no task list")
        selected = [
            task
            for task in tasks
            if isinstance(task, dict)
            and task.get("group") == request.formal_group
            and (
                request.formal_method is None
                or task.get("method") == request.formal_method
            )
            and (
                request.formal_seed is None
                or task.get("seed") == request.formal_seed
            )
        ]
        if not selected:
            raise ValueError("formal experiment selection matches no frozen task")

    def submit(self, request: JobRequest) -> JobRecord:
        """Validate, persist, queue, and return one new job."""
        job_id = f"gui-{_utc_now():%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
        materialized = self._materialize_config(request, job_id=job_id)
        command = self._build_command(
            request,
            job_id=job_id,
            materialized_config=materialized,
        )
        record = JobRecord(
            job_id=job_id,
            kind=request.kind,
            status="queued",
            command=command,
            config_path=materialized,
            run_id=request.run_id,
            partition=request.partition if request.kind == "backtest" else None,
            created_at=_utc_now(),
            log_path=(self.root / job_id / "output.log")
            .relative_to(self.workspace)
            .as_posix(),
        )
        with self._lock:
            self._records[job_id] = record
            self._persist(record)
        self._pool.submit(self._execute, job_id)
        return record

    def _execute(self, job_id: str) -> None:
        with self._lock:
            record = self._records[job_id]
            if record.status == "cancelled":
                return
            record = record.model_copy(
                update={"status": "running", "started_at": _utc_now()}
            )
            self._records[job_id] = record
            self._persist(record)
        log_path = resolve_inside(record.log_path, self.workspace)
        try:
            with log_path.open("wb") as log_stream:
                process = subprocess.Popen(
                    list(record.command),
                    cwd=self.workspace,
                    stdout=log_stream,
                    stderr=subprocess.STDOUT,
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                )
                with self._lock:
                    self._processes[job_id] = process
                    current = self._records[job_id].model_copy(
                        update={"pid": process.pid}
                    )
                    self._records[job_id] = current
                    self._persist(current)
                return_code = process.wait()
            with self._lock:
                current = self._records[job_id]
                status: JobStatus
                if current.status == "cancelled":
                    status = "cancelled"
                else:
                    status = "completed" if return_code == 0 else "failed"
                current = current.model_copy(
                    update={
                        "status": status,
                        "finished_at": _utc_now(),
                        "return_code": return_code,
                    }
                )
                self._records[job_id] = current
                self._processes.pop(job_id, None)
                self._persist(current)
        except OSError as error:
            with self._lock:
                current = self._records[job_id].model_copy(
                    update={
                        "status": "failed",
                        "finished_at": _utc_now(),
                        "error": str(error),
                    }
                )
                self._records[job_id] = current
                self._processes.pop(job_id, None)
                self._persist(current)

    def list(self, *, limit: int = 100) -> tuple[JobRecord, ...]:
        """Return newest jobs first."""
        with self._lock:
            records = sorted(
                self._records.values(),
                key=lambda record: record.created_at,
                reverse=True,
            )
            return tuple(records[:limit])

    def get(self, job_id: str) -> JobRecord:
        """Return one job without exposing arbitrary files."""
        if _PORTABLE_ID.fullmatch(job_id) is None:
            raise KeyError(job_id)
        with self._lock:
            if job_id not in self._records:
                raise KeyError(job_id)
            return self._records[job_id]

    def log_tail(self, job_id: str) -> str:
        """Read a bounded UTF-8 tail of the job's combined output."""
        record = self.get(job_id)
        path = resolve_inside(record.log_path, self.workspace)
        if not path.is_file():
            return ""
        with path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - self.max_log_bytes))
            payload = stream.read(self.max_log_bytes)
        return payload.decode("utf-8", errors="replace")

    def cancel(self, job_id: str) -> JobRecord:
        """Cancel a queued job or terminate its direct child process."""
        with self._lock:
            record = self.get(job_id)
            if record.status in _TERMINAL_STATUSES:
                return record
            if record.status == "running" and (
                record.kind == "formal_experiment"
                or (record.kind == "backtest" and record.partition == "test")
            ):
                raise RuntimeError(
                    "locked test and formal experiment jobs cannot be interrupted"
                )
            process = self._processes.get(job_id)
            if process is not None and process.poll() is None:
                process.terminate()
            record = record.model_copy(
                update={
                    "status": "cancelled",
                    "finished_at": _utc_now(),
                }
            )
            self._records[job_id] = record
            self._persist(record)
            return record

    def shutdown(self) -> None:
        """Stop accepting jobs without killing completed evidence."""
        self._pool.shutdown(wait=False, cancel_futures=True)


def job_record_json(record: JobRecord) -> dict[str, object]:
    """Return a plain JSON-compatible mapping for FastAPI."""
    return cast(dict[str, object], json.loads(record.model_dump_json()))

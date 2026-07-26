"""Read-only, whitelist-based indexing of heterogeneous run artifacts."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from crossmarket_agentgym.reporting.io import (
    combined_sha256,
    finite_metrics,
    read_bounded_json,
    resolve_inside,
)
from crossmarket_agentgym.reporting.models import RunIndex, RunRecord


def _mapping(raw: Any, name: str) -> dict[str, Any]:
    value = raw.get(name) if isinstance(raw, dict) else None
    return value if isinstance(value, dict) else {}


def _scalar(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, str | bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    return None


def _artifact_count(path: Path, *, limit: int = 100_000) -> int:
    count = 0
    for item in path.rglob("*"):
        if item.is_file():
            count += 1
            if count >= limit:
                return limit
    return count


def _record_fingerprint(sources: list[Path], workspace: Path) -> str:
    return combined_sha256(sources, root=workspace)


def _training_record(
    path: Path,
    workspace: Path,
    *,
    max_json_bytes: int,
) -> RunRecord:
    summary_path = path / "run_summary.json"
    summary = read_bounded_json(summary_path, max_bytes=max_json_bytes)
    if not isinstance(summary, dict):
        raise TypeError("training summary must be a JSON object")
    sources = [summary_path]
    metrics: dict[str, dict[str, float]] = {}
    partitions: list[str] = []
    for partition in ("validation", "test"):
        metric_path = path / partition / "metrics.json"
        if not metric_path.exists():
            continue
        raw = read_bounded_json(metric_path, max_bytes=max_json_bytes)
        partition_metrics = finite_metrics(_mapping(raw, "metrics"))
        metrics[partition] = partition_metrics
        partitions.append(partition)
        sources.append(metric_path)
    artifact_path = path / "training_artifact.json"
    artifact = (
        read_bounded_json(artifact_path, max_bytes=max_json_bytes)
        if artifact_path.exists()
        else {}
    )
    if artifact_path.exists():
        sources.append(artifact_path)
    resources = path / "resources.jsonl"
    runtime: float | None = None
    if resources.exists():
        if resources.stat().st_size > max_json_bytes:
            raise ValueError("resource journal exceeds report size limit")
        for line in resources.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            candidate = item.get("wall_seconds") if isinstance(item, dict) else None
            if isinstance(candidate, int | float) and not isinstance(candidate, bool):
                runtime = float(candidate)
        sources.append(resources)
    attributes = {
        "requested_timesteps": _scalar(summary.get("requested_timesteps")),
        "trained_timesteps": _scalar(summary.get("trained_timesteps")),
        "seed": _scalar(artifact.get("seed") if isinstance(artifact, dict) else None),
        "runtime_seconds": runtime,
    }
    return RunRecord(
        run_id=str(summary.get("run_id", path.name)),
        kind="training",
        relative_path=path.relative_to(workspace).as_posix(),
        status="completed",
        algorithm=str(summary.get("algorithm", "unknown")),
        partitions=tuple(partitions),
        metrics=metrics,
        attributes=attributes,
        artifact_count=_artifact_count(path),
        source_files=tuple(item.relative_to(workspace).as_posix() for item in sources),
        fingerprint=_record_fingerprint(sources, workspace),
    )


def _team_totals(summary: dict[str, Any]) -> tuple[int, int, int]:
    configured = int(summary.get("configured_instances", 0))
    succeeded = int(summary.get("succeeded", 0))
    fallback = int(summary.get("fallback", 0))
    return configured, succeeded, fallback


def _phase7_record(
    path: Path,
    workspace: Path,
    *,
    max_json_bytes: int,
) -> RunRecord:
    summary_path = path / "phase7_summary.json"
    summary = read_bounded_json(summary_path, max_bytes=max_json_bytes)
    if not isinstance(summary, dict):
        raise TypeError("Phase 7 summary must be a JSON object")
    teams = [
        _mapping(_mapping(summary, layer), "team")
        for layer in ("research", "risk", "hierarchical")
    ]
    totals = [_team_totals(team) for team in teams if team]
    configured = sum(item[0] for item in totals)
    succeeded = sum(item[1] for item in totals)
    fallback = sum(item[2] for item in totals)
    constraints = _mapping(_mapping(summary, "fusion"), "constraints")
    agent_metrics = {
        "task_success_rate": succeeded / configured if configured else 1.0,
        "fallback_rate": fallback / configured if configured else 0.0,
        "provider_runtimes_started": float(summary.get("provider_runtimes_started", 0)),
        "replay_verified": float(bool(summary.get("directive_replay_verified", False))),
    }
    for name in ("cash_floor", "max_asset_weight", "max_turnover", "risk_budget"):
        value = constraints.get(name)
        if isinstance(value, int | float) and not isinstance(value, bool):
            agent_metrics[name] = float(value)
    return RunRecord(
        run_id=str(summary.get("run_id", path.name)),
        kind="phase7",
        relative_path=path.relative_to(workspace).as_posix(),
        status="completed" if summary.get("directive_replay_verified") else "unverified",
        partitions=("agent",),
        metrics={"agent": agent_metrics},
        attributes={
            "preset": _scalar(summary.get("preset")),
            "network_used": _scalar(summary.get("network_used")),
            "allow_new_positions": _scalar(constraints.get("allow_new_positions")),
        },
        artifact_count=_artifact_count(path),
        source_files=(summary_path.relative_to(workspace).as_posix(),),
        fingerprint=_record_fingerprint([summary_path], workspace),
    )


def _agent_record(
    path: Path,
    workspace: Path,
    *,
    max_json_bytes: int,
) -> RunRecord:
    summary_path = path / "agent" / "team_summary.json"
    summary = read_bounded_json(summary_path, max_bytes=max_json_bytes)
    if not isinstance(summary, dict):
        raise TypeError("Agent summary must be a JSON object")
    configured, succeeded, fallback = _team_totals(summary)
    aggregate = _mapping(summary, "aggregate")
    return RunRecord(
        run_id=str(summary.get("run_id", path.name)),
        kind="agent",
        relative_path=path.relative_to(workspace).as_posix(),
        status=str(aggregate.get("status", "unknown")),
        partitions=("agent",),
        metrics={
            "agent": {
                "task_success_rate": succeeded / configured if configured else 0.0,
                "fallback_rate": fallback / configured if configured else 0.0,
            }
        },
        attributes={
            "topology": _scalar(summary.get("topology")),
            "network_used": _scalar(summary.get("network_used")),
            "configured_instances": configured,
        },
        artifact_count=_artifact_count(path),
        source_files=(summary_path.relative_to(workspace).as_posix(),),
        fingerprint=_record_fingerprint([summary_path], workspace),
    )


def _tuning_record(
    path: Path,
    workspace: Path,
    *,
    max_json_bytes: int,
) -> RunRecord:
    summary_path = path / "tuning_summary.json"
    report_path = path / "study_report.json"
    summary = read_bounded_json(summary_path, max_bytes=max_json_bytes)
    report = (
        read_bounded_json(report_path, max_bytes=max_json_bytes)
        if report_path.exists()
        else {}
    )
    if not isinstance(summary, dict) or not isinstance(report, dict):
        raise TypeError("tuning summaries must be JSON objects")
    best = _mapping(report, "best_trial")
    metrics = finite_metrics(_mapping(best, "metrics"))
    objectives = best.get("objectives")
    if isinstance(objectives, list):
        for index, value in enumerate(objectives):
            if isinstance(value, int | float) and not isinstance(value, bool):
                metrics[f"objective_{index}"] = float(value)
    sources = [summary_path]
    if report_path.exists():
        sources.append(report_path)
    test_accessed = bool(summary.get("test_set_accessed", True))
    return RunRecord(
        run_id=str(summary.get("study_name", path.name)),
        kind="tuning",
        relative_path=path.relative_to(workspace).as_posix(),
        status="completed" if not test_accessed else "invalid_test_access",
        partitions=("validation",),
        metrics={"validation": metrics},
        attributes={
            "trial_count": _scalar(summary.get("trial_count")),
            "completed_count": _scalar(summary.get("completed_count")),
            "failed_count": _scalar(summary.get("failed_count")),
            "best_trial_id": _scalar(summary.get("best_trial_id")),
            "test_set_accessed": test_accessed,
        },
        artifact_count=_artifact_count(path),
        source_files=tuple(item.relative_to(workspace).as_posix() for item in sources),
        fingerprint=_record_fingerprint(sources, workspace),
    )


def _candidate_directories(runs_root: Path) -> Iterable[Path]:
    for path in sorted(runs_root.iterdir(), key=lambda item: item.name):
        if not path.is_dir():
            continue
        yield path
        if path.name == "tuning":
            for child in sorted(path.iterdir(), key=lambda item: item.name):
                if child.is_dir():
                    yield child


def build_run_index(
    workspace_root: str | Path,
    runs_root: str | Path,
    *,
    include_run_ids: tuple[str, ...] = (),
    max_runs: int = 500,
    max_json_bytes: int = 5_000_000,
) -> RunIndex:
    """Index known artifacts without returning raw configuration or messages."""
    workspace = Path(workspace_root).resolve()
    root = resolve_inside(runs_root, workspace)
    if not root.is_dir():
        raise FileNotFoundError(root)
    records: list[RunRecord] = []
    for path in _candidate_directories(root):
        if (path / "phase7_summary.json").exists():
            record = _phase7_record(path, workspace, max_json_bytes=max_json_bytes)
        elif (path / "run_summary.json").exists():
            record = _training_record(path, workspace, max_json_bytes=max_json_bytes)
        elif (path / "tuning_summary.json").exists():
            record = _tuning_record(path, workspace, max_json_bytes=max_json_bytes)
        elif (path / "agent" / "team_summary.json").exists():
            record = _agent_record(path, workspace, max_json_bytes=max_json_bytes)
        else:
            continue
        records.append(record)
        if len(records) > max_runs:
            raise ValueError("run index exceeds configured max_runs")
    by_id: dict[str, RunRecord] = {}
    for record in records:
        if record.run_id in by_id:
            raise ValueError(f"duplicate indexed run_id: {record.run_id}")
        by_id[record.run_id] = record
    if include_run_ids:
        missing = sorted(set(include_run_ids) - set(by_id))
        if missing:
            raise FileNotFoundError(f"configured runs are missing: {missing}")
        records = [by_id[run_id] for run_id in include_run_ids]
    else:
        records.sort(key=lambda item: (item.kind, item.run_id))
    canonical = json.dumps(
        [item.model_dump(mode="json") for item in records],
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
    return RunIndex(
        runs_root=root.relative_to(workspace).as_posix(),
        runs=tuple(records),
        fingerprint=fingerprint,
    )

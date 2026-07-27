"""Execute Phase 11.3 Tasks B-I and write one portable evidence summary."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CommandSpec:
    """One argv-safe command belonging to a Phase 11.3 task."""

    name: str
    argv: tuple[str, ...]


@dataclass(frozen=True)
class TaskSpec:
    """One required Phase 11.3 task and its ordered commands."""

    task_id: str
    name: str
    commands: tuple[CommandSpec, ...]


@dataclass(frozen=True)
class CommandResult:
    """Serializable outcome for one command invocation."""

    name: str
    argv: tuple[str, ...]
    log_file: str
    exit_code: int
    runtime_seconds: float
    status: str


@dataclass(frozen=True)
class TaskResult:
    """Serializable aggregate for one Phase 11.3 task."""

    task_id: str
    name: str
    status: str
    runtime_seconds: float
    commands: tuple[CommandResult, ...]


def phase11_tasks(cmag: str) -> tuple[TaskSpec, ...]:
    """Return the frozen Task B-I command protocol."""
    return (
        TaskSpec(
            "B",
            "data_validate",
            (
                CommandSpec(
                    "validate_sample_data",
                    (
                        cmag,
                        "data",
                        "validate",
                        "--config",
                        "configs/data/sample.yaml",
                    ),
                ),
            ),
        ),
        TaskSpec(
            "C",
            "environment_check",
            (
                CommandSpec(
                    "check_cross_market_environment",
                    (
                        cmag,
                        "env",
                        "check",
                        "--config",
                        "configs/env/sample_cross_market.yaml",
                    ),
                ),
            ),
        ),
        TaskSpec(
            "D",
            "ppo_quickstart",
            (
                CommandSpec(
                    "train_ppo_quickstart",
                    (
                        cmag,
                        "train",
                        "--config",
                        "configs/train/ppo_quickstart.yaml",
                    ),
                ),
            ),
        ),
        TaskSpec(
            "E",
            "research_agent",
            (
                CommandSpec(
                    "run_research_agent",
                    (
                        cmag,
                        "agent",
                        "run",
                        "--config",
                        "configs/agents/research_single_mock.yaml",
                    ),
                ),
            ),
        ),
        TaskSpec(
            "F",
            "risk_committee",
            (
                CommandSpec(
                    "run_risk_committee",
                    (
                        cmag,
                        "agent",
                        "run",
                        "--config",
                        "configs/agents/risk_committee_mock.yaml",
                    ),
                ),
            ),
        ),
        TaskSpec(
            "G",
            "pso_quickstart",
            (
                CommandSpec(
                    "tune_ppo_with_pso",
                    (
                        cmag,
                        "tune",
                        "--config",
                        "configs/tune/ppo_pso_quickstart.yaml",
                    ),
                ),
            ),
        ),
        TaskSpec(
            "H",
            "report",
            (
                CommandSpec(
                    "report_source_run",
                    (cmag, "report", "--run-id", "repro-ppo-quickstart"),
                ),
            ),
        ),
        TaskSpec(
            "I",
            "reproduction",
            (
                CommandSpec(
                    "verify_artifact_integrity",
                    (
                        cmag,
                        "reproduce",
                        "--run-id",
                        "repro-ppo-quickstart",
                        "--verify-only",
                    ),
                ),
                CommandSpec(
                    "execute_computational_replay",
                    (
                        cmag,
                        "reproduce",
                        "--run-id",
                        "repro-ppo-quickstart",
                        "--execute",
                        "--compare",
                        "--tolerance-config",
                        "configs/reproduction/phase11_cpu.yaml",
                    ),
                ),
            ),
        ),
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_commit(workspace: Path) -> str:
    declared = os.environ.get("CMAG_EVIDENCE_COMMIT", "").strip()
    if declared:
        return declared
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def _runtime_identity() -> dict[str, Any]:
    try:
        import torch
    except ImportError:
        torch_version = None
        cuda_available = None
    else:
        torch_version = torch.__version__
        cuda_available = bool(torch.cuda.is_available())
    return {
        "executor": os.environ.get("CMAG_EVIDENCE_EXECUTOR", "local"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "operating_system": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_model": platform.processor() or platform.machine() or "unknown",
        "logical_cpu_count": os.cpu_count(),
        "torch_version": torch_version,
        "cuda_available": cuda_available,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "nvidia_visible_devices": os.environ.get("NVIDIA_VISIBLE_DEVICES"),
    }


def _run_command(
    spec: CommandSpec,
    *,
    workspace: Path,
    log_dir: Path,
    task_id: str,
    command_index: int,
) -> CommandResult:
    log_path = log_dir / (
        f"task_{task_id}_{command_index:02d}_{spec.name}.log"
    )
    started = time.perf_counter()
    with log_path.open("w", encoding="utf-8", newline="\n") as log:
        log.write(json.dumps({"argv": spec.argv}, ensure_ascii=False) + "\n")
        log.flush()
        completed = subprocess.run(
            list(spec.argv),
            cwd=workspace,
            check=False,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            env=os.environ.copy(),
        )
    runtime = time.perf_counter() - started
    return CommandResult(
        name=spec.name,
        argv=spec.argv,
        log_file=log_path.relative_to(log_dir.parent).as_posix(),
        exit_code=completed.returncode,
        runtime_seconds=runtime,
        status="passed" if completed.returncode == 0 else "failed",
    )


def _comparison_evidence(workspace: Path) -> dict[str, Any] | None:
    reproduction_root = (
        workspace
        / "runs"
        / "reproductions"
        / "repro-ppo-quickstart"
    )
    comparisons = sorted(
        reproduction_root.glob("replay-*/reproduction_comparison.json")
    )
    if not comparisons:
        return None
    path = comparisons[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "relative_path": path.relative_to(workspace).as_posix(),
        "sha256": _sha256(path),
        "reproduction_level": payload.get("reproduction_level"),
        "artifact_integrity_verified": payload.get(
            "artifact_integrity_verified"
        ),
        "computational_replay_executed": payload.get(
            "computational_replay_executed"
        ),
        "within_tolerance": payload.get("within_tolerance"),
        "test_partition_accessed_by_replay": payload.get(
            "test_partition_accessed_by_replay"
        ),
        "network_used": payload.get("network_used"),
        "account_state_mutated": payload.get("account_state_mutated"),
    }


def _write_markdown(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Phase 11.3 Task B–I summary",
        "",
        f"- Commit: `{summary['source_commit']}`",
        f"- Executor: `{summary['runtime_identity']['executor']}`",
        f"- Started: `{summary['started_at']}`",
        f"- Finished: `{summary['finished_at']}`",
        f"- All passed: `{str(summary['all_passed']).lower()}`",
        f"- CUDA available: `{summary['runtime_identity']['cuda_available']}`",
        "",
        "| Task | Name | Status | Runtime (s) |",
        "|---|---|---|---:|",
    ]
    for task in summary["tasks"]:
        lines.append(
            f"| {task['task_id']} | {task['name']} | {task['status']} | "
            f"{task['runtime_seconds']:.6f} |"
        )
    comparison = summary.get("reproduction_comparison")
    if isinstance(comparison, dict):
        lines.extend(
            (
                "",
                "## Computational replay",
                "",
                f"- Level: `{comparison.get('reproduction_level')}`",
                f"- Within tolerance: `{comparison.get('within_tolerance')}`",
                f"- Evidence: `{comparison.get('relative_path')}`",
                f"- SHA-256: `{comparison.get('sha256')}`",
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def execute_protocol(
    *,
    workspace: Path,
    evidence_dir: Path,
    cmag: str,
) -> dict[str, Any]:
    """Run the frozen protocol and always persist JSON/Markdown evidence."""
    workspace = workspace.resolve()
    evidence_dir = evidence_dir.resolve()
    runs_dir = workspace / "runs"
    if runs_dir.exists() and any(runs_dir.iterdir()):
        raise FileExistsError(f"runs directory must be empty: {runs_dir}")
    runs_dir.mkdir(parents=True, exist_ok=True)
    log_dir = evidence_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=False)

    started_at = _utc_now()
    overall_start = time.perf_counter()
    task_results: list[TaskResult] = []
    prior_failed = False
    for task in phase11_tasks(cmag):
        task_start = time.perf_counter()
        command_results: list[CommandResult] = []
        if prior_failed:
            task_results.append(
                TaskResult(
                    task_id=task.task_id,
                    name=task.name,
                    status="skipped_dependency_failure",
                    runtime_seconds=0.0,
                    commands=(),
                )
            )
            continue
        for index, command in enumerate(task.commands, start=1):
            result = _run_command(
                command,
                workspace=workspace,
                log_dir=log_dir,
                task_id=task.task_id,
                command_index=index,
            )
            command_results.append(result)
            if result.status != "passed":
                prior_failed = True
                break
        task_results.append(
            TaskResult(
                task_id=task.task_id,
                name=task.name,
                status="failed" if prior_failed else "passed",
                runtime_seconds=time.perf_counter() - task_start,
                commands=tuple(command_results),
            )
        )

    finished_at = _utc_now()
    runtime_identity = _runtime_identity()
    all_tasks_passed = all(item.status == "passed" for item in task_results)
    cuda_is_disabled = runtime_identity["cuda_available"] is False
    comparison = _comparison_evidence(workspace)
    comparison_valid = (
        isinstance(comparison, dict)
        and comparison.get("artifact_integrity_verified") is True
        and comparison.get("computational_replay_executed") is True
        and comparison.get("reproduction_level")
        in {"bitwise_reproduced", "numerically_reproduced"}
        and comparison.get("within_tolerance") is True
        and comparison.get("test_partition_accessed_by_replay") is False
        and comparison.get("network_used") is False
        and comparison.get("account_state_mutated") is False
    )
    summary: dict[str, Any] = {
        "schema_version": "1.0",
        "protocol": "phase11.3-tasks-b-i",
        "source_commit": _source_commit(workspace),
        "started_at": _iso(started_at),
        "finished_at": _iso(finished_at),
        "runtime_seconds": time.perf_counter() - overall_start,
        "runtime_identity": runtime_identity,
        "tasks": [asdict(item) for item in task_results],
        "reproduction_comparison": comparison,
        "all_passed": all_tasks_passed
        and cuda_is_disabled
        and comparison_valid,
    }
    json_path = evidence_dir / "11_3_task_summary.json"
    json_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _write_markdown(summary, evidence_dir / "11_3_task_summary.md")
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute Phase 11.3 Tasks B-I and emit unified evidence."
    )
    parser.add_argument("--workspace-root", type=Path, default=Path("."))
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--cmag", default=shutil.which("cmag") or "cmag")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        summary = execute_protocol(
            workspace=args.workspace_root,
            evidence_dir=args.evidence_dir,
            cmag=args.cmag,
        )
    except Exception as error:
        print(f"Phase 11.3 evidence runner failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

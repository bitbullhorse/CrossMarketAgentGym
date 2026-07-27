"""Fail-closed entry point for one frozen Phase 12 task."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from crossmarket_agentgym.experiments.agent_runs import run_group_e
from crossmarket_agentgym.experiments.audit import FormalRunAudit, FormalRunRecord
from crossmarket_agentgym.experiments.environment_validation import (
    run_environment_validation,
)
from crossmarket_agentgym.experiments.generalization_runs import run_group_c
from crossmarket_agentgym.experiments.hpo_runs import run_group_f
from crossmarket_agentgym.experiments.matrix import (
    FormalRunMatrix,
    FormalTask,
    git_commit,
    load_run_matrix,
)
from crossmarket_agentgym.experiments.mechanism_runs import run_group_d
from crossmarket_agentgym.experiments.protocol import (
    load_protocol,
    sha256_file,
    verify_protocol,
)
from crossmarket_agentgym.experiments.strategy_runs import run_group_b


def _load_verified_matrix(path: Path, checksum_path: Path) -> FormalRunMatrix:
    fields = checksum_path.read_text(encoding="utf-8").split()
    if len(fields) != 2 or fields[1] != path.name or fields[0] != sha256_file(path):
        raise ValueError("formal run matrix checksum is invalid")
    return load_run_matrix(path)


def _task(matrix: FormalRunMatrix, run_id: str) -> FormalTask:
    matches = [task for task in matrix.tasks if task.run_id == run_id]
    if len(matches) != 1:
        raise ValueError(f"formal run ID is absent or duplicated: {run_id}")
    return matches[0]


def _preflight(
    *,
    workspace_root: Path,
    task: FormalTask,
    protocol_path: Path,
    protocol_checksum_path: Path,
) -> None:
    verification = verify_protocol(
        protocol_path,
        protocol_checksum_path,
        workspace_root=workspace_root,
    )
    if not verification.is_ready_to_execute:
        raise RuntimeError(f"protocol input gate failed: {verification.blockers}")
    if verification.protocol_sha256 != task.protocol_sha256:
        raise RuntimeError("task protocol hash differs from verified protocol")
    if git_commit(workspace_root) != task.code_commit:
        raise RuntimeError("current Git commit differs from the frozen run matrix")
    if task.development_input_run_ids:
        raise RuntimeError("formal tasks cannot consume development run IDs")
    if task.group == "F" and task.test_access != "locked_final_once":
        raise RuntimeError("HPO must expose test only after the configuration lock")


def _test_access_count(group: str, result: dict[str, Any]) -> int:
    if group == "A":
        return 0
    if group in {"B", "E", "F"}:
        return int(result["test_evaluation_count"])
    if group == "C":
        return sum(
            int(subrun["test_evaluation_count"])
            for subrun in result["subruns"].values()
        )
    if group == "D":
        return 2 * int(result["test_evaluation_count_per_arm"])
    raise ValueError(f"cannot audit test access for group {group}")


def execute_formal_task(
    *,
    workspace_root: Path,
    run_id: str,
    protocol_path: Path,
    protocol_checksum_path: Path,
    matrix_path: Path,
    matrix_checksum_path: Path,
    output_root: Path,
) -> FormalRunRecord:
    """Execute one unique task, retaining structured evidence on every failure."""
    matrix = _load_verified_matrix(matrix_path, matrix_checksum_path)
    task = _task(matrix, run_id)
    audit = FormalRunAudit(task, output_root)
    (audit.run_dir / "task.json").write_text(
        task.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        _preflight(
            workspace_root=workspace_root,
            task=task,
            protocol_path=protocol_path,
            protocol_checksum_path=protocol_checksum_path,
        )
        protocol = load_protocol(protocol_path)
        audit.start()
        result: dict[str, Any]
        if task.group == "A":
            validation = run_environment_validation(task.method)
            result = validation.model_dump(mode="json")
        elif task.group == "B":
            result = run_group_b(
                protocol=protocol,
                workspace_root=workspace_root,
                method=task.method,
                seed=task.seed,
                run_dir=audit.run_dir,
            )
        elif task.group == "C":
            result = run_group_c(
                protocol=protocol,
                workspace_root=workspace_root,
                method=task.method,
                seed=task.seed,
                run_dir=audit.run_dir,
            )
        elif task.group == "D":
            result = run_group_d(
                protocol=protocol,
                workspace_root=workspace_root,
                method=task.method,
                seed=task.seed,
                run_dir=audit.run_dir,
            )
        elif task.group == "E":
            result = run_group_e(
                protocol=protocol,
                workspace_root=workspace_root,
                method=task.method,
                seed=task.seed,
                run_dir=audit.run_dir,
            )
        elif task.group == "F":
            result = run_group_f(
                protocol=protocol,
                workspace_root=workspace_root,
                method=task.method,
                seed=task.seed,
                run_dir=audit.run_dir,
            )
        else:
            raise NotImplementedError(
                f"formal executor for Group {task.group} is not yet enabled"
            )
        (audit.run_dir / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        test_count = _test_access_count(task.group, result)
        test_authorized = task.test_access == "locked_final_once"
        locks = tuple(audit.run_dir.rglob("configuration_lock.json"))
        network_accessed = bool(result.get("provider_network_used", False))
        return audit.complete(
            test_partition_accessed=test_count > 0,
            test_partition_access_count=test_count,
            test_access_authorized=test_authorized,
            configuration_lock_present_before_test=(
                test_count == 0 or bool(locks)
            ),
            network_accessed=network_accessed,
            network_access_authorized=(
                network_accessed
                and task.group == "E"
                and protocol.agents.network_access == "provider_only"
            ),
            account_state_mutated_externally=bool(
                result.get("account_state_mutated_externally", False)
            ),
        )
    except BaseException as error:
        audit.fail(error)
        raise

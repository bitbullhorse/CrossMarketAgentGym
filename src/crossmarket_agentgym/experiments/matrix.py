"""Deterministic Phase 12 run-matrix construction."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from crossmarket_agentgym.experiments.models import FormalExperimentProtocol
from crossmarket_agentgym.experiments.protocol import load_protocol, sha256_file

RunGroup = Literal["A", "B", "C", "D", "E", "F"]
RunStatus = Literal["planned", "running", "completed", "failed", "blocked"]


class FormalTask(BaseModel):
    """One append-only formal experiment task declaration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(
        pattern=r"^p12(?:v[234]|v4m5)?-[A-F]-[a-z0-9_]+-s[0-9]+$"
    )
    group: RunGroup
    method: str = Field(min_length=1)
    required_metrics: tuple[str, ...]
    seed: int = Field(ge=0)
    protocol_id: Literal[
        "protocol-v1",
        "protocol-v2",
        "protocol-v3",
        "protocol-v4",
    ]
    protocol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    code_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    formal: Literal[True] = True
    development_input_run_ids: tuple[()] = ()
    allowed_selection_partitions: tuple[str, ...]
    test_access: Literal["none", "locked_final_once"]
    objective_seeds: tuple[int, ...]
    walk_forward_folds: tuple[str, ...]

    @model_validator(mode="after")
    def validate_partition_access(self) -> FormalTask:
        """Keep search/model-selection tasks away from the test partition."""
        if self.group == "F" and self.allowed_selection_partitions != (
            "train",
            "validation",
        ):
            raise ValueError("HPO may select only with train and validation")
        if "test" in self.allowed_selection_partitions:
            raise ValueError("test cannot be a model-selection partition")
        return self


class FormalRunMatrix(BaseModel):
    """Frozen complete task matrix for Groups A–F."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    matrix_id: Literal[
        "phase12-run-matrix-v1",
        "phase12-run-matrix-v2",
        "phase12-run-matrix-v3",
        "phase12-run-matrix-v4",
        "phase12-run-matrix-v5",
    ]
    protocol_id: Literal[
        "protocol-v1",
        "protocol-v2",
        "protocol-v3",
        "protocol-v4",
    ]
    protocol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    code_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    tasks: tuple[FormalTask, ...]

    @model_validator(mode="after")
    def validate_unique_runs(self) -> FormalRunMatrix:
        """Reject missing groups and duplicate run identities."""
        run_ids = tuple(task.run_id for task in self.tasks)
        if len(run_ids) != len(set(run_ids)):
            raise ValueError("formal run IDs must be unique")
        if tuple(sorted({task.group for task in self.tasks})) != (
            "A",
            "B",
            "C",
            "D",
            "E",
            "F",
        ):
            raise ValueError("formal run matrix must contain Groups A–F")
        return self


def git_commit(workspace_root: Path) -> str:
    """Return the exact tracked source identity used by a formal run."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _safe_method(value: str) -> str:
    normalized = (
        value.lower()
        .replace("+", "_")
        .replace("→", "_to_")
        .replace("-", "_")
        .replace(" ", "_")
    )
    return "".join(character for character in normalized if character.isalnum() or character == "_")


def build_run_matrix(
    protocol: FormalExperimentProtocol,
    *,
    protocol_sha256: str,
    code_commit: str,
    matrix_revision: Literal[4, 5] = 5,
) -> FormalRunMatrix:
    """Expand the frozen groups into deterministic run/seed declarations."""
    tasks: list[FormalTask] = []
    run_prefix = {
        "protocol-v1": "p12",
        "protocol-v2": "p12v2",
        "protocol-v3": "p12v3",
        "protocol-v4": "p12v4m5" if matrix_revision == 5 else "p12v4",
    }[protocol.protocol_id]
    folds = tuple(fold.fold_id for fold in protocol.partitions.walk_forward)
    for group in protocol.groups:
        seeds = (0,) if group.code == "A" else protocol.compute.seeds
        for method in group.methods:
            for seed in seeds:
                selection = (
                    ("train", "validation")
                    if group.code in {"B", "C", "D", "E", "F"}
                    else ("train",)
                )
                test_access: Literal["none", "locked_final_once"] = (
                    "locked_final_once" if group.code in {"B", "C", "D", "E", "F"} else "none"
                )
                tasks.append(
                    FormalTask(
                        run_id=f"{run_prefix}-{group.code}-{_safe_method(method)}-s{seed}",
                        group=group.code,
                        method=method,
                        required_metrics=group.required_metrics,
                        seed=seed,
                        protocol_id=protocol.protocol_id,
                        protocol_sha256=protocol_sha256,
                        dataset_manifest_sha256=protocol.dataset.processed_manifest_sha256,
                        code_commit=code_commit,
                        allowed_selection_partitions=selection,
                        test_access=test_access,
                        objective_seeds=(seed,),
                        walk_forward_folds=folds if group.code == "F" else (),
                    )
                )
    matrix_id: Literal[
        "phase12-run-matrix-v1",
        "phase12-run-matrix-v2",
        "phase12-run-matrix-v3",
        "phase12-run-matrix-v4",
        "phase12-run-matrix-v5",
    ]
    if protocol.protocol_id == "protocol-v1":
        matrix_id = "phase12-run-matrix-v1"
    elif protocol.protocol_id == "protocol-v2":
        matrix_id = "phase12-run-matrix-v2"
    elif protocol.protocol_id == "protocol-v3":
        matrix_id = "phase12-run-matrix-v3"
    else:
        matrix_id = (
            "phase12-run-matrix-v5"
            if matrix_revision == 5
            else "phase12-run-matrix-v4"
        )
    return FormalRunMatrix(
        matrix_id=matrix_id,
        protocol_id=protocol.protocol_id,
        protocol_sha256=protocol_sha256,
        dataset_manifest_sha256=protocol.dataset.processed_manifest_sha256,
        code_commit=code_commit,
        tasks=tuple(tasks),
    )


def freeze_run_matrix(
    *,
    workspace_root: Path,
    protocol_path: Path,
    protocol_checksum_path: Path,
    output_path: Path,
    checksum_path: Path,
    matrix_revision: Literal[4, 5] = 5,
) -> FormalRunMatrix:
    """Write the complete matrix once; subsequent work must use a new version."""
    if output_path.exists() or checksum_path.exists():
        raise FileExistsError("formal run matrix is immutable; create a new matrix version")
    protocol = load_protocol(protocol_path)
    if protocol.status != "frozen":
        raise ValueError("formal run matrix requires a frozen protocol")
    protocol_sha = sha256_file(protocol_path)
    checksum_text = protocol_checksum_path.read_text(encoding="utf-8").split()
    if not checksum_text or checksum_text[0] != protocol_sha:
        raise ValueError("protocol checksum is invalid")
    matrix = build_run_matrix(
        protocol,
        protocol_sha256=protocol_sha,
        code_commit=git_commit(workspace_root),
        matrix_revision=matrix_revision,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(matrix.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    digest = sha256_file(output_path)
    checksum_path.write_text(f"{digest}  {output_path.name}\n", encoding="utf-8")
    return matrix


def load_run_matrix(path: Path) -> FormalRunMatrix:
    """Load a strict formal run matrix."""
    return FormalRunMatrix.model_validate_json(path.read_text(encoding="utf-8"))

"""Versioned, credential-free manifest for every persisted run directory."""

from __future__ import annotations

import hashlib
import os
import platform
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from crossmarket_agentgym import __version__

RunKind = Literal["training", "tuning", "agent", "phase7"]
SourceState = Literal["clean", "dirty", "unknown"]
_COMMIT = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")


class RunArtifactRecord(BaseModel):
    """One immutable file identity inside a run directory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class RuntimeIdentity(BaseModel):
    """Portable runtime facts that contain no username or absolute path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    python: str
    implementation: str
    system: str
    machine: str
    cpu_count: int | None = Field(default=None, ge=1)


class RunManifest(BaseModel):
    """Frozen Phase 10 run-directory envelope shared by all workflows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    kind: RunKind
    software_version: str
    code_commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
    source_state: SourceState
    created_at: datetime
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    protocol_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    seed: int | None = Field(default=None, ge=0)
    status: Literal["completed", "failed"]
    runtime: RuntimeIdentity
    artifacts: tuple[RunArtifactRecord, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit(workspace: Path) -> str | None:
    configured = os.environ.get("CMAG_CODE_COMMIT", "").strip().lower()
    if configured:
        if _COMMIT.fullmatch(configured) is None:
            raise ValueError("CMAG_CODE_COMMIT must be a 40- or 64-character hex digest")
        return configured
    git_path = workspace / ".git"
    if not git_path.is_dir():
        return None
    head = (git_path / "HEAD").read_text(encoding="utf-8").strip()
    if _COMMIT.fullmatch(head) is not None:
        return head
    if not head.startswith("ref: "):
        return None
    reference = head.removeprefix("ref: ").strip()
    candidate = (git_path / reference).resolve()
    if candidate.is_relative_to(git_path.resolve()) and candidate.is_file():
        value = candidate.read_text(encoding="utf-8").strip().lower()
        return value if _COMMIT.fullmatch(value) is not None else None
    packed = git_path / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or line.startswith("^") or not line.strip():
                continue
            value, name = line.split(" ", maxsplit=1)
            if name == reference and _COMMIT.fullmatch(value) is not None:
                return value
    return None


def _source_state() -> SourceState:
    value = os.environ.get("CMAG_SOURCE_STATE", "unknown").strip().lower()
    if value not in {"clean", "dirty", "unknown"}:
        raise ValueError("CMAG_SOURCE_STATE must be clean, dirty, or unknown")
    return cast(SourceState, value)


def write_run_manifest(
    run_dir: str | Path,
    *,
    workspace_root: str | Path,
    run_id: str,
    kind: RunKind,
    config_path: str | Path,
    dataset_sha256: str | None = None,
    seed: int | None = None,
    protocol_sha256: str | None = None,
    status: Literal["completed", "failed"] = "completed",
) -> RunManifest:
    """Hash one completed run without copying prompts, outputs, or credentials."""
    root = Path(run_dir).resolve()
    workspace = Path(workspace_root).resolve()
    config = Path(config_path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    if not config.is_file() or not config.is_relative_to(root):
        raise ValueError("resolved configuration must be a file inside the run directory")
    artifacts = tuple(
        RunArtifactRecord(
            relative_path=path.relative_to(root).as_posix(),
            sha256=_sha256(path),
            size_bytes=path.stat().st_size,
        )
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix())
        if path.is_file()
        and path.name != "run_manifest.json"
        and not path.name.endswith(("-wal", "-shm", ".tmp"))
    )
    identity = RuntimeIdentity(
        python=platform.python_version(),
        implementation=platform.python_implementation(),
        system=platform.system(),
        machine=platform.machine() or "unknown",
        cpu_count=os.cpu_count(),
    )
    manifest = RunManifest(
        run_id=run_id,
        kind=kind,
        software_version=__version__,
        code_commit=_git_commit(workspace),
        source_state=_source_state(),
        created_at=datetime.now(UTC),
        config_sha256=_sha256(config),
        dataset_sha256=dataset_sha256,
        protocol_sha256=protocol_sha256,
        seed=seed,
        status=status,
        runtime=identity,
        artifacts=artifacts,
    )
    (root / "run_manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def verify_run_manifest(run_dir: str | Path) -> RunManifest:
    """Recompute every recorded file identity and reject missing or extra artifacts."""
    root = Path(run_dir).resolve()
    manifest_path = root / "run_manifest.json"
    manifest = RunManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    actual = {
        path.relative_to(root).as_posix(): (_sha256(path), path.stat().st_size)
        for path in root.rglob("*")
        if path.is_file()
        and path.name != "run_manifest.json"
        and not path.name.endswith(("-wal", "-shm", ".tmp"))
    }
    expected = {
        item.relative_path: (item.sha256, item.size_bytes)
        for item in manifest.artifacts
    }
    if actual != expected:
        raise ValueError("run manifest artifact set or digest mismatch")
    return manifest

"""Load, freeze, and verify a Phase 12 formal-experiment protocol."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from crossmarket_agentgym.experiments.models import (
    FormalExperimentProtocol,
    ProtocolVerification,
)


def sha256_file(path: Path) -> str:
    """Hash a file as immutable protocol evidence."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_protocol(path: str | Path) -> FormalExperimentProtocol:
    """Load strict UTF-8 YAML without resolving paths against the host."""
    path = Path(path)
    with path.open(encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise TypeError("formal experiment protocol root must be a mapping")
    return FormalExperimentProtocol.model_validate(raw)


def freeze_protocol(
    protocol_path: Path,
    checksum_path: Path,
    *,
    overwrite: bool = False,
) -> str:
    """Validate and write one checksum; frozen sidecars are immutable by default."""
    protocol = load_protocol(protocol_path)
    if protocol.status != "frozen":
        raise ValueError("only a protocol with status=frozen may receive a checksum")
    if checksum_path.exists() and not overwrite:
        raise FileExistsError(
            f"protocol checksum already exists; create a new protocol version: {checksum_path}"
        )
    digest = sha256_file(protocol_path)
    checksum_path.parent.mkdir(parents=True, exist_ok=True)
    checksum_path.write_text(
        f"{digest}  {protocol_path.name}\n",
        encoding="utf-8",
    )
    return digest


def _read_checksum(checksum_path: Path, protocol_path: Path) -> str:
    text = checksum_path.read_text(encoding="utf-8").strip()
    fields = text.split()
    if len(fields) != 2 or fields[1] != protocol_path.name:
        raise ValueError("protocol checksum must contain '<sha256>  <protocol filename>'")
    digest = fields[0]
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ValueError("protocol checksum is not a lower-case SHA-256")
    return digest


def verify_protocol(
    protocol_path: Path,
    checksum_path: Path,
    *,
    workspace_root: Path,
) -> ProtocolVerification:
    """Verify schema, checksum, source inventory, and processed-data readiness."""
    protocol = load_protocol(protocol_path)
    expected = _read_checksum(checksum_path, protocol_path)
    actual = sha256_file(protocol_path)
    blockers: list[str] = []
    if protocol.status != "frozen":
        blockers.append("PROTOCOL_NOT_FROZEN")
    checksum_valid = expected == actual
    if not checksum_valid:
        blockers.append("PROTOCOL_HASH_MISMATCH")

    inventory_path = workspace_root / protocol.dataset.source_inventory
    inventory_valid = inventory_path.is_file()
    if inventory_valid:
        inventory_valid = sha256_file(inventory_path) == protocol.dataset.source_inventory_sha256
    if not inventory_valid:
        blockers.append("SOURCE_INVENTORY_MISSING_OR_CHANGED")

    fx_snapshot_path = workspace_root / protocol.fx.raw_snapshot
    fx_snapshot_valid = fx_snapshot_path.is_file()
    if fx_snapshot_valid:
        fx_snapshot_valid = sha256_file(fx_snapshot_path) == protocol.fx.raw_snapshot_sha256
    if not fx_snapshot_valid:
        blockers.append("FX_SNAPSHOT_MISSING_OR_CHANGED")

    manifest_path = workspace_root / protocol.dataset.processed_manifest
    manifest_present = manifest_path.is_file()
    if not manifest_present:
        blockers.append("PROCESSED_DATASET_NOT_BUILT")
    manifest_valid = manifest_present
    if manifest_valid:
        manifest_valid = (
            sha256_file(manifest_path) == protocol.dataset.processed_manifest_sha256
        )
    if manifest_present and not manifest_valid:
        blockers.append("PROCESSED_DATASET_MANIFEST_CHANGED")

    prompt_path = (
        workspace_root / protocol.agents.prompt_source
        if protocol.agents.prompt_source is not None
        else None
    )
    prompt_source_valid = prompt_path is not None and prompt_path.is_file()
    if prompt_source_valid and prompt_path is not None:
        prompt_source_valid = (
            sha256_file(prompt_path) == protocol.agents.prompt_source_sha256
        )
    if not prompt_source_valid:
        blockers.append("PROMPT_SOURCE_MISSING_OR_CHANGED")

    return ProtocolVerification(
        protocol_id=protocol.protocol_id,
        protocol_path=protocol_path.as_posix(),
        checksum_path=checksum_path.as_posix(),
        protocol_sha256=actual,
        schema_valid=True,
        checksum_valid=checksum_valid,
        source_inventory_valid=inventory_valid,
        fx_snapshot_valid=fx_snapshot_valid,
        processed_manifest_present=manifest_present,
        processed_manifest_valid=manifest_valid,
        prompt_source_valid=prompt_source_valid,
        is_ready_to_execute=not blockers,
        blockers=tuple(blockers),
    )

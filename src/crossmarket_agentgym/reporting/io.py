"""Bounded filesystem and JSON helpers for report inputs."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, NoReturn


def resolve_inside(path: str | Path, root: Path) -> Path:
    """Resolve a path under an already-resolved root."""
    candidate = Path(path)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if not resolved.is_relative_to(root):
        raise PermissionError("report path leaves configured workspace")
    return resolved


def _reject_constant(value: str) -> NoReturn:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def read_bounded_json(path: Path, *, max_bytes: int) -> Any:
    """Read strict JSON with a size bound and no NaN/Infinity extension."""
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(f"JSON artifact exceeds {max_bytes} byte limit")
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_constant,
    )


def finite_metrics(value: object) -> dict[str, float]:
    """Keep a flat finite numeric metric mapping and reject booleans."""
    if not isinstance(value, dict):
        return {}
    metrics: dict[str, float] = {}
    for key, item in value.items():
        if isinstance(item, bool) or not isinstance(item, int | float):
            continue
        number = float(item)
        if not math.isfinite(number):
            raise ValueError(f"metric {key!r} is non-finite")
        metrics[str(key)] = number
    return metrics


def sha256_file(path: Path) -> str:
    """Hash one artifact without interpreting its contents."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def combined_sha256(paths: list[Path], *, root: Path) -> str:
    """Hash sorted relative names and file digests to bind provenance."""
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(sha256_file(path).encode())
        digest.update(b"\n")
    return digest.hexdigest()


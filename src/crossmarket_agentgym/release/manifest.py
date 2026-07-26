"""Deterministic distribution provenance generation."""

from __future__ import annotations

import hashlib
import os
import platform
from pathlib import Path

from crossmarket_agentgym import __version__
from crossmarket_agentgym.release.models import (
    DistributionArtifact,
    DistributionManifest,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_release_manifest(dist_dir: str | Path) -> DistributionManifest:
    """Hash built wheels and source archives without publishing them."""
    root = Path(dist_dir).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    paths = sorted(
        (
            path
            for path in root.iterdir()
            if path.is_file()
            and path.name != "release-manifest.json"
            and path.suffix in {".whl", ".gz", ".zip"}
        ),
        key=lambda item: item.name,
    )
    if not paths:
        raise ValueError("distribution directory contains no wheel or source archive")
    epoch_text = os.environ.get("SOURCE_DATE_EPOCH")
    epoch = int(epoch_text) if epoch_text is not None else None
    manifest = DistributionManifest(
        version=__version__,
        python=platform.python_version(),
        platform=platform.platform(),
        source_date_epoch=epoch,
        artifacts=tuple(
            DistributionArtifact(
                filename=path.name,
                sha256=_sha256(path),
                size_bytes=path.stat().st_size,
            )
            for path in paths
        ),
    )
    (root / "release-manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest

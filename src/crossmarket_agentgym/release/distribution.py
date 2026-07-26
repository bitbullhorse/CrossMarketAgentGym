"""Inspect built archives without installing or publishing them."""

from __future__ import annotations

import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path, PurePosixPath

from crossmarket_agentgym import __version__
from crossmarket_agentgym.release.models import (
    DistributionVerificationResult,
    VerificationCheck,
)

_WHEEL_REQUIRED = (
    "crossmarket_agentgym/_version.py",
    "crossmarket_agentgym/py.typed",
    "crossmarket_agentgym/resources/configs/env/cross_market.yaml",
    "crossmarket_agentgym/resources/configs/env/sample_cross_market.yaml",
    "crossmarket_agentgym/resources/data/sample/dataset_manifest.json",
    "crossmarket_agentgym/resources/release/api_inventory.csv",
    "crossmarket_agentgym/resources/schemas/rc1/checksums.json",
)
_SDIST_REQUIRED = (
    "README.md",
    "CITATION.cff",
    "LICENSE",
    "constraints-cpu.txt",
    "environment-cpu.yml",
    "pyproject.toml",
    "paper/softwarex-paper-outline.md",
    "release/api_inventory.csv",
    "schemas/rc1/checksums.json",
    "scripts/verify_release.sh",
    "uv.lock",
)
_FORBIDDEN_ANY_COMPONENT = frozenset(
    {
        ".env",
        ".git",
        ".venv",
        "stock_data",
    }
)
_FORBIDDEN_TOP_LEVEL = frozenset({"reports", "runs"})


def _check(name: str, passed: bool, detail: str) -> VerificationCheck:
    return VerificationCheck(name=name, passed=passed, detail=detail)


def _forbidden(
    names: list[str],
    *,
    strip_archive_root: bool = False,
) -> list[str]:
    offenders: list[str] = []
    for name in names:
        parts = tuple(item.lower() for item in PurePosixPath(name).parts)
        content_parts = parts[1:] if strip_archive_root else parts
        has_forbidden_component = bool(set(content_parts) & _FORBIDDEN_ANY_COMPONENT)
        has_forbidden_top_level = bool(
            content_parts and content_parts[0] in _FORBIDDEN_TOP_LEVEL
        )
        if has_forbidden_component or has_forbidden_top_level:
            offenders.append(name)
    return offenders


def _specifier_parts(value: str | None) -> frozenset[str]:
    if value is None:
        return frozenset()
    return frozenset(part.strip() for part in value.split(",") if part.strip())


def verify_distributions(
    dist_dir: str | Path,
) -> DistributionVerificationResult:
    """Verify metadata, packaged quickstart assets, and archive exclusions."""
    root = Path(dist_dir).resolve()
    wheels = sorted(root.glob("*.whl"))
    sdists = sorted(root.glob("*.tar.gz"))
    checks: list[VerificationCheck] = [
        _check(
            "distribution_count",
            len(wheels) == 1 and len(sdists) == 1,
            f"found {len(wheels)} wheel(s) and {len(sdists)} source archive(s)",
        )
    ]
    if len(wheels) != 1 or len(sdists) != 1:
        return DistributionVerificationResult(
            version=__version__,
            is_valid=False,
            checks=tuple(checks),
        )

    with zipfile.ZipFile(wheels[0]) as archive:
        wheel_names = archive.namelist()
        metadata_names = [
            name for name in wheel_names if name.endswith(".dist-info/METADATA")
        ]
        metadata_text = (
            archive.read(metadata_names[0]).decode("utf-8")
            if len(metadata_names) == 1
            else ""
        )
    metadata = Parser().parsestr(metadata_text)
    metadata_valid = (
        metadata.get("Name") == "crossmarket-agent-gym"
        and metadata.get("Version") == __version__
        and _specifier_parts(metadata.get("Requires-Python"))
        == frozenset({">=3.11", "<3.13"})
    )
    checks.append(
        _check(
            "wheel_metadata",
            metadata_valid,
            "wheel name, version, and Python requirement agree",
        )
    )
    missing_wheel = [item for item in _WHEEL_REQUIRED if item not in wheel_names]
    checks.append(
        _check(
            "wheel_resources",
            not missing_wheel,
            "packaged config, sample manifest, typing marker, and version present"
            if not missing_wheel
            else f"missing: {missing_wheel}",
        )
    )
    wheel_forbidden = _forbidden(wheel_names)
    checks.append(
        _check(
            "wheel_exclusions",
            not wheel_forbidden,
            "wheel contains no local-only path"
            if not wheel_forbidden
            else f"forbidden paths: {wheel_forbidden[:10]}",
        )
    )

    with tarfile.open(sdists[0], "r:gz") as archive:
        sdist_names = archive.getnames()
    stripped = [
        "/".join(PurePosixPath(name).parts[1:])
        for name in sdist_names
        if len(PurePosixPath(name).parts) > 1
    ]
    missing_sdist = [item for item in _SDIST_REQUIRED if item not in stripped]
    checks.append(
        _check(
            "sdist_resources",
            not missing_sdist,
            "source documentation, citation, license, metadata, and paper present"
            if not missing_sdist
            else f"missing: {missing_sdist}",
        )
    )
    sdist_forbidden = _forbidden(sdist_names, strip_archive_root=True)
    checks.append(
        _check(
            "sdist_exclusions",
            not sdist_forbidden,
            "source archive contains no local-only path"
            if not sdist_forbidden
            else f"forbidden paths: {sdist_forbidden[:10]}",
        )
    )
    return DistributionVerificationResult(
        version=__version__,
        is_valid=all(item.passed for item in checks),
        checks=tuple(checks),
    )

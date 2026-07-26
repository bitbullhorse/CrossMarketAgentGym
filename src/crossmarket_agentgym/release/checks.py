"""Conservative local checks required before an external release."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

import yaml

from crossmarket_agentgym import __version__
from crossmarket_agentgym.release.models import (
    ReleaseReadinessResult,
    VerificationCheck,
)

_SECRET_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
_REQUIRED_FILES = (
    "README.md",
    "LICENSE",
    "CITATION.cff",
    ".zenodo.json",
    "Dockerfile",
    ".dockerignore",
    "SECURITY.md",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    "docs/api-reference.md",
    "docs/cli-reference.md",
    "docs/release.md",
    "paper/README.md",
    "paper/softwarex-paper-outline.md",
    "paper/artifact-map.md",
)


def _check(name: str, passed: bool, detail: str) -> VerificationCheck:
    return VerificationCheck(name=name, passed=passed, detail=detail)


def _project_metadata(root: Path) -> dict[str, Any]:
    with (root / "pyproject.toml").open("rb") as stream:
        raw = tomllib.load(stream)
    project = raw.get("project")
    if not isinstance(project, dict):
        raise TypeError("pyproject project metadata is missing")
    return project


def _secret_offenders(root: Path) -> list[str]:
    offenders: list[str] = []
    candidates = (
        root / "src",
        root / "configs",
        root / "docs",
        root / "paper",
    )
    suffixes = {".py", ".md", ".yaml", ".yml", ".toml", ".json"}
    for candidate in candidates:
        if not candidate.exists():
            continue
        for path in candidate.rglob("*"):
            if path.is_file() and path.suffix.lower() in suffixes:
                text = path.read_text(encoding="utf-8")
                if _SECRET_PATTERN.search(text) is not None:
                    offenders.append(path.relative_to(root).as_posix())
    return sorted(offenders)


def check_release_readiness(
    workspace_root: str | Path = ".",
) -> ReleaseReadinessResult:
    """Validate local release assets without uploading or tagging anything."""
    root = Path(workspace_root).resolve()
    checks: list[VerificationCheck] = []
    missing = [item for item in _REQUIRED_FILES if not (root / item).is_file()]
    checks.append(
        _check(
            "required_release_files",
            not missing,
            "all required files present" if not missing else f"missing: {missing}",
        )
    )

    try:
        project = _project_metadata(root)
        urls = project.get("urls", {})
        metadata_valid = (
            project.get("name") == "crossmarket-agent-gym"
            and project.get("requires-python") == ">=3.11,<3.13"
            and "version" in project.get("dynamic", [])
            and isinstance(urls, dict)
            and {"Documentation", "Issues", "Source"} <= set(urls)
        )
    except (FileNotFoundError, TypeError, tomllib.TOMLDecodeError) as error:
        metadata_valid = False
        metadata_detail = str(error)
    else:
        metadata_detail = "PEP 621 name, dynamic version, Python range, and URLs agree"
    checks.append(_check("pypi_metadata", metadata_valid, metadata_detail))

    stable_version = re.fullmatch(r"\d+\.\d+\.\d+", __version__) is not None
    checks.append(
        _check(
            "stable_version",
            stable_version,
            f"package version is {__version__}",
        )
    )

    try:
        citation = yaml.safe_load((root / "CITATION.cff").read_text(encoding="utf-8"))
        zenodo = json.loads((root / ".zenodo.json").read_text(encoding="utf-8"))
        citation_version = str(citation.get("version")) if isinstance(citation, dict) else ""
        zenodo_version = str(zenodo.get("version")) if isinstance(zenodo, dict) else ""
        citation_valid = citation_version == __version__ == zenodo_version
    except (FileNotFoundError, json.JSONDecodeError, yaml.YAMLError) as error:
        citation_valid = False
        citation_detail = str(error)
    else:
        citation_detail = (
            f"CITATION.cff and Zenodo metadata both declare {__version__}"
        )
    checks.append(_check("citation_version", citation_valid, citation_detail))

    docker_path = root / "Dockerfile"
    docker_text = (
        docker_path.read_text(encoding="utf-8") if docker_path.is_file() else ""
    )
    docker_valid = (
        "USER cmag" in docker_text
        and "ENTRYPOINT [\"cmag\"]" in docker_text
        and "COPY . /workspace" not in docker_text
    )
    checks.append(
        _check(
            "docker_boundary",
            docker_valid,
            "non-root runtime, cmag entrypoint, and bounded build inputs",
        )
    )

    offenders = _secret_offenders(root)
    checks.append(
        _check(
            "credential_scan",
            not offenders,
            "no API-key-shaped value found"
            if not offenders
            else f"credential-shaped values: {offenders}",
        )
    )

    readme_path = root / "README.md"
    readme = readme_path.read_text(encoding="utf-8") if readme_path.is_file() else ""
    readme_valid = all(
        token in readme
        for token in (
            "pip install",
            "cmag quickstart",
            "cmag reproduce",
            "CITATION.cff",
            "Non-negotiable safety boundaries",
        )
    )
    checks.append(
        _check(
            "readme_release_sections",
            readme_valid,
            "installation, quickstart, reproduction, citation, and safety documented",
        )
    )
    return ReleaseReadinessResult(
        version=__version__,
        is_ready=all(item.passed for item in checks),
        checks=tuple(checks),
    )

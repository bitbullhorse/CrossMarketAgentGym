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
from crossmarket_agentgym.release.versioning import release_label, release_tag

_SECRET_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
_REQUIRED_FILES = (
    "README.md",
    "DATA_LICENSE.md",
    "LICENSE",
    "CITATION.cff",
    ".zenodo.json",
    "Dockerfile",
    ".dockerignore",
    "SECURITY.md",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    ".github/workflows/phase11-linux-cpu.yml",
    ".github/workflows/phase11-docker.yml",
    "constraints-cpu.txt",
    "constraints-gpu.txt",
    "environment-cpu.yml",
    "environment-gpu.yml",
    "uv.lock",
    "release/rc1_checklist.md",
    "release/rc2_checklist.md",
    "release/api_inventory.csv",
    "release/cli_inventory.json",
    "release/config_schema_inventory.csv",
    "release/format_registry.json",
    "release/known_issues.md",
    "release/compatibility_matrix.md",
    "release/release_notes_v1.0.0-rc1.md",
    "release/release_notes_v1.0.0-rc2.md",
    "release/release_notes_v1.0.0.md",
    "release/release_manifest_v1.0.0.json",
    "release/release_manifest_v1.0.0.sha256",
    "release/release_blockers.md",
    "schemas/rc1/checksums.json",
    "scripts/build_release.sh",
    "scripts/verify_release.sh",
    "scripts/create_clean_env_test.sh",
    "scripts/verify_reproducible_build.py",
    "scripts/run_phase11_tasks.py",
    "scripts/verify_phase11_distribution.py",
    "scripts/build_phase11_release_evidence.py",
    "scripts/create_archive.sh",
    "scripts/create_release_archive.py",
    "scripts/create_stable_release_manifest.py",
    "scripts/publish_docker.sh",
    "scripts/publish_pypi.sh",
    "scripts/verify_public_release.sh",
    "scripts/verify_public_release.py",
    "scripts/build_versioned_docs.py",
    "mkdocs.yml",
    "docs/api-reference.md",
    "docs/api_stability.md",
    "docs/cli-reference.md",
    "docs/deprecation_policy.md",
    "docs/installation.md",
    "docs/quickstart.md",
    "docs/release.md",
    "docs/reproducibility.md",
    "docs/stable-api.md",
    "docs/versioning_policy.md",
    "docs/issues/phase-11-checklist.md",
    "docs/issues/phase-14-checklist.md",
    "docs/phases/phase-11.md",
    "docs/phases/phase-14.md",
    "reproducibility_tests/protocol.md",
    "reproducibility_tests/independent_audit_attestation.md",
    "paper/README.md",
    "paper/softwarex-paper-outline.md",
    "paper/artifact-map.md",
)


def _check(name: str, passed: bool, detail: str) -> VerificationCheck:
    bounded = detail if len(detail) <= 1000 else detail[:997] + "..."
    return VerificationCheck(name=name, passed=passed, detail=bounded)


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

    try:
        public_version = release_label(__version__)
        expected_tag = release_tag(__version__)
    except ValueError as error:
        release_version_valid = False
        version_detail = str(error)
    else:
        release_version_valid = True
        version_detail = (
            f"package {__version__}; public label {public_version}; tag {expected_tag}"
        )
    checks.append(
        _check(
            "release_version",
            release_version_valid,
            version_detail,
        )
    )

    try:
        citation = yaml.safe_load((root / "CITATION.cff").read_text(encoding="utf-8"))
        zenodo = json.loads((root / ".zenodo.json").read_text(encoding="utf-8"))
        citation_version = str(citation.get("version")) if isinstance(citation, dict) else ""
        zenodo_version = str(zenodo.get("version")) if isinstance(zenodo, dict) else ""
        expected_metadata_version = release_label(__version__)
        citation_valid = (
            citation_version == expected_metadata_version == zenodo_version
        )
    except (FileNotFoundError, json.JSONDecodeError, yaml.YAMLError) as error:
        citation_valid = False
        citation_detail = str(error)
    else:
        citation_detail = (
            "CITATION.cff and Zenodo metadata both declare "
            f"{release_label(__version__)}"
        )
    checks.append(_check("citation_version", citation_valid, citation_detail))

    try:
        from crossmarket_agentgym.release.stable_manifest import (
            verify_stable_release_manifest,
        )

        stable_manifest_valid, stable_manifest_problems = (
            verify_stable_release_manifest(root)
        )
    except (OSError, TypeError, ValueError) as error:
        stable_manifest_valid = False
        stable_manifest_detail = str(error)
    else:
        stable_manifest_detail = (
            "stable release, benchmark-v1, protocol-v4, and dataset-manifest-v3 agree"
            if stable_manifest_valid
            else "; ".join(stable_manifest_problems)
        )
    checks.append(
        _check(
            "stable_release_manifest",
            stable_manifest_valid,
            stable_manifest_detail,
        )
    )

    docker_path = root / "Dockerfile"
    docker_text = (
        docker_path.read_text(encoding="utf-8") if docker_path.is_file() else ""
    )
    docker_valid = (
        "USER cmag" in docker_text
        and "ENTRYPOINT [\"cmag\"]" in docker_text
        and "/build/configs /workspace/configs" in docker_text
        and "/build/data/sample /workspace/data/sample" in docker_text
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
            "phase11-linux-cpu.yml/badge.svg",
            "phase11-docker.yml/badge.svg",
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

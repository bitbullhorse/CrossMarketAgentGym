from __future__ import annotations

import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from crossmarket_agentgym.cli.app import app
from crossmarket_agentgym.release import (
    build_release_manifest,
    check_release_readiness,
    run_cpu_quickstart,
    verify_distributions,
)
from crossmarket_agentgym.release.versioning import release_label, release_tag

PROJECT_ROOT = Path(__file__).parents[2]
runner = CliRunner()


def test_release_readiness_and_metadata_are_consistent() -> None:
    result = check_release_readiness(PROJECT_ROOT)
    assert result.is_ready is True
    assert result.version == "1.0.0rc2"
    assert result.external_publish_performed is False
    assert all(item.passed for item in result.checks)

    citation = yaml.safe_load(
        (PROJECT_ROOT / "CITATION.cff").read_text(encoding="utf-8")
    )
    zenodo = json.loads(
        (PROJECT_ROOT / ".zenodo.json").read_text(encoding="utf-8")
    )
    assert citation["version"] == zenodo["version"] == release_label(result.version)
    assert release_tag(result.version) == "v1.0.0-rc2"


def test_release_check_fails_closed_when_assets_are_missing(tmp_path: Path) -> None:
    result = check_release_readiness(tmp_path)
    assert result.is_ready is False
    assert any(
        item.name == "required_release_files" and not item.passed
        for item in result.checks
    )


def test_distribution_manifest_is_deterministic_and_bounded(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "crossmarket_agent_gym-1.0.0rc2.tar.gz").write_bytes(b"source")
    with zipfile.ZipFile(
        dist / "crossmarket_agent_gym-1.0.0rc2-py3-none-any.whl", "w"
    ) as wheel:
        wheel.writestr("METADATA", "Name: crossmarket-agent-gym")
    first = build_release_manifest(dist)
    first_text = (dist / "release-manifest.json").read_text(encoding="utf-8")
    second = build_release_manifest(dist)
    assert first == second
    assert (dist / "release-manifest.json").read_text(encoding="utf-8") == first_text
    assert [item.filename for item in first.artifacts] == [
        "crossmarket_agent_gym-1.0.0rc2-py3-none-any.whl",
        "crossmarket_agent_gym-1.0.0rc2.tar.gz",
    ]
    with pytest.raises(ValueError, match="no wheel"):
        build_release_manifest(tmp_path)


def test_distribution_verifier_requires_metadata_resources_and_exclusions(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel_path = dist / "crossmarket_agent_gym-1.0.0rc2-py3-none-any.whl"
    with zipfile.ZipFile(wheel_path, "w") as wheel:
        wheel.writestr("crossmarket_agentgym/_version.py", '__version__ = "1.0.0rc2"')
        wheel.writestr("crossmarket_agentgym/py.typed", "")
        wheel.writestr(
            "crossmarket_agentgym/resources/configs/env/cross_market.yaml",
            "dataset_root: data/sample",
        )
        wheel.writestr(
            "crossmarket_agentgym/resources/configs/env/sample_cross_market.yaml",
            "dataset_root: data/sample",
        )
        wheel.writestr(
            "crossmarket_agentgym/resources/data/sample/dataset_manifest.json",
            "{}",
        )
        wheel.writestr(
            "crossmarket_agentgym/resources/release/api_inventory.csv",
            "qualified_name\n",
        )
        wheel.writestr(
            "crossmarket_agentgym/resources/schemas/rc1/checksums.json",
            "{}",
        )
        wheel.writestr(
            "crossmarket_agentgym/tuning/reports/__init__.py",
            '"""Packaged HPO report module."""',
        )
        wheel.writestr(
            "crossmarket_agent_gym-1.0.0rc2.dist-info/METADATA",
            "Name: crossmarket-agent-gym\n"
            "Version: 1.0.0rc2\n"
            "Requires-Python: <3.13,>=3.11\n",
        )
    sdist_path = dist / "crossmarket_agent_gym-1.0.0rc2.tar.gz"
    with tarfile.open(sdist_path, "w:gz") as sdist:
        for name in (
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
            "src/crossmarket_agentgym/tuning/reports/__init__.py",
            "uv.lock",
        ):
            payload = b"fixture"
            info = tarfile.TarInfo(f"crossmarket_agent_gym-1.0.0rc2/{name}")
            info.size = len(payload)
            sdist.addfile(info, io.BytesIO(payload))
    verified = verify_distributions(dist)
    assert verified.is_valid is True

    with zipfile.ZipFile(wheel_path, "a") as wheel:
        wheel.writestr("runs/private.json", "{}")
    rejected = verify_distributions(dist)
    assert rejected.is_valid is False
    assert any(
        item.name == "wheel_exclusions" and not item.passed
        for item in rejected.checks
    )


def test_cpu_quickstart_and_release_cli_are_offline() -> None:
    summary = run_cpu_quickstart(PROJECT_ROOT, smoke_steps=8)
    assert summary.is_valid is True
    assert summary.data.markets == ["CN", "HK", "JP", "US"]
    assert summary.environment.smoke_steps == 8
    assert summary.network_used is False
    assert summary.llm_used is False

    release = runner.invoke(
        app,
        ["release", "check", "--workspace-root", str(PROJECT_ROOT)],
    )
    quickstart = runner.invoke(app, ["quickstart", "--smoke-steps", "4"])
    assert release.exit_code == 0
    assert '"external_publish_performed": false' in release.stdout
    assert quickstart.exit_code == 0
    assert '"llm_used": false' in quickstart.stdout

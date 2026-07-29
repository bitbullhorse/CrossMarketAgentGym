from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from crossmarket_agentgym.agents.layer_config import load_phase7_run_config
from crossmarket_agentgym.audit.run_manifest import (
    verify_run_manifest,
    write_run_manifest,
)
from crossmarket_agentgym.environments.checks import load_environment_check_config
from crossmarket_agentgym.release.freeze import verify_frozen_contracts
from crossmarket_agentgym.rl import load_train_run_config
from crossmarket_agentgym.tuning.config import load_tuning_run_config
from crossmarket_agentgym.tuning.store import SQLiteStudyStore

PROJECT_ROOT = Path(__file__).parents[2]


def test_phase10_frozen_contracts_match_code() -> None:
    result = verify_frozen_contracts(PROJECT_ROOT)
    assert result.is_valid is True
    assert result.wrote_files is False
    assert result.api_records >= 200
    assert result.config_schemas == 11
    assert result.artifact_schemas >= 20


def test_gitignore_does_not_hide_python_source_files() -> None:
    if shutil.which("git") is None or not (PROJECT_ROOT / ".git").exists():
        pytest.skip("source-ignore audit requires a Git worktree")
    source_files = sorted(
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in (PROJECT_ROOT / "src").rglob("*.py")
        if "__pycache__" not in path.parts
    )
    completed = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        cwd=PROJECT_ROOT,
        input="\n".join(source_files),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1, (
        "Python source files must never be hidden by .gitignore:\n"
        f"{completed.stdout}{completed.stderr}"
    )


def test_phase11_public_configs_are_strictly_loadable() -> None:
    load_environment_check_config(
        PROJECT_ROOT / "configs/env/sample_cross_market.yaml"
    )
    load_train_run_config(PROJECT_ROOT / "configs/train/ppo_quickstart.yaml")
    research = load_phase7_run_config(
        PROJECT_ROOT / "configs/agents/research_single_mock.yaml"
    )
    risk = load_phase7_run_config(
        PROJECT_ROOT / "configs/agents/risk_committee_mock.yaml"
    )
    tuning = load_tuning_run_config(
        PROJECT_ROOT / "configs/tune/ppo_pso_quickstart.yaml"
    )
    assert research.preset == "research_only"
    assert risk.preset == "risk_only"
    assert risk.layers.risk.team is not None
    assert sum(agent.count for agent in risk.layers.risk.team.agents) == 3
    assert tuning.searcher.type == "pso"
    assert tuning.scheduler.type == "asha"
    assert tuning.objective.budget_stage == "stage_a"


def test_run_manifest_detects_tampering_and_extra_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "runs" / "example"
    run_dir.mkdir(parents=True)
    config = run_dir / "resolved_config.json"
    config.write_text('{"seed": 17}\n', encoding="utf-8")
    artifact = run_dir / "metrics.json"
    artifact.write_text('{"selected_on": "validation"}\n', encoding="utf-8")
    monkeypatch.setenv("CMAG_CODE_COMMIT", "a" * 40)
    monkeypatch.setenv("CMAG_SOURCE_STATE", "clean")

    manifest = write_run_manifest(
        run_dir,
        workspace_root=tmp_path,
        run_id="example",
        kind="training",
        config_path=config,
        dataset_sha256="b" * 64,
        seed=17,
    )
    assert manifest.schema_version == "1.0"
    assert manifest.code_commit == "a" * 40
    assert manifest.source_state == "clean"
    assert verify_run_manifest(run_dir) == manifest

    artifact.write_text('{"selected_on": "test"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="artifact set or digest mismatch"):
        verify_run_manifest(run_dir)

    artifact.write_text('{"selected_on": "validation"}\n', encoding="utf-8")
    (run_dir / "unregistered.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact set or digest mismatch"):
        verify_run_manifest(run_dir)


def test_hpo_store_versions_legacy_database_and_rejects_future(
    tmp_path: Path,
) -> None:
    legacy_path = tmp_path / "legacy.sqlite3"
    with SQLiteStudyStore(legacy_path):
        pass
    with sqlite3.connect(legacy_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1

    future_path = tmp_path / "future.sqlite3"
    with sqlite3.connect(future_path) as connection:
        connection.execute("PRAGMA user_version = 2")
    with pytest.raises(RuntimeError, match="newer than this software"):
        SQLiteStudyStore(future_path)


def test_documentation_contract_passes_offline() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/verify_docs.py"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS documentation contract" in completed.stdout


def test_format_registry_versions_every_persisted_contract() -> None:
    registry = json.loads(
        (PROJECT_ROOT / "release/format_registry.json").read_text(encoding="utf-8")
    )
    assert registry["schema_version"] == "1.0"
    formats = {item["name"]: item for item in registry["formats"]}
    assert formats["hpo_sqlite"]["version"] == "1"
    assert formats["run_manifest"]["version"] == "1.0"
    assert all(item["version"] for item in formats.values())


def test_cli_inventory_covers_phase11_protocol() -> None:
    inventory_text = (
        PROJECT_ROOT / "release/cli_inventory.json"
    ).read_text(encoding="utf-8")
    inventory = json.loads(inventory_text)
    assert "\\\\" not in inventory_text, (
        "CLI path defaults must use platform-independent POSIX separators"
    )
    commands = {item["command"]: item for item in inventory["commands"]}
    assert inventory["schema_version"] == "1.0"
    assert {
        "cmag data validate",
        "cmag env check",
        "cmag train",
        "cmag agent run",
        "cmag tune",
        "cmag report",
        "cmag reproduce",
        "cmag release freeze",
    } <= set(commands)
    report_options = {
        option
        for parameter in commands["cmag report"]["parameters"]
        for option in parameter["options"]
    }
    assert "--run-id" in report_options
    reproduce_options = {
        option
        for parameter in commands["cmag reproduce"]["parameters"]
        for option in parameter["options"]
    }
    assert {
        "--run-id",
        "--verify-only",
        "--execute",
        "--compare",
        "--tolerance-config",
        "--replay-run-id",
    } <= reproduce_options


def test_stable_release_publish_requires_exact_tag_or_explicit_dispatch() -> None:
    workflow = (PROJECT_ROOT / ".github/workflows/release.yml").read_text(
        encoding="utf-8"
    )
    assert (
        '-e ".[dev,docs,legacy-data,release,rl,llm,service]"'
        in workflow
    )
    assert "github.ref == 'refs/tags/v1.0.0'" in workflow
    assert "inputs.publish_pypi" in workflow
    assert "inputs.publish_container" in workflow
    assert 'tags:\n      - "v1.0.0"' in workflow
    assert 'tags:\n      - "v*"' not in workflow
    assert workflow.count('--repo "$GITHUB_REPOSITORY"') == 1


def test_github_actions_use_node24_generations() -> None:
    workflows = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            PROJECT_ROOT / ".github/workflows/ci.yml",
            PROJECT_ROOT / ".github/workflows/release.yml",
        )
    )
    assert "actions/checkout@v7" in workflows
    assert "actions/setup-python@v6" in workflows
    assert "actions/upload-artifact@v7" in workflows
    assert "actions/checkout@v4" not in workflows
    assert "actions/setup-python@v5" not in workflows
    assert "actions/upload-artifact@v4" not in workflows

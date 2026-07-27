"""Phase 11 Linux/Docker workflow and permanent-evidence contracts."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from scripts.build_phase11_release_evidence import build_bundle
from scripts.run_phase11_tasks import phase11_tasks
from scripts.verify_phase11_distribution import verify_wheel


def test_task_b_i_protocol_is_complete_and_offline() -> None:
    tasks = phase11_tasks("cmag")

    assert tuple(item.task_id for item in tasks) == tuple("BCDEFGHI")
    assert tasks[0].commands[0].argv[-1] == "configs/data/sample.yaml"
    assert tasks[-1].commands[0].argv[-1] == "--verify-only"
    replay = tasks[-1].commands[1].argv
    assert "--execute" in replay
    assert "--compare" in replay
    assert "configs/reproduction/phase11_cpu.yaml" in replay


def test_linux_cpu_workflow_freezes_required_evidence_contract() -> None:
    text = Path(".github/workflows/phase11-linux-cpu.yml").read_text(
        encoding="utf-8"
    )

    for token in (
        "runs-on: ubuntu-24.04",
        "python -m build --wheel",
        "python -m venv .phase11-venv",
        "torch.cuda.is_available()",
        "actions/attest@v4",
        "id-token: write",
        "attestations: write",
        "artifact-metadata: write",
        "11_3_task_summary.json",
        "actions/upload-artifact@v7",
        "retention-days: 90",
    ):
        assert token in text


def test_docker_workflow_freezes_resource_and_sandbox_limits() -> None:
    workflow = Path(".github/workflows/phase11-docker.yml").read_text(
        encoding="utf-8"
    )
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    for token in (
        "--pull",
        "--no-cache",
        "--network none",
        "--cpus 2",
        "--memory 7g",
        "CUDA_VISIBLE_DEVICES",
        "NVIDIA_VISIBLE_DEVICES=void",
        "image-id.txt",
        "11_3_task_summary.json",
    ):
        assert token in workflow
    assert "COPY configs ./configs" in dockerfile
    assert "COPY data/sample ./data/sample" in dockerfile
    assert "/build/configs /workspace/configs" in dockerfile
    assert "/build/data/sample /workspace/data/sample" in dockerfile
    assert "USER cmag" in dockerfile


def test_local_execution_reports_are_ignored() -> None:
    ignore = Path(".gitignore").read_text(encoding="utf-8")

    assert "/CrossMarketAgentGym_详细执行报告.md" in ignore
    assert "/CrossMarketAgentGym_Phase10-17_执行报告.md" in ignore


def test_wheel_verifier_requires_configs_sample_mock_and_replay(
    tmp_path: Path,
) -> None:
    wheel = tmp_path / "fixture.whl"
    required = {
        "crossmarket_agentgym/agents/providers/mock.py",
        "crossmarket_agentgym/agents/providers/replay.py",
        "crossmarket_agentgym/resources/configs/agents/research_single_mock.yaml",
        "crossmarket_agentgym/resources/configs/agents/risk_committee_mock.yaml",
        "crossmarket_agentgym/resources/configs/data/sample.yaml",
        "crossmarket_agentgym/resources/configs/env/sample_cross_market.yaml",
        "crossmarket_agentgym/resources/configs/reproduction/phase11_cpu.yaml",
        "crossmarket_agentgym/resources/configs/train/ppo_quickstart.yaml",
        "crossmarket_agentgym/resources/configs/tune/ppo_pso_quickstart.yaml",
        "crossmarket_agentgym/resources/data/sample/dataset_manifest.json",
        "crossmarket_agentgym/resources/data/sample/market=CN/a.parquet",
        "crossmarket_agentgym/resources/data/sample/market=HK/a.parquet",
        "crossmarket_agentgym/resources/data/sample/market=JP/a.parquet",
        "crossmarket_agentgym/resources/data/sample/market=US/a.parquet",
    }
    with zipfile.ZipFile(wheel, "w") as archive:
        for name in sorted(required):
            archive.writestr(name, b"fixture")

    report = verify_wheel(wheel)

    assert report["is_valid"] is True
    assert report["configs_present"] is True
    assert report["sample_data_present"] is True
    assert report["mock_provider_present"] is True
    assert report["replay_provider_present"] is True


def _workflow_evidence(
    root: Path,
    *,
    commit: str,
    executor: str,
    run_id: str,
) -> None:
    root.mkdir()
    (root / "11_3_task_summary.json").write_text(
        json.dumps(
            {
                "all_passed": True,
                "source_commit": commit,
                "runtime_identity": {
                    "executor": executor,
                    "cuda_available": False,
                    "github_run_id": run_id,
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "11_3_task_summary.md").write_text("passed\n", encoding="utf-8")


def test_release_evidence_bundle_is_deterministic_and_commit_bound(
    tmp_path: Path,
) -> None:
    commit = "a" * 40
    cpu = tmp_path / "cpu"
    docker = tmp_path / "docker"
    _workflow_evidence(cpu, commit=commit, executor="linux_cpu", run_id="1")
    _workflow_evidence(docker, commit=commit, executor="docker", run_id="2")

    first, first_sum = build_bundle(
        linux_cpu_dir=cpu,
        docker_dir=docker,
        output_dir=tmp_path / "first",
        commit=commit,
        tag="v1.0.0-rc2",
    )
    second, second_sum = build_bundle(
        linux_cpu_dir=cpu,
        docker_dir=docker,
        output_dir=tmp_path / "second",
        commit=commit,
        tag="v1.0.0-rc2",
    )

    assert first.read_bytes() == second.read_bytes()
    assert first_sum.read_text(encoding="utf-8").split()[0] == (
        second_sum.read_text(encoding="utf-8").split()[0]
    )
    with zipfile.ZipFile(first) as archive:
        manifest = json.loads(
            archive.read("release_evidence_manifest.json")
        )
    assert manifest["source_commit"] == commit
    assert manifest["release_tag"] == "v1.0.0-rc2"

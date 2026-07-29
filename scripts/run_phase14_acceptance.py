"""Evaluate Phase 14 local gates and record externally verified publication state."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from crossmarket_agentgym import __version__
from crossmarket_agentgym.benchmarking.core import verify_benchmark
from crossmarket_agentgym.release.checks import check_release_readiness
from crossmarket_agentgym.release.distribution import verify_distributions
from crossmarket_agentgym.release.stable_manifest import (
    STABLE_VERSION,
    verify_stable_release_manifest,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_tag_state(root: Path) -> dict[str, object]:
    tag = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "refs/tags/v1.0.0^{commit}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tag_commit = tag.stdout.strip() if tag.returncode == 0 else None
    return {
        "tag": "v1.0.0",
        "exists_locally": tag_commit is not None,
        "tag_commit": tag_commit,
        "head_commit": head,
        "points_to_head": tag_commit == head if tag_commit is not None else False,
    }


def evaluate(args: argparse.Namespace) -> dict[str, object]:
    """Build the structured acceptance snapshot without inventing external evidence."""
    root = args.workspace_root.resolve()
    phase13 = json.loads(
        (root / "docs" / "experiments" / "phase13-machine-acceptance.json").read_text(
            encoding="utf-8"
        )
    )
    benchmark = verify_benchmark(root / "benchmarks" / "v1")
    readiness = check_release_readiness(root)
    manifest_valid, manifest_problems = verify_stable_release_manifest(root)

    dist_root = args.dist_dir
    if not dist_root.is_absolute():
        dist_root = root / dist_root
    distribution = (
        verify_distributions(dist_root, expected_version=STABLE_VERSION)
        if dist_root.is_dir()
        and any(dist_root.glob("*.whl"))
        and any(dist_root.glob("*.tar.gz"))
        else None
    )

    with tempfile.TemporaryDirectory(prefix="cmag-phase14-docs-") as temporary:
        docs = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "build_versioned_docs.py"),
                "--workspace-root",
                str(root),
                "--output",
                temporary,
                "--dry-run",
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )

    checkpoint = root / "data" / "sample" / "checkpoints" / "equal_weight_policy.json"
    declared_checkpoint_hash = (
        root
        / "data"
        / "sample"
        / "checkpoints"
        / "equal_weight_policy.json.sha256"
    ).read_text(encoding="utf-8").split(maxsplit=1)[0]
    checkpoint_valid = _sha256(checkpoint) == declared_checkpoint_hash

    local_checks = {
        "phase13_ready": phase13.get("phase14_ready") is True,
        "version_is_stable": __version__ == STABLE_VERSION,
        "benchmark_verified": benchmark.is_valid,
        "release_readiness_verified": readiness.is_ready,
        "release_manifest_verified": manifest_valid,
        "distributions_verified": distribution is not None and distribution.is_valid,
        "versioned_docs_strict_build": docs.returncode == 0,
        "sample_checkpoint_verified": checkpoint_valid,
    }
    local_ready = all(local_checks.values())
    tag_state = _git_tag_state(root)
    doi_verified = (
        isinstance(args.doi, str)
        and args.doi.startswith("10.")
        and args.doi_verified
    )
    external_checks = {
        "pypi_verified": args.pypi_verified,
        "docker_verified": args.docker_verified,
        "docs_site_verified": args.docs_verified,
        "github_release_verified": args.github_release_verified,
        "doi_verified": doi_verified,
        "p0_zero": args.p0_count == 0,
        "p1_zero": args.p1_count == 0,
    }
    phase14_complete = (
        local_ready
        and all(external_checks.values())
        and tag_state["exists_locally"] is True
        and tag_state["points_to_head"] is True
    )
    blockers: list[str] = []
    blockers.extend(name for name, passed in local_checks.items() if not passed)
    blockers.extend(name for name, passed in external_checks.items() if not passed)
    if not tag_state["exists_locally"]:
        blockers.append("stable_tag_missing")
    elif not tag_state["points_to_head"]:
        blockers.append("stable_tag_not_on_head")

    return {
        "schema_version": "1.0",
        "phase": 14,
        "evaluated_at": datetime.now(UTC).isoformat(),
        "phase13_input_valid": phase13.get("phase13_complete") is True,
        "local_checks": local_checks,
        "local_ready": local_ready,
        "distribution_checks": (
            [check.model_dump(mode="json") for check in distribution.checks]
            if distribution is not None
            else []
        ),
        "stable_manifest_problems": list(manifest_problems),
        "tag_state": tag_state,
        "external_verification": {
            **external_checks,
            "doi": args.doi,
            "evidence_source": "operator_supplied_disposition",
            "note": (
                "This script records supplied publication checks. It does not fabricate "
                "registry, DOI, or review evidence."
            ),
        },
        "phase14_complete": phase14_complete,
        "phase15_ready": phase14_complete,
        "release_blockers": sorted(set(blockers)),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path, default=Path("."))
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/experiments/phase14-machine-acceptance.json"),
    )
    parser.add_argument("--pypi-verified", action="store_true")
    parser.add_argument("--docker-verified", action="store_true")
    parser.add_argument("--docs-verified", action="store_true")
    parser.add_argument("--github-release-verified", action="store_true")
    parser.add_argument("--doi")
    parser.add_argument("--doi-verified", action="store_true")
    parser.add_argument("--p0-count", type=int, default=0)
    parser.add_argument("--p1-count", type=int, default=0)
    parser.add_argument("--require-complete", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = evaluate(args)
    root = args.workspace_root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.require_complete and not result["phase14_complete"]:
        return 1
    return 0 if result["local_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())

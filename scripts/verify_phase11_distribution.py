"""Verify that a wheel contains the offline Phase 11.3 execution resources."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

_REQUIRED_EXACT = frozenset(
    {
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
    }
)
_REQUIRED_PREFIXES = (
    "crossmarket_agentgym/resources/data/sample/market=CN/",
    "crossmarket_agentgym/resources/data/sample/market=HK/",
    "crossmarket_agentgym/resources/data/sample/market=JP/",
    "crossmarket_agentgym/resources/data/sample/market=US/",
)


def sha256_file(path: Path) -> str:
    """Return one bounded streaming SHA-256."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_wheel(path: Path) -> dict[str, object]:
    """Fail closed when offline configs, data, Mock, or Replay are absent."""
    resolved = path.resolve()
    with zipfile.ZipFile(resolved) as archive:
        names = frozenset(archive.namelist())
    missing = sorted(_REQUIRED_EXACT - names)
    missing_prefixes = [
        prefix for prefix in _REQUIRED_PREFIXES if not any(
            name.startswith(prefix) for name in names
        )
    ]
    return {
        "schema_version": "1.0",
        "wheel": resolved.name,
        "wheel_sha256": sha256_file(resolved),
        "configs_present": not any(
            item.startswith("crossmarket_agentgym/resources/configs/")
            for item in missing
        ),
        "sample_data_present": not missing_prefixes
        and "crossmarket_agentgym/resources/data/sample/dataset_manifest.json"
        not in missing,
        "mock_provider_present": (
            "crossmarket_agentgym/agents/providers/mock.py" not in missing
        ),
        "replay_provider_present": (
            "crossmarket_agentgym/agents/providers/replay.py" not in missing
        ),
        "missing_entries": missing,
        "missing_prefixes": missing_prefixes,
        "is_valid": not missing and not missing_prefixes,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify Phase 11 configs, sample data, Mock, and Replay in a wheel."
    )
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = verify_wheel(args.wheel)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8", newline="\n")
    return 0 if report["is_valid"] else 1


if __name__ == "__main__":
    sys.exit(main())

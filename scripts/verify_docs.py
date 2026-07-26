"""Verify the Phase 10 documentation set without network access."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED_DOCS = (
    "README.md",
    "docs/api_stability.md",
    "docs/versioning_policy.md",
    "docs/deprecation_policy.md",
    "docs/installation.md",
    "docs/quickstart.md",
    "docs/data_schema.md",
    "docs/environment.md",
    "docs/market_rules.md",
    "docs/rl_training.md",
    "docs/llm_agents.md",
    "docs/multi_agent.md",
    "docs/tuning.md",
    "docs/reproducibility.md",
    "docs/troubleshooting.md",
    "docs/security.md",
    "docs/stable-api.md",
    "docs/faq.md",
)
REQUIRED_COMMANDS = (
    "cmag data validate --config configs/data/sample.yaml",
    "cmag env check --config configs/env/sample_cross_market.yaml",
    "cmag train --config configs/train/ppo_quickstart.yaml",
    "cmag agent run --config configs/agents/research_single_mock.yaml",
    "cmag agent run --config configs/agents/risk_committee_mock.yaml",
    "cmag tune --config configs/tune/ppo_pso_quickstart.yaml",
    "cmag report --run-id",
    "cmag reproduce --run-id",
)
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
SECRET = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")


def _local_target(source: Path, raw_target: str, root: Path) -> Path | None:
    target = raw_target.strip().strip("<>").split("#", maxsplit=1)[0]
    if not target or target.startswith(("http://", "https://", "mailto:")):
        return None
    candidate = Path(target)
    return (
        (root / candidate).resolve()
        if target.startswith("/")
        else (source.parent / candidate).resolve()
    )


def verify_docs(root: Path) -> tuple[str, ...]:
    """Return deterministic documentation violations."""
    problems: list[str] = []
    documents: list[Path] = []
    for relative in REQUIRED_DOCS:
        path = root / relative
        if not path.is_file():
            problems.append(f"missing required document: {relative}")
        else:
            documents.append(path)

    combined = ""
    for path in documents:
        text = path.read_text(encoding="utf-8")
        combined += text + "\n"
        relative = path.relative_to(root).as_posix()
        if SECRET.search(text):
            problems.append(f"credential-shaped value in documentation: {relative}")
        for raw_target in LINK.findall(text):
            target = _local_target(path, raw_target, root)
            if target is not None and (
                not target.is_relative_to(root) or not target.exists()
            ):
                problems.append(f"broken local link in {relative}: {raw_target}")

    for command in REQUIRED_COMMANDS:
        if command not in combined:
            problems.append(f"undocumented reproducibility command: {command}")
    return tuple(sorted(set(problems)))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    problems = verify_docs(root)
    if problems:
        for problem in problems:
            print(f"ERROR {problem}")
        return 1
    print(f"PASS documentation contract ({len(REQUIRED_DOCS)} required files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Generate the Phase 14 stable release consistency manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from crossmarket_agentgym.release.stable_manifest import (
    verify_stable_release_manifest,
    write_stable_release_manifest,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or verify release_manifest_v1.0.0.json."
    )
    parser.add_argument("--workspace-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("release/release_manifest_v1.0.0.json"),
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify checked-in evidence without rewriting it.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.verify:
        valid, problems = verify_stable_release_manifest(
            args.workspace_root,
            manifest=args.output,
        )
        if valid:
            print("PASS stable release manifest")
            return 0
        for problem in problems:
            print(f"ERROR {problem}")
        return 1
    manifest, checksum = write_stable_release_manifest(
        args.workspace_root,
        output=args.output,
    )
    print(manifest)
    print(checksum)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Build v1.0.0 documentation plus stable/latest aliases."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VERSION = "v1.0.0"
ALIASES = ("stable", "latest")


def build(root: Path, output: Path, *, dry_run: bool) -> dict[str, object]:
    """Build strict MkDocs output and byte-identical release aliases."""
    report: dict[str, object] = {
        "schema_version": "1.0",
        "version": VERSION,
        "aliases": list(ALIASES),
        "mode": "dry_run" if dry_run else "built",
    }
    if dry_run:
        subprocess.run(
            [sys.executable, "-m", "mkdocs", "build", "--strict", "--site-dir", str(output)],
            cwd=root,
            check=True,
        )
        shutil.rmtree(output, ignore_errors=True)
        return report

    with tempfile.TemporaryDirectory(prefix="cmag-docs-") as temporary:
        versioned = Path(temporary) / VERSION
        subprocess.run(
            [
                sys.executable,
                "-m",
                "mkdocs",
                "build",
                "--strict",
                "--site-dir",
                str(versioned),
            ],
            cwd=root,
            check=True,
        )
        if output.exists():
            shutil.rmtree(output)
        output.mkdir(parents=True)
        shutil.copytree(versioned, output / VERSION)
        for alias in ALIASES:
            shutil.copytree(versioned, output / alias)
    (output / "versions.json").write_text(
        json.dumps(
            {
                "latest": VERSION,
                "stable": VERSION,
                "versions": [VERSION],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "index.html").write_text(
        '<!doctype html><meta charset="utf-8">'
        '<meta http-equiv="refresh" content="0; url=stable/">'
        '<link rel="canonical" href="stable/">\n',
        encoding="utf-8",
        newline="\n",
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("site"))
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.workspace_root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    result = build(root, output, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Build rc1 twice with one epoch and compare archive bytes."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _source_epoch(root: Path) -> str:
    configured = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    if configured:
        if not configured.isdigit():
            raise ValueError("SOURCE_DATE_EPOCH must be a non-negative integer")
        return configured
    completed = subprocess.run(
        ["git", "show", "-s", "--format=%ct", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    value = completed.stdout.strip()
    if not value.isdigit():
        raise ValueError("Git did not return a valid source epoch")
    return value


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _build(root: Path, output: Path, epoch: str) -> dict[str, str]:
    environment = os.environ.copy()
    environment["SOURCE_DATE_EPOCH"] = epoch
    environment.setdefault(
        "PIP_INDEX_URL",
        "https://pypi.tuna.tsinghua.edu.cn/simple",
    )
    subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(output)],
        cwd=root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        path.name: _digest(path)
        for path in sorted(output.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name.endswith((".whl", ".tar.gz"))
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    epoch = _source_epoch(root)
    with tempfile.TemporaryDirectory(prefix="cmag-build-a-") as first_dir:
        with tempfile.TemporaryDirectory(prefix="cmag-build-b-") as second_dir:
            first = _build(root, Path(first_dir), epoch)
            second = _build(root, Path(second_dir), epoch)
    if len(first) != 2 or first != second:
        print(f"ERROR non-reproducible release build: {first!r} != {second!r}")
        return 1
    print(f"PASS reproducible release build at SOURCE_DATE_EPOCH={epoch}: {first}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

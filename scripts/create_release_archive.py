"""Create a deterministic, restricted-data-free source evidence archive."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

_FORBIDDEN_COMPONENTS = frozenset(
    {
        ".env",
        ".git",
        ".venv",
        "node_modules",
        "stock_data",
    }
)
_FORBIDDEN_TOP_LEVEL = frozenset({"reports", "results", "runs"})


def _tracked_files(root: Path) -> tuple[Path, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    relative_paths = [
        Path(item.decode("utf-8"))
        for item in result.stdout.split(b"\0")
        if item
    ]
    return tuple(
        path
        for path in relative_paths
        if (root / path).is_file() and not _forbidden(path.as_posix())
    )


def _forbidden(name: str) -> bool:
    parts = tuple(part.lower() for part in PurePosixPath(name).parts)
    return bool(
        set(parts) & _FORBIDDEN_COMPONENTS
        or (parts and parts[0] in _FORBIDDEN_TOP_LEVEL)
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_archive(
    root: Path,
    output: Path,
    *,
    source_date_epoch: int,
    dry_run: bool,
) -> dict[str, object]:
    """Build one byte-stable tar.gz from Git-tracked, publishable files."""
    files = _tracked_files(root)
    report: dict[str, object] = {
        "schema_version": "1.0",
        "mode": "dry_run" if dry_run else "archive_created",
        "archive": output.name,
        "source_date_epoch": source_date_epoch,
        "file_count": len(files),
        "uncompressed_bytes": sum((root / path).stat().st_size for path in files),
        "restricted_data_included": False,
    }
    if dry_run:
        return report

    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = "crossmarket-agent-gym-1.0.0"
    with output.open("wb") as raw:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw,
            mtime=source_date_epoch,
        ) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for relative in files:
                    payload = (root / relative).read_bytes()
                    info = tarfile.TarInfo(f"{prefix}/{relative.as_posix()}")
                    info.size = len(payload)
                    info.mode = 0o755 if relative.suffix == ".sh" else 0o644
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = source_date_epoch
                    archive.addfile(info, io.BytesIO(payload))
    checksum = _sha256(output)
    checksum_path = output.with_suffix(output.suffix + ".sha256")
    checksum_path.write_text(
        f"{checksum}  {output.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    report["sha256"] = checksum
    report["checksum_file"] = checksum_path.name
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/crossmarket-agent-gym-1.0.0-evidence.tar.gz"),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.workspace_root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    raw_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if raw_epoch is None:
        result = subprocess.run(
            ["git", "show", "-s", "--format=%ct", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        source_date_epoch = int(result.stdout.strip())
    else:
        source_date_epoch = int(raw_epoch)
    report = build_archive(
        root,
        output,
        source_date_epoch=source_date_epoch,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

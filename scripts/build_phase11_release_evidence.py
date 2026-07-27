"""Build a deterministic permanent Phase 11.3 Release evidence package."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

_FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _load_summary(root: Path) -> dict[str, Any]:
    path = root / "11_3_task_summary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"summary is not an object: {path}")
    return payload


def _files(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda item: item.relative_to(root).as_posix(),
    )


def build_bundle(
    *,
    linux_cpu_dir: Path,
    docker_dir: Path,
    output_dir: Path,
    commit: str,
    tag: str,
) -> tuple[Path, Path]:
    """Validate both workflows and archive every uploaded evidence file."""
    linux_cpu_dir = linux_cpu_dir.resolve()
    docker_dir = docker_dir.resolve()
    cpu = _load_summary(linux_cpu_dir)
    docker = _load_summary(docker_dir)
    for name, summary, executor in (
        ("linux_cpu", cpu, "linux_cpu"),
        ("docker", docker, "docker"),
    ):
        if summary.get("all_passed") is not True:
            raise ValueError(f"{name} summary did not pass")
        if summary.get("source_commit") != commit:
            raise ValueError(f"{name} summary commit does not match {commit}")
        identity = summary.get("runtime_identity")
        if not isinstance(identity, dict) or identity.get("executor") != executor:
            raise ValueError(f"{name} executor identity is invalid")
        if identity.get("cuda_available") is not False:
            raise ValueError(f"{name} CUDA evidence is not false")

    members: dict[str, bytes] = {}
    for prefix, root in (("linux-cpu", linux_cpu_dir), ("docker", docker_dir)):
        for path in _files(root):
            members[f"{prefix}/{path.relative_to(root).as_posix()}"] = (
                path.read_bytes()
            )
    manifest = {
        "schema_version": "1.0",
        "release_tag": tag,
        "source_commit": commit,
        "linux_cpu_github_run_id": cpu["runtime_identity"].get("github_run_id"),
        "docker_github_run_id": docker["runtime_identity"].get("github_run_id"),
        "files": {
            name: {
                "sha256": _sha256_bytes(content),
                "size": len(content),
            }
            for name, content in sorted(members.items())
        },
    }
    manifest_bytes = (
        json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    )
    members["release_evidence_manifest.json"] = manifest_bytes
    markdown = "\n".join(
        (
            "# CrossMarketAgentGym Phase 11.3 Release evidence",
            "",
            f"- Release: `{tag}`",
            f"- Commit: `{commit}`",
            f"- Linux CPU run: `{manifest['linux_cpu_github_run_id']}`",
            f"- Docker run: `{manifest['docker_github_run_id']}`",
            "- Tasks B–I: passed in both execution environments",
            "- CUDA: disabled and unavailable in both execution environments",
            "- Computational replay: at least numerically reproduced",
            "",
        )
    ).encode("utf-8")
    members["README.md"] = markdown

    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = output_dir / (
        f"crossmarket-agent-gym-{tag.removeprefix('v')}-phase11-evidence.zip"
    )
    with zipfile.ZipFile(
        bundle,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for name, content in sorted(members.items()):
            info = zipfile.ZipInfo(name, _FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    checksum = output_dir / f"{bundle.name}.sha256"
    checksum.write_text(
        f"{_sha256_bytes(bundle.read_bytes())}  {bundle.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    return bundle, checksum


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build permanent Phase 11 evidence from two workflow artifacts."
    )
    parser.add_argument("--linux-cpu-dir", type=Path, required=True)
    parser.add_argument("--docker-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--tag", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        bundle, checksum = build_bundle(
            linux_cpu_dir=args.linux_cpu_dir,
            docker_dir=args.docker_dir,
            output_dir=args.output_dir,
            commit=args.commit,
            tag=args.tag,
        )
    except Exception as error:
        print(f"cannot build Phase 11 evidence: {error}", file=sys.stderr)
        return 1
    print(bundle)
    print(checksum)
    return 0


if __name__ == "__main__":
    sys.exit(main())

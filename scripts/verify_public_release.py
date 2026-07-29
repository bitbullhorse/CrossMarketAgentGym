"""Verify local or publicly published v1.0.0 release surfaces."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from crossmarket_agentgym.release.checks import check_release_readiness
from crossmarket_agentgym.release.stable_manifest import (
    STABLE_VERSION,
    verify_stable_release_manifest,
)


def _url_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "CrossMarketAgentGym-release-verifier/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{url} did not return a JSON object")
    return value


def _url_ok(url: str) -> bool:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "CrossMarketAgentGym-release-verifier/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return 200 <= response.status < 400


def verify(root: Path, *, online: bool) -> dict[str, Any]:
    """Return structured local and optional public-release checks."""
    checks: list[dict[str, object]] = []

    readiness = check_release_readiness(root)
    checks.append(
        {
            "name": "local_release_readiness",
            "passed": readiness.is_ready,
            "detail": f"{len(readiness.checks)} local release checks",
        }
    )
    manifest_valid, manifest_problems = verify_stable_release_manifest(root)
    checks.append(
        {
            "name": "stable_release_manifest",
            "passed": manifest_valid,
            "detail": "verified" if manifest_valid else "; ".join(manifest_problems),
        }
    )

    if online:
        try:
            pypi = _url_json("https://pypi.org/pypi/crossmarket-agent-gym/1.0.0/json")
            pypi_valid = pypi.get("info", {}).get("version") == STABLE_VERSION
        except (OSError, TypeError, urllib.error.URLError, json.JSONDecodeError) as error:
            pypi_valid = False
            pypi_detail = str(error)
        else:
            pypi_detail = "PyPI version 1.0.0 is public"
        checks.append({"name": "pypi", "passed": pypi_valid, "detail": pypi_detail})

        with tempfile.TemporaryDirectory(prefix="cmag-public-release-") as temporary:
            install = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "download",
                    "--no-deps",
                    "--dest",
                    temporary,
                    "crossmarket-agent-gym==1.0.0",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        checks.append(
            {
                "name": "pypi_download",
                "passed": install.returncode == 0,
                "detail": "fresh package download succeeded"
                if install.returncode == 0
                else install.stderr[-500:],
            }
        )

        container = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--pull",
                "always",
                "--network",
                "none",
                "--cpus",
                "2",
                "--memory",
                "7g",
                "--env",
                "CUDA_VISIBLE_DEVICES=",
                "--env",
                "NVIDIA_VISIBLE_DEVICES=void",
                "ghcr.io/bitbullhorse/crossmarket-agent-gym:1.0.0",
                "--version",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        checks.append(
            {
                "name": "public_container",
                "passed": container.returncode == 0
                and container.stdout.strip() == STABLE_VERSION,
                "detail": "public non-CUDA container returned 1.0.0"
                if container.returncode == 0
                else container.stderr[-500:],
            }
        )

        for alias in ("v1.0.0", "stable", "latest"):
            url = (
                "https://bitbullhorse.github.io/CrossMarketAgentGym/"
                f"{alias}/"
            )
            try:
                passed = _url_ok(url)
                detail = url
            except (OSError, urllib.error.URLError) as error:
                passed = False
                detail = str(error)
            checks.append(
                {
                    "name": f"docs_{alias.replace('.', '_')}",
                    "passed": passed,
                    "detail": detail,
                }
            )

        manifest = json.loads(
            (root / "release" / "release_manifest_v1.0.0.json").read_text(
                encoding="utf-8"
            )
        )
        doi = manifest["publication"]["doi"]["identifier"]
        doi_valid = isinstance(doi, str) and doi.startswith("10.")
        if doi_valid:
            try:
                doi_valid = _url_ok(f"https://doi.org/{doi}")
            except (OSError, urllib.error.URLError):
                doi_valid = False
        checks.append(
            {
                "name": "doi",
                "passed": doi_valid,
                "detail": str(doi) if doi is not None else "DOI is not reserved",
            }
        )

    return {
        "schema_version": "1.0",
        "version": STABLE_VERSION,
        "verification_mode": "public_online" if online else "local_offline",
        "passed": all(bool(check["passed"]) for check in checks),
        "checks": checks,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path, default=Path("."))
    parser.add_argument("--online", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = verify(args.workspace_root.resolve(), online=args.online)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env bash
set -euo pipefail

mode="--dry-run"
if [[ "${1:-}" == "--create" ]]; then
  mode=""
elif [[ "${1:-}" != "" && "${1:-}" != "--dry-run" ]]; then
  echo "usage: scripts/create_archive.sh [--dry-run|--create]" >&2
  exit 2
fi

python scripts/create_stable_release_manifest.py --verify
python scripts/create_release_archive.py ${mode}

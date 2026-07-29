#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--online" ]]; then
  python scripts/verify_public_release.py --online
elif [[ "${1:-}" == "" || "${1:-}" == "--offline" || "${1:-}" == "--dry-run" ]]; then
  python scripts/verify_public_release.py
else
  echo "usage: scripts/verify_public_release.sh [--offline|--dry-run|--online]" >&2
  exit 2
fi

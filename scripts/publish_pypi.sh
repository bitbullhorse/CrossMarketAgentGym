#!/usr/bin/env bash
set -euo pipefail

version="1.0.0"
if [[ "${1:-}" == "--publish" ]]; then
  cmag release verify --dist-dir dist --version "${version}"
  python -m twine check dist/*.whl dist/*.tar.gz
  command -v gh >/dev/null
  gh workflow run release.yml \
    --ref "v${version}" \
    -f publish_pypi=true \
    -f publish_container=false \
    -f deploy_docs=false
  echo "Requested OIDC-backed PyPI publication for v${version}."
elif [[ "${1:-}" == "" || "${1:-}" == "--dry-run" ]]; then
  cmag release verify --dist-dir dist --version "${version}"
  python -m twine check dist/*.whl dist/*.tar.gz
  echo "DRY RUN: validated distributions; no PyPI upload was performed."
  echo "Publish with: scripts/publish_pypi.sh --publish"
else
  echo "usage: scripts/publish_pypi.sh [--dry-run|--publish]" >&2
  exit 2
fi

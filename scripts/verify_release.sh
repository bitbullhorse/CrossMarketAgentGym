#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python scripts/verify_docs.py
cmag release freeze --workspace-root .
ruff check .
mypy src
pytest
cmag quickstart --smoke-steps 64
python scripts/verify_reproducible_build.py
bash scripts/build_release.sh

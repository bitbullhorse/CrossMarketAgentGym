#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
export PIP_DISABLE_PIP_VERSION_CHECK=1
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git show -s --format=%ct HEAD)}"

python scripts/verify_docs.py
cmag release freeze --workspace-root .
cmag release check --workspace-root .
python -m build
python -m twine check dist/*.whl dist/*.tar.gz
cmag release verify --dist-dir dist
cmag release manifest --dist-dir dist

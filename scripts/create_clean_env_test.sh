#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHEEL="${1:-}"
if [[ -z "$WHEEL" ]]; then
  WHEEL="$(find "$ROOT/dist" -maxdepth 1 -type f -name '*.whl' -print -quit)"
fi
if [[ -z "$WHEEL" || ! -f "$WHEEL" ]]; then
  echo "wheel not found; pass a wheel path or run scripts/build_release.sh" >&2
  exit 2
fi

TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT
python -m venv "$TMP_ROOT/venv"
PYTHON="$TMP_ROOT/venv/bin/python"
"$PYTHON" -m pip install \
  --index-url "${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}" \
  "$WHEEL"
cd "$TMP_ROOT"
"$PYTHON" -m crossmarket_agentgym.cli.app --help
"$TMP_ROOT/venv/bin/cmag" quickstart --smoke-steps 16

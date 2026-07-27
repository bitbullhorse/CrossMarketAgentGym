#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${CMAG_REPRO_IMAGE:-crossmarket-agent-gym:phase11-local}"
WORK_ROOT="$(mktemp -d)"
trap 'rm -rf "$WORK_ROOT"' EXIT

mkdir -p "$WORK_ROOT/runs"
chmod 0777 "$WORK_ROOT/runs"

docker build \
  --build-arg "PIP_INDEX_URL=${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}" \
  --build-arg "CMAG_EXTRAS=rl,hpo,llm" \
  --tag "$IMAGE" \
  "$ROOT"

run_cmag() {
  docker run --rm \
    --network none \
    --user 10001:10001 \
    --volume "$ROOT/configs:/workspace/configs:ro" \
    --volume "$ROOT/data/sample:/workspace/data/sample:ro" \
    --volume "$WORK_ROOT/runs:/workspace/runs" \
    "$IMAGE" "$@"
}

run_cmag data validate --config configs/data/sample.yaml
run_cmag env check --config configs/env/sample_cross_market.yaml
run_cmag train --config configs/train/ppo_quickstart.yaml
run_cmag agent run --config configs/agents/research_single_mock.yaml
run_cmag agent run --config configs/agents/risk_committee_mock.yaml
run_cmag tune --config configs/tune/ppo_pso_quickstart.yaml
run_cmag report --run-id repro-ppo-quickstart
run_cmag reproduce --run-id repro-ppo-quickstart --verify-only
run_cmag reproduce \
  --run-id repro-ppo-quickstart \
  --execute \
  --compare \
  --tolerance-config configs/reproduction/phase11_cpu.yaml

echo "PASS Phase 11 non-root, network-disabled Docker reproduction"

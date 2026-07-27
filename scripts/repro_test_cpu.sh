#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVIDENCE_ROOT="${1:-$ROOT/reproducibility_tests/executions/cpu-$(date -u +%Y%m%dT%H%M%SZ)}"

if [[ -e "$EVIDENCE_ROOT" ]]; then
  echo "evidence directory already exists: $EVIDENCE_ROOT" >&2
  exit 2
fi

mkdir -p "$EVIDENCE_ROOT/data"
cp -R "$ROOT/configs" "$EVIDENCE_ROOT/configs"
cp -R "$ROOT/data/sample" "$EVIDENCE_ROOT/data/sample"

cd "$EVIDENCE_ROOT"
cmag data validate --config configs/data/sample.yaml
cmag env check --config configs/env/sample_cross_market.yaml
cmag train --config configs/train/ppo_quickstart.yaml
cmag agent run --config configs/agents/research_single_mock.yaml
cmag agent run --config configs/agents/risk_committee_mock.yaml
cmag tune --config configs/tune/ppo_pso_quickstart.yaml
cmag report --run-id repro-ppo-quickstart
cmag reproduce --run-id repro-ppo-quickstart --verify-only
python "$ROOT/scripts/compare_reproduced_run.py" \
  --workspace-root "$EVIDENCE_ROOT" \
  --run-id repro-ppo-quickstart \
  --tolerance-config "$ROOT/configs/reproduction/phase11_cpu.yaml"

echo "PASS Phase 11 CPU reproduction evidence: $EVIDENCE_ROOT"

#!/usr/bin/env bash
set -euo pipefail

project_root="${CMAG_PHASE12_ROOT:-/home/czj/CodexProject/CrossMarketAgentGym}"
python_bin="${CMAG_PHASE12_PYTHON:-/mnt/sdb/czj/conda_envs/pytorch_3.12/bin/python}"
parallelism="${CMAG_PHASE12_PARALLELISM:-4}"
group="${1:?usage: run_phase12_remote.sh GROUP [METHOD]}"
method="${2:-}"

cd "$project_root"

"$python_bin" scripts/freeze_phase12_protocol.py >/tmp/cmag-phase12-protocol-check.json
"$python_bin" -m pytest -q tests/leakage tests/experiments

list_args=(scripts/run_phase12_group.py --group "$group" --list-only)
if [[ -n "$method" ]]; then
  list_args+=(--method "$method")
fi
mapfile -t run_ids < <("$python_bin" "${list_args[@]}")

run_one() {
  local slot="$1"
  local run_id="$2"
  export CUDA_VISIBLE_DEVICES="$((slot % 4))"
  "$python_bin" scripts/run_phase12_task.py --run-id "$run_id"
}
export -f run_one
export python_bin

for index in "${!run_ids[@]}"; do
  printf '%s\0%s\0' "$index" "${run_ids[$index]}"
done | xargs -0 -n2 -P"$parallelism" bash -c 'run_one "$0" "$1"'

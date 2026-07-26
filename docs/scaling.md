# Optional Ray and GPU execution

CPU execution remains the reference contract. Phase 9 adds an optional Ray adapter for independent
Trial evaluation after the local searcher and scheduler APIs stabilized.

## Separation of responsibilities

```text
SearchAlgorithm -> TrialSuggestion
TrialScheduler -> resource/stop/promote/exploit decision
TrialBatchExecutor -> local or Ray placement of objective evaluation
ObjectiveEvaluator -> train/validation-only TrialResult
```

`RayTrialExecutor` does not generate candidates and does not implement ASHA, HyperBand, or PBT.
Those remain `TrialScheduler` implementations. Results are restored to suggestion order before
the searcher observes them, so Ray completion order cannot change deterministic search history.

Objective exceptions become failed Trials and remain persisted. A mismatched Trial ID, parameter
set, or result count fails closed.

## Installation

On the target CUDA host, use the existing Python 3.12 environment and Tsinghua mirror:

```bash
export PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
python -m pip install -c constraints-gpu.txt -e ".[rl,ray]"
```

Install the CUDA-specific PyTorch build appropriate for the host driver before running a CUDA
configuration. CUDA wheel/channel selection is intentionally not hard-coded into project
metadata.

## Example

`configs/tune/ppo_pso_ray_gpu.yaml` requests four concurrent Trial slots with one GPU and two CPUs
per Trial:

```bash
ray start --head
cmag tune --config configs/tune/ppo_pso_ray_gpu.yaml
```

The example uses PSO, ASHA, and Ray as three separate top-level configuration objects. Its base
training configuration is `configs/train/ppo_tune_gpu.yaml`, which explicitly requests `cuda`.

All Ray workers must see the same code, dataset manifest, output directory, and SQLite/storage
location. Do not copy API keys into Ray runtime environments or command lines.

## Current boundary

Unit tests use a deterministic fake Ray runtime to validate resource requests, result ordering,
failure isolation, and shutdown ownership without making Ray a CPU-test dependency. An actual
multi-GPU acceptance run requires a secure SSH key or another credential channel; the supplied
password is not written to source, command history, process arguments, or logs.

Ray placement does not yet provide live SB3 checkpoint cancellation, distributed PBT weight
transfer, or multi-node failure recovery. These require an incremental objective protocol and
shared checkpoint transport rather than changes to search/scheduler identity.

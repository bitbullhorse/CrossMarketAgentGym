# Frequently asked questions

## Does the quickstart use private stock data?

No. It uses the redistributable deterministic sample under `data/sample`.

## Does an Agent place trades?

No. Agents return typed proposals. Deterministic risk and environment code applies constraints and
is the only layer that updates simulated account state.

## Which LLM model is configured?

Online examples require `deepseek-v4-pro`. Release tests use Mock/Replay and do not use a network.

## Can HPO use the test partition?

No. Training and validation are available to HPO. Test is reserved for a locked final evaluation.

## Are ASHA, HyperBand, and PBT search algorithms?

No. They are resource schedulers independent from the nine search algorithms.

## What is the relationship between rc2 and v1.0.0?

rc2 closed the Phase 11 independent-reproduction gate. Stable v1.0.0 additionally binds the
accepted formal experiment inputs and immutable Benchmark v1 through its release manifest.

## Where are compatibility and known limitations recorded?

See the [compatibility matrix](compatibility.md) and
[known limitations](known-limitations.md).

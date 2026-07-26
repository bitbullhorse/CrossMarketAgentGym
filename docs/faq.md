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

## Is rc1 the final v1.0.0 release?

No. rc1 freezes the Phase 10 interface for Phase 11 independent reproduction. rc2 and the later
experiment, benchmark, and formal-release gates must occur in order.

## Where are compatibility and known limitations recorded?

See [compatibility matrix](../release/compatibility_matrix.md) and
[known issues](../release/known_issues.md).

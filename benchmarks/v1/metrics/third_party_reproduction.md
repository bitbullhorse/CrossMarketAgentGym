# Phase 11 reproducibility report

Status: **release closing**. Computational replay and Tasks 5–8 are closed locally. The workspace
owner reports multiple independent participants completed functional review and the P0/P1 audit
is clear. Linux CPU/Docker Task B–I evidence and a permanent rc2 Release asset remain required.
This file does not authorize Phase 12 formal experiments.

## Operator-provided Phase 11.3 status

The current workspace owner reported successful installation, data/environment validation, PPO
quickstart, Research Agent, risk committee, PSO quickstart, reporting, and persistence/hash
validation. Those statements identify the starting condition for this implementation task; they
are not substituted for independent participant forms.

## Computational replay implementation evidence

On 2026-07-27, the final direct-CLI CPU implementation replay of source run
`repro-ppo-quickstart` was written as `replay-repro-ppo-quickstart-003`. The authoritative local
source file is:

```text
runs/reproductions/repro-ppo-quickstart/
  replay-repro-ppo-quickstart-003/reproduction_comparison.json
```

The result was `numerically_reproduced`:

- artifact integrity passed and actual retraining/evaluation executed;
- all five required metric absolute differences were `0.0`;
- trained timesteps, algorithm, dataset hash, TrainerConfig hash, execution protocol, and both
  checkpoint loadability results matched;
- validation metrics, trades, and weights were byte-identical;
- the SB3 checkpoint ZIP hash differed, so the stronger bitwise level was not claimed;
- source artifacts were unchanged;
- no test partition, network, or external account mutation was used;
- three compatible replay samples also passed the statistical comparison, while the ordered level
  remained the stronger single-run `numerically_reproduced`;
- the replay manifest verified all 12 recorded artifacts.

This is implementation evidence, not an independent participant result and not a Phase 12 formal
experiment.

## Tasks 5–8 local evidence

- `flat` and `tensor` preserve identical OHLCV values; packaged PPO/SAC quickstarts use `flat`,
  while tensor-mode SB3 requires a custom extractor.
- `cmag env check --config configs/env/sample_cross_market.yaml` passed Gymnasium, SB3, and 64
  smoke steps with no warnings; maximum accounting error was
  `2.3283064365386963e-10`.
- `phase11-flat-metadata-smoke` records non-null timing/runtime identity and explicit single-sample
  statistical warnings.
- Its replay `replay-phase11-flat-metadata-smoke-001` reached
  `numerically_reproduced`, with zero difference for all five comparison metrics and no
  test/network/account access.
- Risk fusion journals the exact `cash_floor` max derivation, and committee/projection logs
  distinguish policy, conflict, outcome, two confidence meanings, and projection reasons.

## Exit status

| Gate | Status |
|---|---|
| Artifact verification semantics are explicit | passed |
| Isolated computational retraining and comparison | passed locally |
| CPU level at least numerical | passed locally |
| Source immutability and replay manifest | passed locally |
| Test/network/account boundaries | passed locally |
| Full repository tests | 331 passed; 87.35% branch coverage |
| Leakage/accounting/risk-boundary selection | 43 passed independently |
| Tasks 5–8 targeted tests | 58 passed |
| Flat-layout computational replay | numerically reproduced |
| Independent participant review | owner attests multiple participants completed |
| Module functionality | owner reports all tested modules normal |
| P0/P1 independent issue audit | owner reports P0 = 0, P1 = 0, audit complete |
| Fabricated participant details | none |
| Linux CPU/Docker Task B–I | pending dedicated workflows |
| Permanent Release evidence | pending |
| `v1.0.0-rc2` | blocked |
| Phase 12 readiness | blocked |

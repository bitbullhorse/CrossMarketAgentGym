# Phase 2 — Environment and accounting

## Goal

Deliver a leakage-safe Gymnasium portfolio environment with deterministic action projection,
cross-market calendars and FX, market-rule plugins, explicit cost/slippage accounting, tradability
masks, six reward functions, and an auditable next-open execution protocol.

## File changes

- `data/calendars/`: calendar protocol plus native, union, intersection, and scheduled-rebalance
  implementations.
- `data/fx/`: validated latest-on-or-before base-currency conversion.
- `environments/config.py`: immutable environment, risk, cost, reward, lot, and T+1 settings.
- `environments/panel.py`: union-calendar arrays, supplied-calendar selection, valuation continuity,
  FX conversion, masks, identifiers, and feature windows.
- `environments/projection.py`, `environments/rules.py`: action normalization, hard portfolio
  constraints, and execution-rule plugins.
- `environments/accounting.py`, `environments/execution.py`: immutable account state, signed
  positions, deterministic fills, costs, and per-step reconciliation.
- `environments/rewards.py`: LogReturn, ReturnMinusCost, RiskAdjusted, DifferentialSharpe,
  DrawdownPenalty, and CVaRPenalty.
- `environments/portfolio.py`: Gymnasium environment, observations, next-open step protocol, and
  audit `info`.
- `environments/checks.py`, `cli/app.py`: Gymnasium/SB3 compatibility and 1,000-step CLI smoke
  validation.
- `configs/env/`: reproducible sample validation configuration.
- `tests/`: calendar, FX, panel, projection, execution, reward, leakage, property, integration, and
  CLI coverage.
- `.github/workflows/ci.yml`: CPU CI now installs the RL compatibility extra.

## Design decisions

1. An action observed after close `t` executes only at open `t+1`; close `t+1` is used only after
   quantity and execution price are fixed.
2. The observed union calendar is the default, while explicit calendar composition can select
   native, intersection, or scheduled sessions.
3. Forward-filled prices maintain valuation continuity but never set execution eligibility.
4. FX conversion uses the latest rate on or before the local session and fails if no historical
   rate exists.
5. Non-tradable positions are frozen. Existing cap violations are reported as unresolved instead
   of forcing an impossible trade.
6. Account state is immutable-by-replacement and only `ExecutionEngine` may replace it.
7. Transaction fees and slippage are separate non-negative amounts and must reconcile against the
   open-price mid-value before close marking.
8. T+1 eligibility is session state; configured markets and lot sizes are not inferred as universal
   exchange facts.
9. The required `[N,L,F]` market window is retained even though the generic SB3 checker treats it
   as image-like; Phase 3 must supply the matching custom feature extractor.

## Tests

The suite covers calendar composition and navigation, forward-only FX lookup, supplied and union
calendar panels, closure masks, action cleaning, frozen assets, hard exposure and turnover limits,
all six rewards, manual and property-based accounting identities, non-negative costs, signed short
positions, lot/T+1/suspension/price-limit behavior, modern Gymnasium API compatibility, temporal
leakage, auditable step output, and 1,000 seeded random actions.

## Acceptance result

Phase 2 passed the required local quality gates on Python 3.12.13:

| Check | Result |
|---|---|
| `cmag env check --config configs/env/cross_market.yaml` | Valid |
| Gymnasium `check_env` | Passed |
| Stable-Baselines3 `check_env` | Passed with documented image-shape warnings |
| Random-action smoke | 1,000 steps; finite observations, rewards, and values |
| Maximum accounting error | `4.656612873077393e-10` |
| Manual accounting | Buy at 100, close at 110: expected and actual value 1,100 |
| Leakage contract | Future close cannot affect prior observation or executed quantity |
| `pytest` | 89 passed |
| Branch coverage | 88.22%, above the 85% gate |
| `ruff check .` | Passed |
| `mypy src` | Passed for 59 source files |
| `pip check` | No broken requirements |
| `python -m uv lock --check` | Passed; 111 packages resolved |

The machine-readable acceptance record is
`docs/environment/phase2-acceptance.json`.

## Open issues

- The Phase 3 RL policies need a custom dictionary feature extractor for the required market tensor.
- Production runs need authoritative exchange calendars, instrument lot masters, price-limit flags,
  and FX artifacts with their own manifests.
- Borrow costs, financing, margin calls, taxes, and intraday microstructure are outside the Phase 2
  daily-bar accounting claim.
- The full private source tree remains unconverted because Phase 1 found anomalies that require an
  explicit remediation policy.

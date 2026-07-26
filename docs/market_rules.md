# Market rules

The rc1 environment models rules explicitly through configuration and recorded data:

- asynchronous CN, HK, JP, and US calendars;
- next-open execution after a close-time signal;
- CN T+1 sell restrictions;
- suspensions and per-row tradability;
- market and asset weight caps;
- minimum cash, leverage, turnover, transaction costs, and slippage;
- quote-currency conversion into one base currency; and
- configurable lot sizes.

The most conservative behavior is used when required market state is missing: the affected asset
is non-tradable. A rule change is a configuration and protocol change, not an Agent decision.
Future information such as a later calendar, constituent set, corporate action, or FX value must
not be injected into an earlier observation.

Accounting must reconcile:

```text
portfolio_value = cash + sum(position_quantity * executable_price * fx_rate)
```

Any safety, accounting, or leakage failure blocks release and formal experiments.

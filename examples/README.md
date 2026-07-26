# Examples

Executable CPU quickstarts are added with the implementation phases. Examples will consume the
public four-market sample and will never substitute for package code or tests.

`evaluate_baselines.py` runs all seven deterministic Phase 3 baselines against that sample. Its
printed returns are compatibility evidence only.

`serve_reports.py` starts the optional Phase 8 read-only local report browser from
`configs/reporting/service.yaml`. It performs no report or run mutation.

`cpu_quickstart.py` validates the packaged four-market sample and environment without network or
LLM use. `reproduce_run.py <run-id>` verifies a recorded run without retraining or account
mutation.

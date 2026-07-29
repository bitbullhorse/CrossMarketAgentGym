# benchmark-v1 operator guide

`benchmarks/v1` is the immutable result snapshot used by later manuscript work. It contains
215 formal run records, compact metrics and statistics, Agent/HPO evidence, generated tables,
generated figures and SHA-256 provenance.

Verify it before reading or exporting results:

```bash
cmag benchmark verify --benchmark benchmarks/v1
```

A successful result has `is_valid: true` and eight passing checks. The Benchmark must not be
edited to fix a caption, add an experiment or answer a reviewer. Such changes require a new
protocol and a new revision such as `benchmarks/v2`.

Paper artifacts are copied to a new directory; the source Benchmark remains unchanged:

```bash
cmag paper export-tables \
  --benchmark benchmarks/v1 \
  --output paper/generated/benchmark-v1/tables

cmag paper export-figures \
  --benchmark benchmarks/v1 \
  --output paper/generated/benchmark-v1/figures
```

The exporter also refuses to overwrite an existing destination. Tables are available as CSV,
LaTeX, Markdown and HTML. SVGs have adjacent `.data.csv` files and
`figures/sources.json`. Large trades and weights can be located and verified through
`trades/artifact_index.csv` and `weights/artifact_index.csv`.

The training, locked-test equity/drawdown and realized market-exposure figures use the
representative formal run `p12v4m6-B-ppo-s1024`. Its three source payloads are embedded under
`metrics/representative_run/` only after their hashes match `formal_run.json`.

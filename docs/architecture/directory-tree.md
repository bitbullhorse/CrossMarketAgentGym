# Complete target directory tree

The distribution name is `crossmarket-agent-gym`, the import package is
`crossmarket_agentgym`, and the executable is `cmag`.

```text
.
├── .github/
│   └── workflows/{ci,release}.yml
├── configs/
│   ├── agents/
│   ├── data/
│   ├── env/
│   ├── examples/
│   ├── train/
│   └── tune/
├── data/
│   └── sample/
├── docs/
│   ├── architecture/
│   ├── data/
│   ├── issues/
│   └── phases/
├── paper/
├── examples/
├── src/
│   └── crossmarket_agentgym/
│       ├── agents/
│       │   ├── aggregation/
│       │   ├── guardrails/
│       │   ├── providers/
│       │   ├── roles/
│       │   └── tools/
│       ├── api/
│       ├── audit/
│       ├── cli/
│       ├── config/
│       ├── data/
│       │   ├── adapters/
│       │   ├── calendars/
│       │   ├── fx/
│       │   ├── manifests/
│       │   ├── quality/
│       │   └── schemas/
│       ├── environments/
│       ├── evaluation/
│       ├── features/
│       ├── reporting/
│       ├── release/
│       ├── rl/
│       │   ├── callbacks/
│       │   ├── policies/
│       │   └── trainers/
│       ├── tuning/
│       │   ├── executors/
│       │   ├── reports/
│       │   ├── schedulers/
│       │   └── searchers/
│       └── utils/
├── tests/
│   ├── agents/
│   ├── integration/
│   ├── leakage/
│   ├── property/
│   ├── regression/
│   ├── tuning/
│   └── unit/
├── .env.example
├── .gitignore
├── CHANGELOG.md
├── CITATION.cff
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── CrossMarketAgentGym_详细执行报告.md
├── Dockerfile
├── LICENSE
├── README.md
├── constraints-cpu.txt
├── constraints-gpu.txt
├── pyproject.toml
└── uv.lock
```

Local-only inputs and outputs such as `stock_data/`, `.venv/`, `runs/`, and logs are excluded from
the distribution.

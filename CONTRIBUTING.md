# Contributing

Changes must follow the phase order and the precedence rules in the detailed execution report:
no leakage, accounting correctness, reproducibility, hard risk limits, extensibility, performance,
then interface work.

Before opening a change, run:

```bash
pytest --cov-report=xml
ruff check .
mypy src
cmag release check --workspace-root .
```

Release changes must also run `python -m build`, `python -m twine check dist/*`, and inspect the
distribution manifest. Never commit source market data, credentials, generated runs, or model
checkpoints. Never push a release tag merely to test publishing.

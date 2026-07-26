# Development

Use Python 3.11 or 3.12:

```bash
export PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
python -m venv .venv
.venv/bin/python -m pip install -c constraints-cpu.txt -e ".[dev,rl,service]"
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy src
```

On Windows PowerShell, set
`$env:PIP_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple"` and use
`.venv\Scripts\python.exe`. The lock file and CI use the same Tsinghua mirror. GPU and Ray
validation is additive and must not block the CPU quickstart.

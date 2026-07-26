# Installation

CrossMarketAgentGym supports Python 3.11 and 3.12. Run commands from the repository root. The
Tsinghua PyPI mirror is used for ordinary Python packages.

## CPU source environment

```bash
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
python -m pip install -c constraints-cpu.txt -e ".[dev,legacy-data,release,service]"
cmag --version
cmag quickstart --smoke-steps 64
```

The `dev` extra intentionally contains RL, HPO, Mock/Replay LLM, and test dependencies because the
independent reproduction protocol starts with `pip install -e ".[dev]"`. CPU PyTorch should be
installed from a CPU channel when the platform's default resolver would pull CUDA libraries.

The equivalent Conda declaration is `environment-cpu.yml`:

```bash
conda env create -f environment-cpu.yml
conda activate crossmarket-agent-gym-cpu
```

## Optional profiles

- `legacy-data`: Excel adapters (`openpyxl`, `xlrd`).
- `rl`: PyTorch and Stable-Baselines3.
- `hpo`: Optuna and SciPy adapters.
- `llm`: HTTP transport for an online OpenAI-compatible DeepSeek endpoint.
- `ray`: Ray Tune executor only; searchers and schedulers remain project abstractions.
- `service`: local read-only FastAPI report browser.
- `release`: build and distribution validation tools.

`environment-gpu.yml` declares PyTorch 2.7.1 with CUDA 12.6 and Ray. Verify the NVIDIA driver
before use. Never report that profile as verified solely because dependency resolution succeeds.

For a built wheel, install into a new environment and run:

```bash
python -m pip install dist/crossmarket_agent_gym-1.0.0rc1-py3-none-any.whl
cmag --help
cmag quickstart --smoke-steps 16
```

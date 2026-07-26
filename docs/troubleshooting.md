# Troubleshooting

## A run already exists

Run IDs are immutable. Use a clean workspace or a new run ID. Do not overwrite audit evidence.

## PyTorch installs CUDA packages on a CPU machine

Create `environment-cpu.yml`, or install the matching PyTorch CPU wheel before installing the
project. Confirm `python -c "import torch; print(torch.__version__, torch.cuda.is_available())"`.

## Online Agent reports a missing key

Install the `llm` extra and set `DEEPSEEK_API_KEY` only in the current process environment. Do not
paste credentials into a config, issue, test fixture, or log. Offline Mock/Replay commands need no
key.

## Dataset validation reports a hash mismatch

Treat the dataset as changed or corrupted. Do not edit the manifest to silence the error; rebuild
a new versioned manifest from the intended source.

## HPO resume rejects the database

Use the study with the software version that created it or apply a reviewed migration. A database
with a newer `PRAGMA user_version` is rejected to prevent silent reinterpretation.

## Docker command is unavailable

Docker is a Phase 10 exit gate. Record the local limitation and rely on the required Linux CI
Docker job; do not mark the phase complete until that job passes.

"""Run the installed-wheel-compatible CPU quickstart."""

from __future__ import annotations

from crossmarket_agentgym.release import run_cpu_quickstart


def main() -> None:
    summary = run_cpu_quickstart(smoke_steps=64)
    print(summary.model_dump_json(indent=2))
    if not summary.is_valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

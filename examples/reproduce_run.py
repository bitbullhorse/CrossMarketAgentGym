"""Verify a recorded run without network, retraining, or account mutation."""

from __future__ import annotations

import argparse

from crossmarket_agentgym.release import reproduce_run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    arguments = parser.parse_args()
    result = reproduce_run(".", "runs", arguments.run_id)
    print(result.model_dump_json(indent=2))
    if not result.is_valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

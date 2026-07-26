"""Start the optional local read-only report browser."""

from __future__ import annotations

import argparse
from pathlib import Path

from crossmarket_agentgym.api import load_service_config, run_service


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/reporting/service.yaml"),
    )
    arguments = parser.parse_args()
    run_service(load_service_config(arguments.config))


if __name__ == "__main__":
    main()

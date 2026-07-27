"""Build the immutable, non-redistributable-data Phase 12 source inventory."""

from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path

from crossmarket_agentgym.data.manifests import sha256_file
from crossmarket_agentgym.experiments.source_inventory import build_source_inventory


def parse_args() -> argparse.Namespace:
    """Parse explicit versioned-inventory inputs."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-config",
        type=Path,
        default=Path("configs/data/local_stock_data_full.yaml"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiments/data/source_inventory_v1.json"),
    )
    parser.add_argument("--ordering-salt", default="CrossMarketAgentGym-protocol-v1")
    parser.add_argument("--coverage-start", type=date.fromisoformat, required=True)
    parser.add_argument("--coverage-end", type=date.fromisoformat, required=True)
    parser.add_argument("--assets-per-market", type=int, default=20)
    parser.add_argument("--held-out-assets-per-market", type=int, default=4)
    parser.add_argument("--created-at", type=datetime.fromisoformat, required=True)
    return parser.parse_args()


def main() -> None:
    """Build once and print its identity without exposing raw market data."""
    args = parse_args()
    inventory = build_source_inventory(
        data_config=args.data_config,
        output_path=args.output,
        ordering_salt=args.ordering_salt,
        minimum_coverage_start=args.coverage_start,
        minimum_coverage_end=args.coverage_end,
        assets_per_market=args.assets_per_market,
        held_out_assets_per_market=args.held_out_assets_per_market,
        created_at=args.created_at,
    )
    print(
        {
            "inventory_id": inventory.inventory_id,
            "path": args.output.as_posix(),
            "sha256": sha256_file(args.output),
            "source_file_count": inventory.source_file_count,
            "selected_symbol_count": inventory.selected_symbol_count,
            "quarantined_file_count": inventory.quarantined_file_count,
        }
    )


if __name__ == "__main__":
    main()

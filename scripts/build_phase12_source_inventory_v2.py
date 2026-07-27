"""Build the cutoff-safe Phase 12 source inventory without future selection data."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

from crossmarket_agentgym.data.manifests import sha256_file
from crossmarket_agentgym.experiments.source_inventory import (
    build_source_inventory_v2,
)


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
        default=Path("experiments/data/source_inventory_v2.json"),
    )
    parser.add_argument("--ordering-salt", default="CrossMarketAgentGym-protocol-v2")
    parser.add_argument(
        "--experiment-start",
        type=date.fromisoformat,
        default=date(2021, 1, 4),
    )
    parser.add_argument(
        "--experiment-end",
        type=date.fromisoformat,
        default=date(2025, 9, 30),
    )
    parser.add_argument(
        "--selection-cutoff",
        type=date.fromisoformat,
        default=date(2021, 2, 1),
    )
    parser.add_argument("--assets-per-market", type=int, default=20)
    parser.add_argument("--held-out-assets-per-market", type=int, default=4)
    parser.add_argument("--created-at", type=datetime.fromisoformat, required=True)
    return parser.parse_args()


def main() -> None:
    """Build once and print the cutoff-safety and censoring evidence."""
    args = parse_args()
    inventory = build_source_inventory_v2(
        data_config=args.data_config,
        output_path=args.output,
        ordering_salt=args.ordering_salt,
        experiment_start=args.experiment_start,
        experiment_end=args.experiment_end,
        selection_cutoff=args.selection_cutoff,
        assets_per_market=args.assets_per_market,
        held_out_assets_per_market=args.held_out_assets_per_market,
        created_at=args.created_at,
    )
    selected = [
        record
        for record in inventory.files
        if record.selection_status in {"training_universe", "held_out_unseen"}
    ]
    print(
        json.dumps(
            {
                "inventory_id": inventory.inventory_id,
                "path": args.output.as_posix(),
                "sha256": sha256_file(args.output),
                "source_file_count": inventory.source_file_count,
                "selected_symbol_count": inventory.selected_symbol_count,
                "quarantined_file_count": inventory.quarantined_file_count,
                "future_data_used_for_source_selection": (
                    inventory.future_data_used_for_source_selection
                ),
                "selected_sources_censored_after_cutoff": sum(
                    record.censored_from_position is not None for record in selected
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

"""Correct global post-cutoff ordering failures without changing universe selection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from crossmarket_agentgym.data.manifests import sha256_file
from crossmarket_agentgym.experiments.source_inventory import (
    SourceInventory,
    load_source_inventory,
)

_GLOBAL_SEQUENCE_ERRORS = {"unsorted_trade_date", "duplicate_primary_key"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("experiments/data/source_inventory_v2.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiments/data/source_inventory_v3.json"),
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"versioned inventory already exists: {args.output}")
    source = load_source_inventory(args.input)
    if source.inventory_id != "source-inventory-v2":
        raise ValueError("inventory-v3 must derive from immutable inventory-v2")
    records = []
    corrected = 0
    for record in source.files:
        global_error = bool(
            _GLOBAL_SEQUENCE_ERRORS.intersection(record.post_cutoff_issue_codes)
        )
        if global_error and record.selection_quality_valid:
            if (
                record.selection_row_count is None
                or record.selection_date_start is None
                or record.selection_date_end is None
                or record.selection_information_cutoff is None
            ):
                raise ValueError(f"global censor lacks cutoff evidence: {record.path}")
            records.append(
                record.model_copy(
                    update={
                        "date_start": record.selection_date_start,
                        "date_end": record.selection_date_end,
                        "accepted_ohlcv_row_count": record.selection_row_count,
                        "censor_mode": "selection_window_only",
                        "censored_from_position": None,
                        "censored_from_date": None,
                        "censored_after_date": (
                            record.selection_information_cutoff
                        ),
                    }
                )
            )
            corrected += 1
        elif record.censored_from_position is not None:
            records.append(
                record.model_copy(
                    update={
                        "censor_mode": "prefix_before_first_invalid_position"
                    }
                )
            )
        else:
            records.append(record.model_copy(update={"censor_mode": "none"}))
    inventory = SourceInventory.model_validate(
        source.model_dump()
        | {
            "inventory_id": "source-inventory-v3",
            "protocol_id": "protocol-v4",
            "files": tuple(records),
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            inventory.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "inventory_id": inventory.inventory_id,
                "sha256": sha256_file(args.output),
                "global_sequence_sources_corrected": corrected,
                "future_data_used_for_source_selection": (
                    inventory.future_data_used_for_source_selection
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

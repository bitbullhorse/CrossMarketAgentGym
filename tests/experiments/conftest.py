"""Deterministic Phase 12 test fixtures."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from crossmarket_agentgym.data.manifests import sha256_file
from crossmarket_agentgym.data.sample import generate_sample_dataset
from crossmarket_agentgym.experiments.models import (
    DateInterval,
    WalkForwardFold,
)
from crossmarket_agentgym.experiments.protocol import load_protocol


@pytest.fixture
def formal_sample(tmp_path: Path) -> tuple[Path, object]:
    root = tmp_path / "workspace"
    dataset = root / "data" / "sample"
    generate_sample_dataset(dataset)
    inventory_path = root / "experiments" / "data" / "inventory.json"
    inventory_path.parent.mkdir(parents=True)
    inventory_path.write_text(
        json.dumps(
            {
                "training_symbols": {
                    "CN": ["000001"],
                    "HK": ["0001.HK"],
                    "JP": ["1301.T"],
                    "US": ["A"],
                },
                "held_out_symbols": {"CN": [], "HK": [], "JP": [], "US": []},
            }
        ),
        encoding="utf-8",
    )
    prompt_source = root / "experiments" / "agents" / "prompt_bundle_v1.json"
    prompt_source.parent.mkdir(parents=True)
    prompt_source.write_bytes(
        Path("experiments/agents/prompt_bundle_v1.json").read_bytes()
    )
    protocol = load_protocol(Path("experiments/protocol_v4.yaml"))
    folds = (
        WalkForwardFold(
            fold_id="fold_01",
            train=DateInterval(start=date(2024, 1, 3), end=date(2024, 1, 3)),
            validation=DateInterval(start=date(2024, 1, 4), end=date(2024, 1, 4)),
        ),
        WalkForwardFold(
            fold_id="fold_02",
            train=DateInterval(start=date(2024, 1, 3), end=date(2024, 1, 3)),
            validation=DateInterval(start=date(2024, 1, 4), end=date(2024, 1, 4)),
        ),
        WalkForwardFold(
            fold_id="fold_03",
            train=DateInterval(start=date(2024, 1, 3), end=date(2024, 1, 3)),
            validation=DateInterval(start=date(2024, 1, 4), end=date(2024, 1, 4)),
        ),
    )
    protocol = protocol.model_copy(
        update={
            "dataset": protocol.dataset.model_copy(
                update={
                    "source_inventory": inventory_path.relative_to(root),
                    "source_inventory_sha256": sha256_file(inventory_path),
                    "processed_root": dataset.relative_to(root),
                    "processed_manifest": (
                        dataset / "dataset_manifest.json"
                    ).relative_to(root),
                    "processed_manifest_sha256": sha256_file(
                        dataset / "dataset_manifest.json"
                    ),
                }
            ),
            "partitions": protocol.partitions.model_copy(
                update={
                    "train": DateInterval(
                        start=date(2024, 1, 3),
                        end=date(2024, 1, 3),
                    ),
                    "validation": DateInterval(
                        start=date(2024, 1, 4),
                        end=date(2024, 1, 4),
                    ),
                    "test": DateInterval(
                        start=date(2024, 1, 5),
                        end=date(2024, 1, 6),
                    ),
                    "walk_forward": folds,
                }
            ),
            "drl": protocol.drl.model_copy(
                update={
                    "lookback": 1,
                    "total_timesteps": 8,
                    "evaluation_episodes": 2,
                }
            ),
            "hpo": protocol.hpo.model_copy(
                update={
                    "trials_per_searcher": 2,
                    "timesteps_per_trial": 2,
                }
            ),
            "execution": protocol.execution.model_copy(
                update={
                    "max_asset_weight": 0.35,
                    "max_market_weight": 0.35,
                }
            ),
        }
    )
    return root, protocol

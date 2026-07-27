"""Static and executable leakage gates for the frozen formal protocol."""

from __future__ import annotations

import inspect
from pathlib import Path

from crossmarket_agentgym.experiments.hpo_runs import _locked_test, _run_search
from crossmarket_agentgym.experiments.matrix import build_run_matrix
from crossmarket_agentgym.experiments.protocol import load_protocol, sha256_file
from crossmarket_agentgym.experiments.source_inventory import load_source_inventory
from crossmarket_agentgym.features.normalization import TrainOnlyStandardizer


def test_phase12_protocol_hash_and_partition_contract_are_frozen() -> None:
    protocol_path = Path("experiments/protocol_v4.yaml")
    protocol = load_protocol(protocol_path)
    assert (
        Path("experiments/protocol_v4.sha256").read_text(encoding="utf-8").split()[0]
        == sha256_file(protocol_path)
    )
    assert protocol.partitions.random_time_shuffle is False
    assert protocol.dataset.selection.allow_row_repair is False
    assert protocol.hpo.test_partition_visible_during_search is False
    assert protocol.agents.account_state_mutation is False
    assert protocol.agents.deterministic_risk_layer_bypass is False


def test_hpo_matrix_never_grants_test_for_selection() -> None:
    protocol = load_protocol(Path("experiments/protocol_v4.yaml"))
    matrix = build_run_matrix(
        protocol,
        protocol_sha256="a" * 64,
        code_commit="b" * 40,
    )
    hpo = [task for task in matrix.tasks if task.group == "F"]
    assert len(hpo) == 40
    assert all(
        task.allowed_selection_partitions == ("train", "validation")
        for task in hpo
    )
    assert all("test" not in task.allowed_selection_partitions for task in hpo)
    assert all(task.test_access == "locked_final_once" for task in hpo)
    assert all(task.run_id.startswith("p12v4m6-") for task in hpo)


def test_hpo_search_and_locked_test_are_separate_code_paths() -> None:
    search_source = inspect.getsource(_run_search)
    locked_source = inspect.getsource(_locked_test)
    assert "evaluate_saved_run" not in search_source
    assert 'partition="test"' not in search_source
    assert "test_metrics" not in search_source
    assert "configuration_lock.json" in locked_source
    assert locked_source.index("configuration_lock.json") < locked_source.index(
        "evaluate_saved_run"
    )
    assert "TrainOnlyStandardizer" not in search_source
    assert TrainOnlyStandardizer.__name__ == "TrainOnlyStandardizer"


def test_global_sequence_failures_keep_only_formation_window() -> None:
    protocol = load_protocol(Path("experiments/protocol_v4.yaml"))
    inventory = load_source_inventory(
        Path("experiments/data/source_inventory_v3.json")
    )
    global_codes = {"unsorted_trade_date", "duplicate_primary_key"}
    affected = [
        record
        for record in inventory.files
        if global_codes.intersection(record.post_cutoff_issue_codes)
        and record.selection_quality_valid
    ]
    assert affected
    assert all(record.censor_mode == "selection_window_only" for record in affected)
    assert all(
        record.date_end is not None
        and record.date_end
        <= protocol.dataset.selection.selection_information_cutoff
        for record in affected
    )

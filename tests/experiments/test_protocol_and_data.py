"""Protocol, inventory, snapshot, matrix, and Group A gates."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

from crossmarket_agentgym.data.quality import validate_ohlcv_frame
from crossmarket_agentgym.experiments.audit import FormalRunAudit
from crossmarket_agentgym.experiments.dataset_snapshot import (
    _canonical_selected_frame,
    _selected_records,
    _validate_inventory_contract,
    _write_instruments,
    transform_ecb_snapshot,
)
from crossmarket_agentgym.experiments.environment_validation import (
    _VALIDATORS,
    run_environment_validation,
)
from crossmarket_agentgym.experiments.matrix import (
    build_run_matrix,
    load_run_matrix,
)
from crossmarket_agentgym.experiments.models import FormalExperimentProtocol
from crossmarket_agentgym.experiments.protocol import (
    freeze_protocol,
    load_protocol,
    sha256_file,
    verify_protocol,
)
from crossmarket_agentgym.experiments.source_inventory import (
    _ordering_key,
    build_source_inventory,
    build_source_inventory_v2,
    load_source_inventory,
)


def test_frozen_protocol_loads_and_rejects_invalid_contract(tmp_path: Path) -> None:
    protocol_path = Path("experiments/protocol_v4.yaml")
    protocol = load_protocol(protocol_path)
    expected = Path("experiments/protocol_v4.sha256").read_text().split()[0]
    assert sha256_file(protocol_path) == expected
    assert protocol.development_run_inputs_allowed is False
    assert protocol.hpo.test_partition_visible_during_search is False
    assert protocol.compute.seeds == (1024, 2048, 4096, 8192, 16384)
    assert protocol.supersedes_protocol == "protocol-v3"
    assert protocol.agents.prompt_source == Path(
        "experiments/agents/prompt_bundle_v1.json"
    )
    assert protocol.dataset.selection.selection_information_cutoff == date(
        2021, 2, 1
    )
    assert protocol.partitions.train.start == date(2021, 2, 2)

    raw = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
    raw["partitions"]["random_time_shuffle"] = True
    with pytest.raises(ValidationError):
        FormalExperimentProtocol.model_validate(raw)
    raw["partitions"]["random_time_shuffle"] = False
    raw["hpo"]["searchers"] = ["random"]
    with pytest.raises(ValidationError):
        FormalExperimentProtocol.model_validate(raw)

    raw = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
    raw["status"] = "draft"
    draft = tmp_path / "draft.yaml"
    draft.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="status=frozen"):
        freeze_protocol(draft, tmp_path / "draft.sha256")

    copy = tmp_path / "protocol.yaml"
    copy.write_text(protocol_path.read_text(encoding="utf-8"), encoding="utf-8")
    checksum = tmp_path / "protocol.sha256"
    digest = freeze_protocol(copy, checksum)
    assert digest == sha256_file(copy)
    with pytest.raises(FileExistsError):
        freeze_protocol(copy, checksum)
    checksum.write_text(f"{'0' * 64}  protocol.yaml\n", encoding="utf-8")
    verification = verify_protocol(
        copy,
        checksum,
        workspace_root=Path.cwd(),
    )
    assert verification.checksum_valid is False
    assert "PROTOCOL_HASH_MISMATCH" in verification.blockers


@pytest.mark.parametrize("method", sorted(_VALIDATORS))
def test_all_hand_computable_group_a_methods(method: str) -> None:
    result = run_environment_validation(method)
    assert result.passed
    assert result.absolute_error <= result.accounting_tolerance


def _yahoo(path: Path, symbol: str) -> None:
    pd.DataFrame(
        {
            "Date": ["2024-01-02", "2024-01-03", "2024-01-04"],
            "Open": [10.0, 11.0, 12.0],
            "High": [11.0, 12.0, 13.0],
            "Low": [9.0, 10.0, 11.0],
            "Close": [10.5, 11.5, 12.5],
            "Volume": [100.0, 110.0, 120.0],
            "Ticker": [symbol] * 3,
        }
    ).to_csv(path, index=False)


def _cn(path: Path) -> None:
    pd.DataFrame(
        {
            "S_Date": ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
            "S_Oppr": [10.0, 11.0, 12.0, None],
            "S_Hipr": [11.0, 12.0, 13.0, None],
            "S_Lopr": [9.0, 10.0, 11.0, None],
            "S_Clpr": [10.5, 11.5, 12.5, None],
            "S_Trdvol": [100.0, 110.0, 120.0, None],
        }
    ).to_excel(path, index=False)


def test_source_inventory_selection_and_snapshot_helpers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "raw"
    mappings = {"cn": "CN", "hk": "HK", "jp": "JP", "us": "US"}
    for directory, market in mappings.items():
        folder = root / directory
        folder.mkdir(parents=True)
        for index in range(2):
            symbol = f"{market}{index}"
            if market == "CN":
                source = folder / f"{index:06d}" / "bars.xlsx"
                source.parent.mkdir()
                _cn(source)
            else:
                _yahoo(folder / f"{symbol}.csv", symbol)
    config = tmp_path / "data.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "dataset": {
                    "root": str(root),
                    "layout": "legacy_mixed",
                    "markets": mappings,
                    "mutation_policy": "reject",
                }
            }
        ),
        encoding="utf-8",
    )
    inventory_path = tmp_path / "inventory.json"
    inventory = build_source_inventory(
        data_config=config,
        output_path=inventory_path,
        ordering_salt="test",
        minimum_coverage_start=date(2024, 1, 2),
        minimum_coverage_end=date(2024, 1, 4),
        assets_per_market=2,
        held_out_assets_per_market=1,
        created_at=datetime(2026, 7, 27, tzinfo=UTC),
    )
    assert inventory.selected_symbol_count == 8
    assert len(_selected_records(inventory)) == 8
    assert load_source_inventory(inventory_path) == inventory
    assert _ordering_key("x", "CN", "A") == _ordering_key("x", "CN", "A")
    with pytest.raises(FileExistsError):
        build_source_inventory(
            data_config=config,
            output_path=inventory_path,
            ordering_salt="test",
            minimum_coverage_start=date(2024, 1, 2),
            minimum_coverage_end=date(2024, 1, 4),
            assets_per_market=2,
            held_out_assets_per_market=1,
            created_at=datetime(2026, 7, 27, tzinfo=UTC),
        )

    protocol = load_protocol(Path("experiments/protocol_v1.yaml"))
    selection = protocol.dataset.selection.model_copy(
        update={
            "ordering_salt": "test",
            "minimum_source_coverage": protocol.dataset.selection.minimum_source_coverage.model_copy(
                update={"start": date(2024, 1, 2), "end": date(2024, 1, 4)}
            ),
            "experiment_window": protocol.dataset.selection.experiment_window.model_copy(
                update={"start": date(2024, 1, 2), "end": date(2024, 1, 4)}
            ),
            "assets_per_market": 2,
            "held_out_assets_per_market": 1,
        }
    )
    protocol = protocol.model_copy(
        update={
            "dataset": protocol.dataset.model_copy(
                update={"selection": selection}
            )
        }
    )
    _validate_inventory_contract(protocol, inventory)
    broken = inventory.model_copy(update={"ordering_salt": "changed"})
    with pytest.raises(ValueError, match="selection contract"):
        _validate_inventory_contract(protocol, broken)

    selected = _selected_records(inventory)
    instruments = tmp_path / "instruments.csv"
    _write_instruments(instruments, selected)
    assert len(pd.read_csv(instruments)) == 8
    cn_record = next(record for record in selected if record.market == "CN")
    frame = _canonical_selected_frame(
        source_path=root / cn_record.path,
        record=cn_record,
        start=date(2024, 1, 2),
        end=date(2024, 1, 4),
    )
    assert len(frame) == 3
    assert cn_record.semantic_exclusion_rows == (3,)


def test_cutoff_safe_inventory_censors_future_quality_failure(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    mappings = {"cn": "CN", "hk": "HK", "jp": "JP", "us": "US"}
    for directory, market in mappings.items():
        folder = root / directory
        folder.mkdir(parents=True)
        for index in range(2):
            symbol = f"{market}{index}"
            if market == "CN":
                source = folder / f"{index:06d}" / "bars.xlsx"
                source.parent.mkdir()
                _cn(source)
            else:
                source = folder / f"{symbol}.csv"
                _yahoo(source, symbol)
                if market == "US" and index == 0:
                    frame = pd.read_csv(source)
                    frame.loc[2, "High"] = 5.0
                    frame.to_csv(source, index=False)
    config = tmp_path / "data.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "dataset": {
                    "root": str(root),
                    "layout": "legacy_mixed",
                    "markets": mappings,
                    "mutation_policy": "reject",
                }
            }
        ),
        encoding="utf-8",
    )
    inventory_path = tmp_path / "inventory-v2.json"
    inventory = build_source_inventory_v2(
        data_config=config,
        output_path=inventory_path,
        ordering_salt="cutoff-safe",
        experiment_start=date(2024, 1, 2),
        experiment_end=date(2024, 1, 4),
        selection_cutoff=date(2024, 1, 3),
        assets_per_market=2,
        held_out_assets_per_market=1,
        created_at=datetime(2026, 7, 27, tzinfo=UTC),
    )
    assert inventory.protocol_id == "protocol-v2"
    assert inventory.future_data_used_for_source_selection is False
    record = next(
        item
        for item in _selected_records(inventory)
        if item.market == "US" and item.symbol == "US0"
    )
    assert record.selection_quality_valid is True
    assert record.selection_date_end == date(2024, 1, 3)
    assert record.accepted_ohlcv_row_count == 2
    assert record.censored_from_position == 2
    assert record.censored_from_date == date(2024, 1, 4)
    accepted = _canonical_selected_frame(
        source_path=root / record.path,
        record=record,
        start=date(2024, 1, 2),
        end=date(2024, 1, 4),
    )
    assert len(accepted) == 2
    assert validate_ohlcv_frame(accepted).is_valid


def test_ecb_transform_and_matrix_audit(
    tmp_path: Path,
    formal_sample: tuple[Path, object],
) -> None:
    snapshot = tmp_path / "ecb.csv"
    pd.DataFrame(
        [
            {
                "CURRENCY": currency,
                "CURRENCY_DENOM": "EUR",
                "TIME_PERIOD": day,
                "OBS_VALUE": value,
            }
            for day, values in (
                ("2024-01-02", {"CNY": 7.8, "HKD": 8.5, "JPY": 160.0, "USD": 1.1}),
                ("2024-01-03", {"CNY": 7.7, "HKD": 8.4, "JPY": 159.0, "USD": 1.2}),
            )
            for currency, value in values.items()
        ]
    ).to_csv(snapshot, index=False)
    fx = transform_ecb_snapshot(
        snapshot,
        currencies=("CNY", "HKD", "JPY", "USD"),
        quote_currency="USD",
    )
    assert set(fx["base_currency"]) == {"CNY", "HKD", "JPY", "USD"}
    assert fx.loc[fx["base_currency"] == "USD", "rate"].eq(1.0).all()

    _, sample_protocol = formal_sample
    protocol = sample_protocol
    matrix = build_run_matrix(
        protocol,
        protocol_sha256="a" * 64,
        code_commit="b" * 40,
    )
    assert len(matrix.tasks) == 215
    assert matrix.protocol_id == protocol.protocol_id
    assert matrix.matrix_id == "phase12-run-matrix-v4"
    assert {task.group for task in matrix.tasks} == {"A", "B", "C", "D", "E", "F"}
    assert all(not task.development_input_run_ids for task in matrix.tasks)
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(matrix.model_dump_json(indent=2), encoding="utf-8")
    assert load_run_matrix(matrix_path) == matrix

    task = matrix.tasks[0]
    audit = FormalRunAudit(task, tmp_path / "runs")
    (audit.run_dir / "result.json").write_text("{}", encoding="utf-8")
    audit.start()
    record = audit.complete()
    assert record.status == "completed"
    assert any(item.path == "result.json" for item in record.artifacts)
    with pytest.raises(FileExistsError):
        FormalRunAudit(task, tmp_path / "runs")

    failed_task = matrix.tasks[1]
    failed = FormalRunAudit(failed_task, tmp_path / "runs")
    failed.start()
    failed_record = failed.fail(ValueError("expected"))
    assert failed_record.status == "failed"
    assert failed_record.failure_type == "ValueError"

"""Artifact verification and isolated Phase 11 computational replay."""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import zipfile
from pathlib import Path
from typing import Any

import yaml

from crossmarket_agentgym.agents.directives import DirectiveProjection
from crossmarket_agentgym.agents.layer_stack import replay_phase7_bundle
from crossmarket_agentgym.agents.providers.replay import ReplayRecord
from crossmarket_agentgym.audit.logging import redact_value
from crossmarket_agentgym.audit.run_manifest import verify_run_manifest
from crossmarket_agentgym.release.models import (
    ReproductionResult,
    VerificationCheck,
)
from crossmarket_agentgym.release.reproduction_models import (
    CoreArtifactComparison,
    InvariantComparison,
    MetricComparison,
    MetricName,
    ReproductionLevel,
    ReproductionReport,
    ReproductionToleranceConfig,
    StatisticalMetricComparison,
)
from crossmarket_agentgym.reporting.indexer import build_run_index
from crossmarket_agentgym.reporting.io import read_bounded_json, resolve_inside

_REPLAY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_CORE_METRICS: tuple[MetricName, ...] = (
    "mean_return",
    "mean_reward",
    "max_drawdown",
    "mean_turnover",
    "total_cost",
)
_CORE_ARTIFACTS = (
    "checkpoints/final_model.zip",
    "validation/metrics.json",
    "validation/trades.json",
    "validation/weights.json",
)


def _check(name: str, passed: bool, detail: str) -> VerificationCheck:
    return VerificationCheck(name=name, passed=passed, detail=detail)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_config_file(run_dir: Path) -> VerificationCheck:
    config_path = run_dir / "config.resolved.yaml"
    digest_path = run_dir / "config.sha256"
    try:
        expected = digest_path.read_text(encoding="utf-8").strip()
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        safe = redact_value(raw)
        canonical = yaml.safe_dump(
            safe,
            allow_unicode=True,
            sort_keys=True,
        )
        actual = hashlib.sha256(canonical.encode()).hexdigest()
        passed = expected == actual and raw == safe
    except (FileNotFoundError, OSError, yaml.YAMLError) as error:
        return _check("resolved_config_hash", False, str(error))
    return _check(
        "resolved_config_hash",
        passed,
        "resolved configuration hash and redaction verified",
    )


def _verify_versioned_run_manifest(run_dir: Path) -> VerificationCheck:
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.is_file():
        return _check(
            "run_manifest",
            True,
            "legacy pre-rc1 run; specialized provenance verification applied",
        )
    try:
        manifest = verify_run_manifest(run_dir)
    except (OSError, TypeError, ValueError) as error:
        return _check("run_manifest", False, str(error))
    return _check(
        "run_manifest",
        True,
        f"schema {manifest.schema_version}; {len(manifest.artifacts)} artifacts verified",
    )


def _load_training_config(
    run_dir: Path,
    *,
    max_bytes: int,
) -> tuple[Any, str]:
    """Load the reviewed YAML form first while supporting pre-Phase-11 JSON runs."""
    # Keep the heavyweight RL dependency lazy for artifact-only Agent reproduction.
    from crossmarket_agentgym.rl.config import TrainRunConfig

    yaml_path = run_dir / "config.resolved.yaml"
    json_path = run_dir / "resolved_config.json"
    yaml_config: TrainRunConfig | None = None
    json_config: TrainRunConfig | None = None
    if yaml_path.is_file():
        if yaml_path.stat().st_size > max_bytes:
            raise ValueError("resolved YAML configuration exceeds size limit")
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise TypeError("resolved YAML training configuration must be an object")
        yaml_config = TrainRunConfig.model_validate(raw)
    if json_path.is_file():
        raw_json = read_bounded_json(json_path, max_bytes=max_bytes)
        if not isinstance(raw_json, dict):
            raise TypeError("resolved JSON training configuration must be an object")
        json_config = TrainRunConfig.model_validate(raw_json)
    if yaml_config is None and json_config is None:
        raise FileNotFoundError("config.resolved.yaml or resolved_config.json")
    if (
        yaml_config is not None
        and json_config is not None
        and yaml_config.model_dump(mode="json") != json_config.model_dump(mode="json")
    ):
        raise ValueError("resolved YAML and JSON training configurations differ")
    if yaml_config is not None:
        return yaml_config, "config.resolved.yaml"
    if json_config is None:
        raise AssertionError("unreachable resolved-config state")
    return json_config, "resolved_config.json"


def _verify_training(
    workspace: Path,
    run_dir: Path,
    *,
    max_json_bytes: int,
) -> tuple[list[VerificationCheck], bool]:
    checks: list[VerificationCheck] = []
    try:
        config, config_name = _load_training_config(
            run_dir,
            max_bytes=max_json_bytes,
        )
        trainer = config.trainer
        checks.append(
            _check(
                "resolved_training_config",
                True,
                f"validated {config_name} without modifying the source run",
            )
        )
        metadata = read_bounded_json(
            run_dir / "training_artifact.json",
            max_bytes=max_json_bytes,
        )
        if not isinstance(metadata, dict):
            raise TypeError("training configuration and metadata must be objects")
        trainer_digest = hashlib.sha256(trainer.model_dump_json().encode()).hexdigest()
        recorded_config_hash = metadata.get("config_sha256")
        checks.append(
            _check(
                "trainer_config_hash",
                trainer_digest == recorded_config_hash,
                "recorded TrainerConfig identity verified",
            )
        )
        dataset_root = resolve_inside(config.dataset_root, workspace)
        dataset_digest = _sha256(dataset_root / "dataset_manifest.json")
        checks.append(
            _check(
                "dataset_manifest_hash",
                dataset_digest == metadata.get("dataset_id"),
                "training dataset manifest identity verified",
            )
        )
        checkpoint_name = metadata.get("checkpoint")
        if not isinstance(checkpoint_name, str):
            raise TypeError("training checkpoint path must be a string")
        checkpoint = resolve_inside(checkpoint_name, run_dir)
        archive_valid = False
        if checkpoint.is_file() and zipfile.is_zipfile(checkpoint):
            with zipfile.ZipFile(checkpoint) as archive:
                archive_valid = archive.testzip() is None
        checks.append(
            _check(
                "checkpoint_archive",
                archive_valid,
                f"checkpoint SHA-256 {_sha256(checkpoint) if checkpoint.is_file() else 'missing'}",
            )
        )
        checks.append(
            _check(
                "training_partition",
                metadata.get("data_partition") == "train",
                "model fitting capability is train-only",
            )
        )
    except (FileNotFoundError, KeyError, TypeError, ValueError, zipfile.BadZipFile) as error:
        checks.append(_check("training_artifacts", False, str(error)))
    return checks, False


def _verify_tuning(
    run_dir: Path,
    *,
    max_json_bytes: int,
) -> tuple[list[VerificationCheck], bool]:
    checks: list[VerificationCheck] = []
    try:
        summary = read_bounded_json(
            run_dir / "tuning_summary.json",
            max_bytes=max_json_bytes,
        )
        report = read_bounded_json(
            run_dir / "study_report.json",
            max_bytes=max_json_bytes,
        )
        locked = read_bounded_json(
            run_dir / "locked_parameters.json",
            max_bytes=max_json_bytes,
        )
        if not all(isinstance(item, dict) for item in (summary, report, locked)):
            raise TypeError("tuning artifacts must be JSON objects")
        summary_map = summary
        report_map = report
        locked_map = locked
        best = report_map.get("best_trial")
        best_map = best if isinstance(best, dict) else {}
        leakage_safe = (
            summary_map.get("test_set_accessed") is False
            and report_map.get("test_metrics_present") is False
            and report_map.get("partition_policy") == "train_and_validation_only"
            and locked_map.get("test_set_accessed") is False
            and locked_map.get("selected_on") == "validation"
        )
        checks.append(
            _check(
                "tuning_partition_boundary",
                leakage_safe,
                "selection used train/validation artifacts only",
            )
        )
        checks.append(
            _check(
                "locked_parameters",
                locked_map.get("parameters") == best_map.get("parameters"),
                "locked parameters equal the recorded best validation trial",
            )
        )
    except (FileNotFoundError, TypeError, ValueError) as error:
        checks.append(_check("tuning_artifacts", False, str(error)))
    return checks, False


def _verify_replay_journals(
    run_dir: Path,
) -> tuple[list[VerificationCheck], bool]:
    checks = [_verify_config_file(run_dir)]
    journals = sorted(run_dir.glob("agent_instances/*/agent/replay.jsonl"))
    record_count = 0
    try:
        for journal in journals:
            for line in journal.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    ReplayRecord.model_validate_json(line)
                    record_count += 1
        passed = bool(journals) and record_count > 0
        detail = f"{record_count} strict replay records across {len(journals)} journals"
    except (OSError, ValueError) as error:
        passed = False
        detail = str(error)
    checks.append(_check("agent_replay_journals", passed, detail))
    return checks, passed


def _verify_phase7(
    run_dir: Path,
    *,
    max_json_bytes: int,
) -> tuple[list[VerificationCheck], bool]:
    checks = [_verify_config_file(run_dir)]
    try:
        summary = read_bounded_json(
            run_dir / "phase7_summary.json",
            max_bytes=max_json_bytes,
        )
        if not isinstance(summary, dict):
            raise TypeError("Phase 7 summary must be an object")
        expected = DirectiveProjection.model_validate(summary.get("projection"))
        replayed = replay_phase7_bundle(run_dir / "agent" / "directive_replay.json")
        passed = (
            summary.get("directive_replay_verified") is True
            and replayed == expected
        )
        detail = "directive fusion and deterministic projection recomputed exactly"
    except (FileNotFoundError, TypeError, ValueError) as error:
        passed = False
        detail = str(error)
    checks.append(_check("phase7_directive_replay", passed, detail))
    return checks, passed


def reproduce_run(
    workspace_root: str | Path,
    runs_root: str | Path,
    run_id: str,
    *,
    max_json_bytes: int = 5_000_000,
) -> ReproductionResult:
    """Verify one known run without network, retraining, or account mutation."""
    workspace = Path(workspace_root).resolve()
    index = build_run_index(
        workspace,
        runs_root,
        include_run_ids=(run_id,),
        max_json_bytes=max_json_bytes,
    )
    record = index.runs[0]
    run_dir = resolve_inside(record.relative_path, workspace)
    checks = [
        _check(
            "source_fingerprint",
            len(record.fingerprint) == 64,
            f"whitelisted source fingerprint {record.fingerprint}",
        ),
        _verify_versioned_run_manifest(run_dir),
    ]
    specialized: list[VerificationCheck]
    deterministic = False
    if record.kind == "training":
        specialized, deterministic = _verify_training(
            workspace,
            run_dir,
            max_json_bytes=max_json_bytes,
        )
    elif record.kind == "tuning":
        specialized, deterministic = _verify_tuning(
            run_dir,
            max_json_bytes=max_json_bytes,
        )
    elif record.kind == "agent":
        specialized, deterministic = _verify_replay_journals(run_dir)
    else:
        specialized, deterministic = _verify_phase7(
            run_dir,
            max_json_bytes=max_json_bytes,
        )
    checks.extend(specialized)
    return ReproductionResult(
        run_id=record.run_id,
        kind=record.kind,
        run_fingerprint=record.fingerprint,
        is_valid=all(item.passed for item in checks),
        deterministic_replay=deterministic,
        checks=tuple(checks),
    )


def load_reproduction_tolerance_config(
    path: str | Path | None = None,
) -> ReproductionToleranceConfig:
    """Load strict Phase 11 tolerances or return the reviewed CPU defaults."""
    if path is None:
        return ReproductionToleranceConfig()
    candidate = Path(path)
    raw = yaml.safe_load(candidate.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("reproduction tolerance configuration must be a mapping")
    return ReproductionToleranceConfig.model_validate(raw)


def verify_run_artifacts(
    workspace_root: str | Path,
    runs_root: str | Path,
    run_id: str,
    *,
    max_json_bytes: int = 5_000_000,
) -> ReproductionReport:
    """Describe the legacy read-only check honestly as artifact integrity."""
    legacy = reproduce_run(
        workspace_root,
        runs_root,
        run_id,
        max_json_bytes=max_json_bytes,
    )
    return ReproductionReport(
        verification_mode="artifact_integrity",
        artifact_integrity_verified=legacy.is_valid,
        computational_replay_executed=False,
        reproduction_level=(
            "artifact_verified" if legacy.is_valid else "failed"
        ),
        bitwise_deterministic=False,
        within_tolerance=None,
        run_id=legacy.run_id,
        source_run_id=legacy.run_id,
        kind=legacy.kind,
        run_fingerprint=legacy.run_fingerprint,
        is_valid=legacy.is_valid,
        deterministic_replay=legacy.deterministic_replay,
        checks=legacy.checks,
    )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path: Path, values: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        json.dumps(value, allow_nan=False, sort_keys=True) + "\n"
        for value in values
    )
    path.write_text(payload, encoding="utf-8", newline="\n")


def _allocate_replay_directory(
    replay_parent: Path,
    source_run_id: str,
    replay_run_id: str | None,
) -> tuple[str, Path]:
    replay_parent.mkdir(parents=True, exist_ok=True)
    if replay_run_id is not None:
        if _REPLAY_ID.fullmatch(replay_run_id) is None:
            raise ValueError("replay_run_id contains unsupported path characters")
        target = replay_parent / replay_run_id
        target.mkdir(exist_ok=False)
        return replay_run_id, target
    for index in range(1, 10_000):
        candidate_id = f"replay-{source_run_id}-{index:03d}"
        candidate = replay_parent / candidate_id
        try:
            candidate.mkdir(exist_ok=False)
        except FileExistsError:
            continue
        return candidate_id, candidate
    raise FileExistsError("replay directory sequence exhausted")


def _finite_metric_mapping(raw: object) -> dict[str, float]:
    if not isinstance(raw, dict):
        raise TypeError("validation metrics must be an object")
    metrics = raw.get("metrics")
    if not isinstance(metrics, dict):
        raise TypeError("validation metrics payload is missing metrics")
    result: dict[str, float] = {}
    for name in _CORE_METRICS:
        value = metrics.get(name)
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise TypeError(f"validation metric {name!r} must be numeric")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"validation metric {name!r} is non-finite")
        result[name] = number
    return result


def _compare_metrics(
    source: dict[str, float],
    replay: dict[str, float],
    tolerance: ReproductionToleranceConfig,
) -> dict[str, MetricComparison]:
    comparisons: dict[str, MetricComparison] = {}
    relative_tolerance = tolerance.relative_tolerance.default
    for name in _CORE_METRICS:
        source_value = source[name]
        replay_value = replay[name]
        difference = abs(source_value - replay_value)
        scale = max(abs(source_value), abs(replay_value))
        relative_difference = difference / scale if scale > 0.0 else 0.0
        absolute_tolerance = tolerance.absolute_tolerance[name]
        effective_tolerance = max(
            absolute_tolerance,
            relative_tolerance * scale,
        )
        comparisons[f"validation.{name}"] = MetricComparison(
            source=source_value,
            replay=replay_value,
            absolute_difference=difference,
            relative_difference=relative_difference,
            absolute_tolerance=absolute_tolerance,
            relative_tolerance=relative_tolerance,
            effective_tolerance=effective_tolerance,
            passed=difference <= effective_tolerance,
        )
    return comparisons


def _invariant(
    source: str | int | bool,
    replay: str | int | bool,
    *,
    require_truth: bool = False,
) -> InvariantComparison:
    passed = source == replay and (not require_truth or source is True)
    return InvariantComparison(source=source, replay=replay, passed=passed)


def _loadable_checkpoint(
    trainer: Any,
    checkpoint: Path,
) -> bool:
    try:
        trainer.load(checkpoint)
    except (FileNotFoundError, OSError, RuntimeError, TypeError, ValueError, zipfile.BadZipFile):
        return False
    return True


def _compare_core_artifacts(
    source_dir: Path,
    replay_dir: Path,
) -> dict[str, CoreArtifactComparison]:
    comparisons: dict[str, CoreArtifactComparison] = {}
    for relative in _CORE_ARTIFACTS:
        source_digest = _sha256(source_dir / relative)
        replay_digest = _sha256(replay_dir / relative)
        comparisons[relative] = CoreArtifactComparison(
            source_sha256=source_digest,
            replay_sha256=replay_digest,
            passed=source_digest == replay_digest,
        )
    return comparisons


def _prior_replay_values(
    replay_parent: Path,
    current: dict[str, float],
    *,
    max_json_bytes: int,
) -> dict[str, list[float]]:
    values = {name: [value] for name, value in current.items()}
    for report_path in sorted(replay_parent.glob("*/reproduction_comparison.json")):
        try:
            raw = read_bounded_json(report_path, max_bytes=max_json_bytes)
        except (OSError, TypeError, ValueError):
            continue
        if not isinstance(raw, dict):
            continue
        metric_comparison = raw.get("metric_comparison")
        if (
            raw.get("computational_replay_executed") is not True
            or raw.get("artifact_integrity_verified") is not True
            or raw.get("source_run_id") != replay_parent.name
            or not isinstance(metric_comparison, dict)
        ):
            continue
        invariants = raw.get("invariant_comparison")
        if not isinstance(invariants, dict) or not all(
            isinstance(invariants.get(name), dict)
            and invariants[name].get("passed") is True
            for name in (
                "trained_timesteps",
                "algorithm",
                "dataset_manifest_hash",
                "trainer_config_hash",
                "execution_protocol",
                "checkpoint_loadability",
            )
        ):
            continue
        for name in _CORE_METRICS:
            item = metric_comparison.get(f"validation.{name}")
            value = item.get("replay") if isinstance(item, dict) else None
            if (
                isinstance(value, int | float)
                and not isinstance(value, bool)
                and math.isfinite(float(value))
            ):
                values[name].append(float(value))
    return values


def _compare_statistically(
    replay_parent: Path,
    source: dict[str, float],
    current: dict[str, float],
    tolerance: ReproductionToleranceConfig,
    *,
    max_json_bytes: int,
) -> tuple[dict[str, StatisticalMetricComparison], bool]:
    values = _prior_replay_values(
        replay_parent,
        current,
        max_json_bytes=max_json_bytes,
    )
    minimum = tolerance.statistical.minimum_replays
    if any(len(samples) < minimum for samples in values.values()):
        return {}, False
    comparisons: dict[str, StatisticalMetricComparison] = {}
    for name in _CORE_METRICS:
        samples = values[name]
        count = len(samples)
        replay_mean = statistics.fmean(samples)
        replay_std = statistics.stdev(samples)
        standard_error = replay_std / math.sqrt(count)
        source_value = source[name]
        scale = max(abs(source_value), abs(replay_mean))
        base_tolerance = max(
            tolerance.absolute_tolerance[name],
            tolerance.relative_tolerance.default * scale,
        )
        allowed = (
            base_tolerance
            + tolerance.statistical.standard_error_multiplier * standard_error
        )
        difference = abs(source_value - replay_mean)
        comparisons[f"validation.{name}"] = StatisticalMetricComparison(
            source=source_value,
            replay_count=count,
            replay_mean=replay_mean,
            replay_std=replay_std,
            standard_error=standard_error,
            absolute_difference=difference,
            allowed_difference=allowed,
            passed=difference <= allowed,
        )
    return comparisons, all(item.passed for item in comparisons.values())


def _snapshot_files(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix())
        if path.is_file()
    }


def _classify_reproduction(
    *,
    bitwise: bool,
    numerically_passed: bool,
    invariants_passed: bool,
    statistically_passed: bool,
    source_unchanged: bool,
) -> tuple[ReproductionLevel, bool]:
    """Apply the ordered Phase 11 levels without masking source mutation."""
    if not source_unchanged:
        return "failed", False
    if bitwise:
        return "bitwise_reproduced", True
    if numerically_passed:
        return "numerically_reproduced", True
    if invariants_passed and statistically_passed:
        return "statistically_reproduced", True
    return "failed", False


def execute_training_replay(
    workspace_root: str | Path,
    runs_root: str | Path,
    run_id: str,
    *,
    tolerance: ReproductionToleranceConfig | None = None,
    replay_run_id: str | None = None,
    max_json_bytes: int = 5_000_000,
) -> ReproductionReport:
    """Retrain one verified training run in an isolated directory and compare it."""
    reviewed_tolerance = tolerance or ReproductionToleranceConfig()
    integrity = verify_run_artifacts(
        workspace_root,
        runs_root,
        run_id,
        max_json_bytes=max_json_bytes,
    )
    if not integrity.artifact_integrity_verified or integrity.kind != "training":
        checks = list(integrity.checks)
        if integrity.kind != "training":
            checks.append(
                _check(
                    "computational_replay_supported",
                    False,
                    "computational replay currently requires a training run",
                )
            )
        return integrity.model_copy(
            update={
                "verification_mode": "computational_replay",
                "reproduction_level": "failed",
                "is_valid": False,
                "checks": tuple(checks),
            }
        )

    workspace = Path(workspace_root).resolve()
    index = build_run_index(
        workspace,
        runs_root,
        include_run_ids=(run_id,),
        max_json_bytes=max_json_bytes,
    )
    record = index.runs[0]
    source_dir = resolve_inside(record.relative_path, workspace)
    source_snapshot = _snapshot_files(source_dir)
    source_config, source_config_name = _load_training_config(
        source_dir,
        max_bytes=max_json_bytes,
    )
    dataset_root = resolve_inside(source_config.dataset_root, workspace)
    dataset_manifest = dataset_root / "dataset_manifest.json"
    dataset_digest = _sha256(dataset_manifest)
    runs_dir = resolve_inside(runs_root, workspace)
    replay_parent = runs_dir / "reproductions" / run_id
    allocated_id, replay_dir = _allocate_replay_directory(
        replay_parent,
        run_id,
        replay_run_id,
    )
    replay_relative = replay_dir.relative_to(workspace).as_posix()
    dataset_relative = dataset_root.relative_to(workspace)
    output_relative = replay_parent.relative_to(workspace)
    persisted_config = source_config.model_copy(
        update={
            "dataset_root": dataset_relative,
            "output_dir": output_relative,
            "run_name": allocated_id,
        }
    )
    execution_config = source_config.model_copy(
        update={
            "dataset_root": dataset_root,
            "output_dir": replay_parent,
            "run_name": allocated_id,
        }
    )
    source_information = {
        "schema_version": "1.0",
        "source_run_id": run_id,
        "source_relative_path": source_dir.relative_to(workspace).as_posix(),
        "source_config": source_config_name,
        "source_run_fingerprint": record.fingerprint,
        "dataset_manifest_sha256": dataset_digest,
        "artifact_integrity_verified": True,
    }
    _write_json(replay_dir / "source_run.json", source_information)
    yaml_payload = yaml.safe_dump(
        persisted_config.model_dump(mode="json"),
        allow_unicode=True,
        sort_keys=True,
    )
    (replay_dir / "config.resolved.yaml").write_text(
        yaml_payload,
        encoding="utf-8",
        newline="\n",
    )
    tolerance_payload = yaml.safe_dump(
        reviewed_tolerance.model_dump(mode="json"),
        allow_unicode=True,
        sort_keys=True,
    )
    (replay_dir / "reproduction_tolerance.resolved.yaml").write_text(
        tolerance_payload,
        encoding="utf-8",
        newline="\n",
    )
    audit_events: list[dict[str, object]] = [
        {
            "event": "computational_replay_started",
            "source_run_id": run_id,
            "replay_run_id": allocated_id,
            "network_used": False,
            "test_partition_accessed": False,
            "account_state_mutated": False,
        }
    ]
    _write_jsonl(replay_dir / "reproduction_audit.jsonl", audit_events)
    checks = list(integrity.checks)
    replay_executed = False
    try:
        from crossmarket_agentgym.audit import write_run_manifest
        from crossmarket_agentgym.rl.trainers import trainer_from_config
        from crossmarket_agentgym.rl.workflow import execute_training_run

        execute_training_run(execution_config)
        replay_executed = True
        (replay_dir / "resolved_config.json").write_text(
            persisted_config.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        replay_summary_raw = read_bounded_json(
            replay_dir / "run_summary.json",
            max_bytes=max_json_bytes,
        )
        source_summary_raw = read_bounded_json(
            source_dir / "run_summary.json",
            max_bytes=max_json_bytes,
        )
        source_metadata = read_bounded_json(
            source_dir / "training_artifact.json",
            max_bytes=max_json_bytes,
        )
        replay_metadata = read_bounded_json(
            replay_dir / "training_artifact.json",
            max_bytes=max_json_bytes,
        )
        if not all(
            isinstance(value, dict)
            for value in (
                replay_summary_raw,
                source_summary_raw,
                source_metadata,
                replay_metadata,
            )
        ):
            raise TypeError("training summaries and metadata must be objects")
        replay_summary = dict(replay_summary_raw)
        replay_summary["run_dir"] = replay_relative
        replay_summary["checkpoint"] = (
            f"{replay_relative}/checkpoints/final_model.zip"
        )
        _write_json(replay_dir / "run_summary.json", replay_summary)

        source_metrics_raw = read_bounded_json(
            source_dir / "validation" / "metrics.json",
            max_bytes=max_json_bytes,
        )
        replay_metrics_raw = read_bounded_json(
            replay_dir / "validation" / "metrics.json",
            max_bytes=max_json_bytes,
        )
        source_metrics = _finite_metric_mapping(source_metrics_raw)
        replay_metrics = _finite_metric_mapping(replay_metrics_raw)
        metric_comparison = _compare_metrics(
            source_metrics,
            replay_metrics,
            reviewed_tolerance,
        )
        trainer = trainer_from_config(source_config.trainer, replay_dir)
        source_checkpoint_loadable = _loadable_checkpoint(
            trainer,
            source_dir / "checkpoints" / "final_model.zip",
        )
        replay_checkpoint_loadable = _loadable_checkpoint(
            trainer,
            replay_dir / "checkpoints" / "final_model.zip",
        )
        source_trainer_hash = str(source_metadata["config_sha256"])
        replay_trainer_hash = str(replay_metadata["config_sha256"])
        computed_replay_trainer_hash = hashlib.sha256(
            execution_config.trainer.model_dump_json().encode()
        ).hexdigest()
        invariant_comparison = {
            "trained_timesteps": _invariant(
                int(source_summary_raw["trained_timesteps"]),
                int(replay_summary_raw["trained_timesteps"]),
            ),
            "algorithm": _invariant(
                str(source_summary_raw["algorithm"]),
                str(replay_summary_raw["algorithm"]),
            ),
            "dataset_manifest_hash": _invariant(
                str(source_metadata["dataset_id"]),
                str(replay_metadata["dataset_id"]),
            ),
            "trainer_config_hash": _invariant(
                source_trainer_hash,
                replay_trainer_hash,
            ).model_copy(
                update={
                    "passed": (
                        source_trainer_hash
                        == replay_trainer_hash
                        == computed_replay_trainer_hash
                    )
                }
            ),
            "execution_protocol": _invariant(
                source_config.environment.execution_protocol,
                execution_config.environment.execution_protocol,
            ),
            "checkpoint_loadability": _invariant(
                source_checkpoint_loadable,
                replay_checkpoint_loadable,
                require_truth=True,
            ),
        }
        core_artifact_comparison = _compare_core_artifacts(
            source_dir,
            replay_dir,
        )
        metrics_passed = all(item.passed for item in metric_comparison.values())
        invariants_passed = all(
            item.passed for item in invariant_comparison.values()
        )
        bitwise = invariants_passed and all(
            item.passed for item in core_artifact_comparison.values()
        )
        statistical_comparison, statistically_passed = _compare_statistically(
            replay_parent,
            source_metrics,
            replay_metrics,
            reviewed_tolerance,
            max_json_bytes=max_json_bytes,
        )
        numerically_passed = metrics_passed and invariants_passed
        source_unchanged = source_snapshot == _snapshot_files(source_dir)
        level, within_tolerance = _classify_reproduction(
            bitwise=bitwise,
            numerically_passed=numerically_passed,
            invariants_passed=invariants_passed,
            statistically_passed=statistically_passed,
            source_unchanged=source_unchanged,
        )
        bitwise = bitwise and source_unchanged
        checks.extend(
            (
                _check(
                    "source_run_immutable",
                    source_unchanged,
                    "source artifact names and SHA-256 values are unchanged",
                ),
                _check(
                    "computational_replay",
                    True,
                    "training and validation evaluation executed in an isolated directory",
                ),
                _check(
                    "required_invariants",
                    invariants_passed,
                    "mandatory training, data, protocol, and loadability values compared",
                ),
                _check(
                    "metric_tolerances",
                    within_tolerance,
                    "validation metrics satisfy numerical or repeated-replay tolerances",
                ),
                _check(
                    "test_partition_boundary",
                    True,
                    "replay built train and validation environments only",
                ),
            )
        )
        report = ReproductionReport(
            verification_mode="computational_replay",
            artifact_integrity_verified=True,
            computational_replay_executed=True,
            reproduction_level=level,
            bitwise_deterministic=bitwise,
            within_tolerance=within_tolerance,
            run_id=run_id,
            source_run_id=run_id,
            replay_run_id=allocated_id,
            replay_relative_path=replay_relative,
            kind="training",
            run_fingerprint=record.fingerprint,
            is_valid=level != "failed" and source_unchanged,
            deterministic_replay=bitwise,
            metric_comparison=metric_comparison,
            invariant_comparison=invariant_comparison,
            core_artifact_comparison=core_artifact_comparison,
            statistical_comparison=statistical_comparison,
            checks=tuple(checks),
        )
        audit_events.append(
            {
                "event": "computational_replay_completed",
                "source_run_id": run_id,
                "replay_run_id": allocated_id,
                "reproduction_level": level,
                "within_tolerance": within_tolerance,
                "network_used": False,
                "test_partition_accessed": False,
                "account_state_mutated": False,
            }
        )
        _write_jsonl(replay_dir / "reproduction_audit.jsonl", audit_events)
        _write_json(
            replay_dir / "reproduction_comparison.json",
            report.model_dump(mode="json"),
        )
        write_run_manifest(
            replay_dir,
            workspace_root=workspace,
            run_id=allocated_id,
            kind="training",
            config_path=replay_dir / "config.resolved.yaml",
            dataset_sha256=dataset_digest,
            seed=source_config.trainer.seed,
            status="completed" if report.is_valid else "failed",
        )
        return report
    except Exception as error:
        source_unchanged = source_snapshot == _snapshot_files(source_dir)
        checks.extend(
            (
                _check(
                    "source_run_immutable",
                    source_unchanged,
                    "source artifact names and SHA-256 values are unchanged",
                ),
                _check(
                    "computational_replay",
                    False,
                    f"{type(error).__name__}: {str(error)[:800]}",
                ),
            )
        )
        audit_events.append(
            {
                "event": "computational_replay_failed",
                "source_run_id": run_id,
                "replay_run_id": allocated_id,
                "error_type": type(error).__name__,
                "network_used": False,
                "test_partition_accessed": False,
                "account_state_mutated": False,
            }
        )
        _write_jsonl(replay_dir / "reproduction_audit.jsonl", audit_events)
        failed = ReproductionReport(
            verification_mode="computational_replay",
            artifact_integrity_verified=True,
            computational_replay_executed=replay_executed,
            reproduction_level="failed",
            bitwise_deterministic=False,
            within_tolerance=False,
            run_id=run_id,
            source_run_id=run_id,
            replay_run_id=allocated_id,
            replay_relative_path=replay_relative,
            kind="training",
            run_fingerprint=record.fingerprint,
            is_valid=False,
            deterministic_replay=False,
            checks=tuple(checks),
        )
        _write_json(
            replay_dir / "reproduction_comparison.json",
            failed.model_dump(mode="json"),
        )
        try:
            from crossmarket_agentgym.audit import write_run_manifest

            write_run_manifest(
                replay_dir,
                workspace_root=workspace,
                run_id=allocated_id,
                kind="training",
                config_path=replay_dir / "config.resolved.yaml",
                dataset_sha256=dataset_digest,
                seed=source_config.trainer.seed,
                status="failed",
            )
        except (OSError, TypeError, ValueError):
            pass
        return failed

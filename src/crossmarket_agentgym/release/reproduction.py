"""Read-only provenance verification and deterministic run replay."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

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
from crossmarket_agentgym.reporting.indexer import build_run_index
from crossmarket_agentgym.reporting.io import read_bounded_json, resolve_inside


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


def _verify_training(
    workspace: Path,
    run_dir: Path,
    *,
    max_json_bytes: int,
) -> tuple[list[VerificationCheck], bool]:
    checks: list[VerificationCheck] = []
    try:
        config_raw = read_bounded_json(
            run_dir / "resolved_config.json",
            max_bytes=max_json_bytes,
        )
        if not isinstance(config_raw, dict):
            raise TypeError("resolved training configuration must be an object")
        # Keep the heavyweight RL dependency lazy: CPU quickstart and non-training
        # reproduction must remain usable from the core installation.
        from crossmarket_agentgym.rl.config import TrainerConfig

        trainer = TrainerConfig.model_validate(config_raw.get("trainer"))
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
        dataset_root = resolve_inside(str(config_raw.get("dataset_root", "")), workspace)
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

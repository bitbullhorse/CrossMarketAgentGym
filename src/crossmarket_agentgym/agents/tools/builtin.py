"""Typed built-in tools for Provider checks and Research Orchestration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from crossmarket_agentgym.agents.tools.models import (
    ToolDefinition,
    ToolPayload,
)
from crossmarket_agentgym.agents.tools.registry import ToolHandler, ToolRegistry
from crossmarket_agentgym.data.manifests import DatasetManifest, sha256_file

if TYPE_CHECKING:
    from crossmarket_agentgym.rl.config import TrainRunConfig
    from crossmarket_agentgym.tuning.config import TuningRunConfig


class StrictBuiltinModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class InspectDatasetInput(StrictBuiltinModel):
    """Workspace-relative canonical manifest path."""

    manifest_path: str = "data/sample/dataset_manifest.json"


class InspectDatasetOutput(StrictBuiltinModel):
    """Credential-free manifest summary."""

    dataset_name: str
    markets: tuple[str, ...]
    symbol_count: int = Field(ge=0)
    row_count: int = Field(ge=0)
    quality_valid: bool
    manifest_sha256: str


class ValidateDatasetInput(StrictBuiltinModel):
    config_path: str
    max_files_per_market: int | None = Field(default=None, ge=1, le=10000)


class ValidateDatasetOutput(StrictBuiltinModel):
    is_valid: bool
    layout: str
    markets: tuple[str, ...]
    files_checked: int = Field(ge=0)
    row_count: int = Field(ge=0)
    issue_count: int = Field(ge=0)


class ManifestListOutput(StrictBuiltinModel):
    markets: tuple[str, ...]
    symbols: tuple[str, ...]


class CreateSplitInput(StrictBuiltinModel):
    train_end_execution_index: int = Field(ge=1)
    validation_end_execution_index: int = Field(ge=2)
    test_end_execution_index: int | None = Field(default=None, ge=3)

    @model_validator(mode="after")
    def validate_order(self) -> CreateSplitInput:
        if self.validation_end_execution_index <= self.train_end_execution_index:
            raise ValueError("validation boundary must follow training")
        if (
            self.test_end_execution_index is not None
            and self.test_end_execution_index <= self.validation_end_execution_index
        ):
            raise ValueError("test boundary must follow validation")
        return self


class CreateSplitOutput(StrictBuiltinModel):
    train: tuple[int, int]
    validation: tuple[int, int]
    test: tuple[int, int] | None
    selection_partition: Literal["validation"] = "validation"
    test_available_to_tuning: Literal[False] = False


class ValidateExperimentInput(StrictBuiltinModel):
    config_path: str
    kind: Literal["train", "tune"]


class ValidateExperimentOutput(StrictBuiltinModel):
    valid: Literal[True] = True
    kind: Literal["train", "tune"]
    identity: str
    config_sha256: str
    selection_partition: Literal["validation"] = "validation"
    test_metrics_accessible: Literal[False] = False


class EstimateBudgetInput(StrictBuiltinModel):
    timesteps: int = Field(default=1000, ge=1)
    trials: int = Field(default=1, ge=1)
    seeds: int = Field(default=1, ge=1)
    walk_forward_folds: int = Field(default=1, ge=1)
    gpu_count: int = Field(default=0, ge=0)


class EstimateBudgetOutput(StrictBuiltinModel):
    work_units: int = Field(ge=1)
    estimated_cpu_hours: float = Field(ge=0.0)
    estimated_gpu_hours: float = Field(ge=0.0)
    requires_expensive_permission: bool


class ConfigPathInput(StrictBuiltinModel):
    config_path: str


class TrainToolOutput(StrictBuiltinModel):
    run_id: str
    checkpoint_path: str
    trained_timesteps: int = Field(ge=0)
    validation_metrics: dict[str, float]
    test_set_accessed: Literal[False] = False


class TuneToolOutput(StrictBuiltinModel):
    study_name: str
    trial_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    best_trial_id: int | None
    test_set_accessed: Literal[False] = False


class EvaluateCheckpointInput(StrictBuiltinModel):
    run_dir: str
    partition: Literal["validation"] = "validation"


class EvaluateCheckpointOutput(StrictBuiltinModel):
    partition: Literal["validation"] = "validation"
    metrics: dict[str, float]
    test_set_accessed: Literal[False] = False


class CompareRunsInput(StrictBuiltinModel):
    run_paths: tuple[str, ...] = Field(min_length=1, max_length=100)


class ComparedRun(StrictBuiltinModel):
    run_id: str
    validation_metrics: dict[str, float]


class CompareRunsOutput(StrictBuiltinModel):
    runs: tuple[ComparedRun, ...]
    comparison_partition: Literal["validation"] = "validation"
    test_metrics_accessed: Literal[False] = False


class GenerateReportInput(StrictBuiltinModel):
    title: str = Field(min_length=1, max_length=200)
    sections: dict[str, str]
    output_path: str


class GenerateReportOutput(StrictBuiltinModel):
    report_path: str
    section_count: int = Field(ge=0)


def _resolve(path: str, root: Path) -> Path:
    candidate = Path(path)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if not resolved.is_relative_to(root):
        raise PermissionError("configured path leaves workspace")
    return resolved


def _register(
    registry: ToolRegistry,
    *,
    name: str,
    description: str,
    input_model: type[BaseModel],
    output_model: type[BaseModel],
    permission: Literal["read", "compute", "write", "expensive"],
    handler: ToolHandler,
    timeout_seconds: float = 30.0,
) -> None:
    definition = ToolDefinition.from_models(
        name=name,
        description=description,
        input_model=input_model,
        output_model=output_model,
        permission=permission,
        timeout_seconds=timeout_seconds,
    )
    registry.register(
        definition,
        input_model=input_model,
        output_model=output_model,
        handler=handler,
    )


def build_builtin_tool_registry(workspace_root: str | Path) -> ToolRegistry:
    """Build all bounded Python capabilities; none accepts shell text."""
    root = Path(workspace_root).resolve()
    registry = ToolRegistry()

    def resolved_train_config(config_path: Path) -> TrainRunConfig:
        from crossmarket_agentgym.rl.config import load_train_run_config

        config = load_train_run_config(config_path)
        return config.model_copy(
            update={
                "dataset_root": _resolve(str(config.dataset_root), root),
                "output_dir": _resolve(str(config.output_dir), root),
            }
        )

    def resolved_tuning_config(
        config_path: Path,
    ) -> tuple[TuningRunConfig, TrainRunConfig | None]:
        from crossmarket_agentgym.tuning.config import load_tuning_run_config

        config = load_tuning_run_config(config_path)
        base_config: TrainRunConfig | None = None
        objective = config.objective
        if objective.base_train_config is not None:
            base_path = _resolve(str(objective.base_train_config), root)
            base_config = resolved_train_config(base_path)
            objective = objective.model_copy(
                update={"base_train_config": base_path}
            )
        return (
            config.model_copy(
                update={
                    "output_dir": _resolve(str(config.output_dir), root),
                    "storage_path": _resolve(str(config.storage_path), root),
                    "objective": objective,
                }
            ),
            base_config,
        )

    def manifest(arguments: BaseModel) -> tuple[DatasetManifest, Path]:
        typed = InspectDatasetInput.model_validate(arguments)
        manifest_path = _resolve(typed.manifest_path, root)
        return (
            DatasetManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            ),
            manifest_path,
        )

    def inspect_dataset(arguments: BaseModel) -> InspectDatasetOutput:
        value, manifest_path = manifest(arguments)
        return InspectDatasetOutput(
            dataset_name=value.dataset_name,
            markets=tuple(value.markets),
            symbol_count=len(value.symbols),
            row_count=value.row_count,
            quality_valid=value.quality.is_valid,
            manifest_sha256=sha256_file(manifest_path),
        )

    _register(
        registry,
        name="inspect_dataset",
        description="Read a canonical dataset manifest and return its audited summary.",
        input_model=InspectDatasetInput,
        output_model=InspectDatasetOutput,
        permission="read",
        handler=inspect_dataset,
        timeout_seconds=10.0,
    )

    def validate_dataset(arguments: BaseModel) -> ValidateDatasetOutput:
        from crossmarket_agentgym.data.config import load_data_config
        from crossmarket_agentgym.data.dataset import validate_configured_dataset

        typed = ValidateDatasetInput.model_validate(arguments)
        config = load_data_config(_resolve(typed.config_path, root))
        dataset_root = _resolve(str(config.dataset.root), root)
        config = config.model_copy(
            update={
                "dataset": config.dataset.model_copy(
                    update={"root": dataset_root}
                )
            }
        )
        summary = validate_configured_dataset(
            config,
            max_files_per_market=typed.max_files_per_market,
        )
        return ValidateDatasetOutput(
            is_valid=summary.is_valid,
            layout=summary.layout,
            markets=tuple(summary.markets),
            files_checked=summary.files_checked,
            row_count=summary.ohlcv_rows,
            issue_count=len(summary.quality.issues),
        )

    _register(
        registry,
        name="validate_dataset",
        description="Validate configured market data without modifying source rows.",
        input_model=ValidateDatasetInput,
        output_model=ValidateDatasetOutput,
        permission="compute",
        handler=validate_dataset,
        timeout_seconds=300.0,
    )

    def list_manifest(arguments: BaseModel) -> ManifestListOutput:
        value, _path = manifest(arguments)
        return ManifestListOutput(
            markets=tuple(value.markets),
            symbols=tuple(sorted(value.symbols)),
        )

    for name, description in (
        ("list_markets", "List markets recorded by a canonical manifest."),
        ("list_symbols", "List symbols recorded by a canonical manifest."),
    ):
        _register(
            registry,
            name=name,
            description=description,
            input_model=InspectDatasetInput,
            output_model=ManifestListOutput,
            permission="read",
            handler=list_manifest,
            timeout_seconds=10.0,
        )

    def create_split(arguments: BaseModel) -> CreateSplitOutput:
        typed = CreateSplitInput.model_validate(arguments)
        return CreateSplitOutput(
            train=(0, typed.train_end_execution_index),
            validation=(
                typed.train_end_execution_index,
                typed.validation_end_execution_index,
            ),
            test=(
                (
                    typed.validation_end_execution_index,
                    typed.test_end_execution_index,
                )
                if typed.test_end_execution_index is not None
                else None
            ),
        )

    _register(
        registry,
        name="create_split",
        description="Create a non-overlapping train/validation/test split plan.",
        input_model=CreateSplitInput,
        output_model=CreateSplitOutput,
        permission="compute",
        handler=create_split,
    )

    def validate_experiment(arguments: BaseModel) -> ValidateExperimentOutput:
        typed = ValidateExperimentInput.model_validate(arguments)
        path = _resolve(typed.config_path, root)
        if typed.kind == "train":
            train_config = resolved_train_config(path)
            identity = train_config.run_name
            canonical = train_config.model_dump_json()
        else:
            tuning_config, _base_config = resolved_tuning_config(path)
            identity = tuning_config.study_name
            canonical = tuning_config.model_dump_json()
        return ValidateExperimentOutput(
            kind=typed.kind,
            identity=identity,
            config_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
        )

    _register(
        registry,
        name="validate_experiment_config",
        description="Schema-validate a train or validation-only tuning configuration.",
        input_model=ValidateExperimentInput,
        output_model=ValidateExperimentOutput,
        permission="compute",
        handler=validate_experiment,
    )

    def estimate_budget(arguments: BaseModel) -> EstimateBudgetOutput:
        typed = EstimateBudgetInput.model_validate(arguments)
        work_units = (
            typed.timesteps
            * typed.trials
            * typed.seeds
            * typed.walk_forward_folds
        )
        cpu_hours = work_units / 3_600_000.0
        gpu_hours = (
            work_units / (12_000_000.0 * typed.gpu_count)
            if typed.gpu_count
            else 0.0
        )
        return EstimateBudgetOutput(
            work_units=work_units,
            estimated_cpu_hours=cpu_hours,
            estimated_gpu_hours=gpu_hours,
            requires_expensive_permission=work_units >= 1000,
        )

    _register(
        registry,
        name="estimate_compute_budget",
        description="Estimate bounded compute work before any expensive tool is allowed.",
        input_model=EstimateBudgetInput,
        output_model=EstimateBudgetOutput,
        permission="compute",
        handler=estimate_budget,
    )

    def train_rl(arguments: BaseModel) -> TrainToolOutput:
        from crossmarket_agentgym.rl.workflow import execute_training_run

        typed = ConfigPathInput.model_validate(arguments)
        config = resolved_train_config(_resolve(typed.config_path, root))
        summary = execute_training_run(config)
        return TrainToolOutput(
            run_id=summary.run_id,
            checkpoint_path=summary.checkpoint,
            trained_timesteps=summary.trained_timesteps,
            validation_metrics=summary.validation_metrics,
        )

    _register(
        registry,
        name="train_rl",
        description="Run bounded RL training with validation output and no test evaluation.",
        input_model=ConfigPathInput,
        output_model=TrainToolOutput,
        permission="expensive",
        handler=train_rl,
        timeout_seconds=3600.0,
    )

    def tune_rl(arguments: BaseModel) -> TuneToolOutput:
        from crossmarket_agentgym.tuning.workflow import execute_tuning_run

        typed = ConfigPathInput.model_validate(arguments)
        config, base_config = resolved_tuning_config(
            _resolve(typed.config_path, root)
        )
        summary = execute_tuning_run(
            config,
            base_train_config=base_config,
        )
        if summary.test_set_accessed:
            raise RuntimeError("tuning workflow reported forbidden test access")
        return TuneToolOutput(
            study_name=summary.study_name,
            trial_count=summary.trial_count,
            completed_count=summary.completed_count,
            failed_count=summary.failed_count,
            best_trial_id=summary.best_trial_id,
        )

    _register(
        registry,
        name="tune_rl",
        description="Run HPO using training and validation only.",
        input_model=ConfigPathInput,
        output_model=TuneToolOutput,
        permission="expensive",
        handler=tune_rl,
        timeout_seconds=3600.0,
    )

    def evaluate_checkpoint(arguments: BaseModel) -> EvaluateCheckpointOutput:
        from crossmarket_agentgym.rl.config import TrainRunConfig
        from crossmarket_agentgym.rl.workflow import evaluate_saved_run

        typed = EvaluateCheckpointInput.model_validate(arguments)
        run_dir = _resolve(typed.run_dir, root)
        saved_config = TrainRunConfig.model_validate_json(
            (run_dir / "resolved_config.json").read_text(encoding="utf-8")
        )
        safe_config = saved_config.model_copy(
            update={
                "dataset_root": _resolve(str(saved_config.dataset_root), root),
                "output_dir": _resolve(str(saved_config.output_dir), root),
            }
        )
        result = evaluate_saved_run(
            run_dir,
            partition="validation",
            config_override=safe_config,
        )
        return EvaluateCheckpointOutput(metrics=result.metrics)

    _register(
        registry,
        name="evaluate_checkpoint",
        description="Evaluate a checkpoint on validation only; test is not in the schema.",
        input_model=EvaluateCheckpointInput,
        output_model=EvaluateCheckpointOutput,
        permission="compute",
        handler=evaluate_checkpoint,
        timeout_seconds=600.0,
    )

    def compare_runs(arguments: BaseModel) -> CompareRunsOutput:
        typed = CompareRunsInput.model_validate(arguments)
        compared: list[ComparedRun] = []
        for run_path in typed.run_paths:
            path = _resolve(run_path, root)
            summary_path = path / "run_summary.json"
            raw: Any = json.loads(
                summary_path.read_text(encoding="utf-8")
            )
            metrics = raw.get("validation_metrics")
            if not isinstance(metrics, dict):
                raise ValueError("run summary has no validation_metrics")
            compared.append(
                ComparedRun(
                    run_id=str(raw.get("run_id", path.name)),
                    validation_metrics={
                        str(key): float(value)
                        for key, value in metrics.items()
                    },
                )
            )
        return CompareRunsOutput(runs=tuple(compared))

    _register(
        registry,
        name="compare_runs",
        description="Compare validation summaries without opening test metrics.",
        input_model=CompareRunsInput,
        output_model=CompareRunsOutput,
        permission="read",
        handler=compare_runs,
    )

    def generate_report(arguments: BaseModel) -> ToolPayload:
        typed = GenerateReportInput.model_validate(arguments)
        output_path = _resolve(typed.output_path, root)
        if output_path.suffix.lower() != ".md":
            raise ValueError("research report output must be Markdown")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        body = [f"# {typed.title}", ""]
        for heading, content in typed.sections.items():
            body.extend((f"## {heading}", "", content, ""))
        output_path.write_text("\n".join(body), encoding="utf-8")
        return ToolPayload(
            data={
                "report_path": str(output_path),
                "section_count": len(typed.sections),
            },
            artifact_paths=(str(output_path),),
        )

    _register(
        registry,
        name="generate_report",
        description="Write a bounded Markdown research note from supplied validated sections.",
        input_model=GenerateReportInput,
        output_model=GenerateReportOutput,
        permission="write",
        handler=generate_report,
    )
    return registry

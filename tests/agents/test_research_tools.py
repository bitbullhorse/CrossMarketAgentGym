from __future__ import annotations

from pathlib import Path

from crossmarket_agentgym.agents.tools import (
    ToolExecutor,
    ToolPolicy,
    build_builtin_tool_registry,
)

_RESEARCH_TOOLS = {
    "inspect_dataset",
    "validate_dataset",
    "list_markets",
    "list_symbols",
    "create_split",
    "validate_experiment_config",
    "estimate_compute_budget",
    "train_rl",
    "tune_rl",
    "evaluate_checkpoint",
    "compare_runs",
    "generate_report",
}


def _executor(
    *,
    permissions: frozenset[str] = frozenset({"read", "compute"}),
) -> ToolExecutor:
    return ToolExecutor(
        build_builtin_tool_registry(Path.cwd()),
        ToolPolicy(
            allowed_permissions=permissions,  # type: ignore[arg-type]
            max_total_calls=20,
            max_expensive_calls=1,
        ),
        Path.cwd(),
    )


def test_all_reported_research_tools_are_registered() -> None:
    names = {
        definition.name
        for definition in build_builtin_tool_registry(Path.cwd()).definitions()
    }
    assert names == _RESEARCH_TOOLS


def test_manifest_lists_and_split_plan_are_validation_safe() -> None:
    executor = _executor()
    listed = executor.execute(
        "list_symbols",
        {"manifest_path": "data/sample/dataset_manifest.json"},
    )
    split = executor.execute(
        "create_split",
        {
            "train_end_execution_index": 20,
            "validation_end_execution_index": 30,
            "test_end_execution_index": 40,
        },
    )
    assert listed.success
    assert listed.data is not None
    assert listed.data["markets"] == ["CN", "HK", "JP", "US"]
    assert split.success
    assert split.data is not None
    assert split.data["selection_partition"] == "validation"
    assert split.data["test_available_to_tuning"] is False


def test_experiment_validation_and_budget_estimation_do_not_start_work() -> None:
    executor = _executor()
    validated = executor.execute(
        "validate_experiment_config",
        {"config_path": "configs/train/ppo.yaml", "kind": "train"},
    )
    budget = executor.execute(
        "estimate_compute_budget",
        {
            "timesteps": 1000,
            "trials": 4,
            "seeds": 3,
            "walk_forward_folds": 2,
            "gpu_count": 0,
        },
    )
    assert validated.success
    assert validated.data is not None
    assert validated.data["test_metrics_accessible"] is False
    assert budget.success
    assert budget.data is not None
    assert budget.data["work_units"] == 24000
    assert budget.data["requires_expensive_permission"] is True


def test_validation_checkpoint_schema_cannot_request_test() -> None:
    result = _executor().execute(
        "evaluate_checkpoint",
        {"run_dir": "runs/example", "partition": "test"},
    )
    assert result.error_code == "invalid_tool_input"


def test_plural_path_arguments_cannot_escape_workspace(tmp_path: Path) -> None:
    executor = ToolExecutor(
        build_builtin_tool_registry(tmp_path),
        ToolPolicy(allowed_permissions=frozenset({"read"})),
        tmp_path,
    )
    result = executor.execute(
        "compare_runs",
        {"run_paths": ["../outside"]},
    )
    assert result.error_code == "invalid_tool_input"


def test_nested_experiment_paths_cannot_escape_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_path = workspace / "train.yaml"
    config_path.write_text(
        "\n".join(
            (
                "dataset_root: ../outside",
                "output_dir: runs",
                "run_name: escaped",
                "split:",
                "  train_end_execution_index: 20",
                "  validation_end_execution_index: 30",
            )
        ),
        encoding="utf-8",
    )
    executor = ToolExecutor(
        build_builtin_tool_registry(workspace),
        ToolPolicy(allowed_permissions=frozenset({"compute"})),
        workspace,
    )
    result = executor.execute(
        "validate_experiment_config",
        {"config_path": "train.yaml", "kind": "train"},
    )
    assert result.success is False
    assert result.error_code == "invalid_tool_output"


def test_markdown_report_requires_explicit_write_permission(tmp_path: Path) -> None:
    registry = build_builtin_tool_registry(tmp_path)
    denied = ToolExecutor(
        registry,
        ToolPolicy(allowed_permissions=frozenset({"read", "compute"})),
        tmp_path,
    ).execute(
        "generate_report",
        {
            "title": "Research",
            "sections": {"Evidence": "Validation only."},
            "output_path": "reports/research.md",
        },
    )
    allowed = ToolExecutor(
        registry,
        ToolPolicy(allowed_permissions=frozenset({"write"})),
        tmp_path,
    ).execute(
        "generate_report",
        {
            "title": "Research",
            "sections": {"Evidence": "Validation only."},
            "output_path": "reports/research.md",
        },
    )
    assert denied.error_code == "permission_denied"
    assert allowed.success
    assert (tmp_path / "reports" / "research.md").exists()


def test_expensive_research_tool_requires_prior_budget_estimate() -> None:
    executor = ToolExecutor(
        build_builtin_tool_registry(Path.cwd()),
        ToolPolicy(
            allowed_permissions=frozenset({"compute", "expensive"}),
            allowed_tools=frozenset({"estimate_compute_budget", "train_rl"}),
            max_total_calls=3,
            max_expensive_calls=1,
            require_budget_before_expensive=True,
        ),
        Path.cwd(),
    )
    denied = executor.execute(
        "train_rl",
        {"config_path": "configs/train/ppo.yaml"},
    )
    estimated = executor.execute(
        "estimate_compute_budget",
        {"timesteps": 1, "trials": 1, "seeds": 1, "walk_forward_folds": 1},
    )
    assert denied.error_code == "budget_estimate_required"
    assert estimated.success
    assert executor.budget_estimated is True

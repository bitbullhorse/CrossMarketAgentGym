"""Deterministic JSON and Markdown HPO study reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from crossmarket_agentgym.tuning.models import StudyState, scalar_utility
from crossmarket_agentgym.tuning.objectives import pareto_front


def build_study_report(state: StudyState) -> dict[str, Any]:
    """Build a JSON-serializable study summary without test-set metrics."""
    completed = [result for result in state.results if result.status == "completed"]
    failed = [result for result in state.results if result.status == "failed"]
    pruned = [result for result in state.results if result.status == "pruned"]
    best = (
        max(completed, key=lambda result: scalar_utility(result, state.directions))
        if completed
        else None
    )
    front = pareto_front(completed, state.directions)
    return {
        "study_name": state.study_name,
        "directions": list(state.directions),
        "trial_count": len(state.results),
        "completed_count": len(completed),
        "failed_count": len(failed),
        "pruned_count": len(pruned),
        "best_trial": None if best is None else best.model_dump(mode="json"),
        "pareto_trial_ids": [result.trial_id for result in front],
        "trials": [result.model_dump(mode="json") for result in state.results],
        "partition_policy": "train_and_validation_only",
        "test_metrics_present": False,
    }


def write_study_report(
    state: StudyState,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    """Write canonical JSON plus a compact human-readable Markdown summary."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    report = build_study_report(state)
    json_path = destination / "study_report.json"
    markdown_path = destination / "study_report.md"
    json_path.write_text(
        json.dumps(
            report,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    best = report["best_trial"]
    best_line = (
        "无已完成 Trial"
        if best is None
        else f"Trial {best['trial_id']}，objectives={best['objectives']}"
    )
    markdown_path.write_text(
        "\n".join(
            [
                f"# HPO Study：{state.study_name}",
                "",
                "- 数据边界：仅训练集与验证集；报告不含测试集指标。",
                f"- Trial 总数：{report['trial_count']}",
                f"- 完成 / 失败 / 剪枝：{report['completed_count']} / "
                f"{report['failed_count']} / {report['pruned_count']}",
                f"- 当前最优：{best_line}",
                f"- Pareto Trial：{report['pareto_trial_ids']}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, markdown_path

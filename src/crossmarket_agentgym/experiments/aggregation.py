"""Automated Phase 12 audit, statistical summaries, tables, and figures."""

from __future__ import annotations

import json
import math
from html import escape
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats  # type: ignore[import-untyped]

from crossmarket_agentgym.experiments.audit import FormalRunRecord
from crossmarket_agentgym.experiments.matrix import FormalRunMatrix, load_run_matrix
from crossmarket_agentgym.experiments.protocol import sha256_file


def _mean_metrics(values: list[dict[str, Any]]) -> dict[str, float]:
    numeric_keys = sorted(
        set.intersection(
            *(
                {key for key, value in row.items() if isinstance(value, int | float)}
                for row in values
            )
        )
    )
    return {
        key: float(np.mean([float(row[key]) for row in values]))
        for key in numeric_keys
    }


def _result_metrics(group: str, result: dict[str, Any]) -> dict[str, float]:
    if group == "A":
        return {
            "passed": float(bool(result["passed"])),
            "absolute_error": float(result["absolute_error"]),
        }
    if group == "B":
        metrics = {
            key: float(value)
            for key, value in result["test_metrics"].items()
            if isinstance(value, int | float)
        }
        metrics["runtime_seconds"] = float(result["runtime_seconds"])
        return metrics
    if group == "C":
        return _mean_metrics(
            [
                subrun["test_metrics"]
                for subrun in result["subruns"].values()
            ]
        )
    if group == "D":
        metrics = {
            key: float(value)
            for key, value in result["variant_metrics"].items()
            if isinstance(value, int | float)
        }
        for key, value in result["base_metrics"].items():
            if isinstance(value, int | float) and key in metrics:
                metrics[f"delta_{key}"] = metrics[key] - float(value)
        metrics["runtime_seconds"] = float(result["runtime_seconds"])
        return metrics
    if group == "E":
        metrics = {
            key: float(value)
            for key, value in result["portfolio_metrics"].items()
            if isinstance(value, int | float)
        }
        for key in (
            "task_success_rate",
            "config_validity_rate",
            "tool_call_accuracy",
            "leakage_violation_rate",
            "risk_directive_validity_rate",
            "conflict_resolution_rate",
            "report_completeness_rate",
            "additional_runtime_seconds",
        ):
            metrics[key] = float(result[key])
        return metrics
    return {
        "validation_score": float(result["validation_score"]),
        "locked_test_score": float(result["locked_test_score"]),
        "runtime_seconds": float(result["runtime_seconds"]),
        "stability": float(result["stability"]),
        "tuning_overfit_gap": float(result["tuning_overfit_gap"]),
    }


def _missing_required_metrics(
    group: str,
    required: tuple[str, ...],
    result: dict[str, Any],
) -> tuple[str, ...]:
    if group == "A":
        available = set(result)
    elif group == "B":
        available = set(result["test_metrics"]) | set(result)
    elif group == "C":
        subruns = list(result["subruns"].values())
        available = (
            set.intersection(*(set(item["test_metrics"]) for item in subruns))
            if subruns
            else set()
        )
    elif group == "D":
        available = set(result["variant_metrics"]) | set(result)
    else:
        available = set(result)
    return tuple(metric for metric in required if metric not in available)


def collect_formal_results(
    *,
    matrix: FormalRunMatrix,
    results_root: Path,
) -> tuple[pd.DataFrame, list[str]]:
    """Verify completed task records and return one normalized metric table."""
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    for task in matrix.tasks:
        run_dir = results_root / task.run_id
        record_path = run_dir / "formal_run.json"
        result_path = run_dir / "result.json"
        if not record_path.is_file():
            blockers.append(f"MISSING_RUN:{task.run_id}")
            continue
        record = FormalRunRecord.model_validate_json(
            record_path.read_text(encoding="utf-8")
        )
        if record.task != task:
            blockers.append(f"TASK_IDENTITY_MISMATCH:{task.run_id}")
            continue
        if record.status != "completed":
            blockers.append(f"RUN_NOT_COMPLETED:{task.run_id}:{record.status}")
            continue
        expected_test_access = task.test_access == "locked_final_once"
        unsafe_test_access = (
            record.test_partition_accessed != expected_test_access
            or record.test_access_authorized != expected_test_access
            or (
                expected_test_access
                and (
                    record.test_partition_access_count < 1
                    or not record.configuration_lock_present_before_test
                )
            )
        )
        unsafe_network_access = (
            record.network_accessed and not record.network_access_authorized
        )
        if (
            unsafe_test_access
            or unsafe_network_access
            or record.development_result_accessed
            or record.account_state_mutated_externally
        ):
            blockers.append(f"SAFETY_AUDIT_FAILED:{task.run_id}")
            continue
        artifact = next(
            (item for item in record.artifacts if item.path == "result.json"),
            None,
        )
        if (
            artifact is None
            or not result_path.is_file()
            or sha256_file(result_path) != artifact.sha256
        ):
            blockers.append(f"RESULT_HASH_FAILED:{task.run_id}")
            continue
        result = json.loads(result_path.read_text(encoding="utf-8"))
        missing_metrics = _missing_required_metrics(
            task.group,
            task.required_metrics,
            result,
        )
        if missing_metrics:
            blockers.append(
                f"REQUIRED_METRICS_MISSING:{task.run_id}:{','.join(missing_metrics)}"
            )
            continue
        if task.group == "F":
            convergence = result.get("convergence", [])
            trial_budget = int(result.get("trial_budget", -1))
            completed_trials = sum(
                item.get("status") == "completed"
                for item in convergence
                if isinstance(item, dict)
            )
            fold_count = int(result.get("walk_forward_folds", -1))
            fold_artifacts = sum(
                item.path.endswith("hpo_validation.json")
                and "/fold_" in f"/{item.path}"
                for item in record.artifacts
            )
            if (
                len(convergence) != trial_budget
                or fold_count != len(task.walk_forward_folds)
                or fold_artifacts < completed_trials * fold_count
            ):
                blockers.append(f"HPO_FOLD_EVIDENCE_INCOMPLETE:{task.run_id}")
                continue
        for metric, value in _result_metrics(task.group, result).items():
            rows.append(
                {
                    "run_id": task.run_id,
                    "group": task.group,
                    "method": task.method,
                    "seed": task.seed,
                    "metric": metric,
                    "value": value,
                    "protocol_sha256": task.protocol_sha256,
                    "dataset_manifest_sha256": task.dataset_manifest_sha256,
                    "code_commit": task.code_commit,
                }
            )
    return pd.DataFrame(rows), blockers


def summarize_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute the frozen five-seed descriptive statistics and Student-t CI."""
    summaries: list[dict[str, Any]] = []
    if frame.empty:
        return pd.DataFrame()
    for (group, method, metric), selected in frame.groupby(
        ["group", "method", "metric"],
        sort=True,
    ):
        values = selected["value"].to_numpy(dtype=float)
        count = len(values)
        mean = float(values.mean())
        deviation = float(values.std(ddof=1)) if count > 1 else 0.0
        margin = (
            float(stats.t.ppf(0.975, df=count - 1) * deviation / math.sqrt(count))
            if count > 1
            else 0.0
        )
        summaries.append(
            {
                "group": group,
                "method": method,
                "metric": metric,
                "n": count,
                "mean": mean,
                "std": deviation,
                "median": float(np.median(values)),
                "ci95_low": mean - margin,
                "ci95_high": mean + margin,
                "best": float(values.max()),
                "worst": float(values.min()),
            }
        )
    return pd.DataFrame(summaries)


def _rank_biserial(differences: np.ndarray[Any, Any]) -> float:
    nonzero = differences[differences != 0.0]
    if nonzero.size == 0:
        return 0.0
    ranks = stats.rankdata(np.abs(nonzero))
    positive = float(ranks[nonzero > 0].sum())
    negative = float(ranks[nonzero < 0].sum())
    denominator = positive + negative
    return (positive - negative) / denominator if denominator else 0.0


def paired_tests(frame: pd.DataFrame) -> pd.DataFrame:
    """Compare each method with the frozen group reference and apply Holm."""
    references = {"B": "cash", "E": "no_llm", "F": "default"}
    rows: list[dict[str, Any]] = []
    for group, reference in references.items():
        group_frame = frame[frame["group"] == group]
        for metric in sorted(group_frame["metric"].unique()):
            pivot = group_frame[group_frame["metric"] == metric].pivot_table(
                index="seed",
                columns="method",
                values="value",
                aggfunc="first",
            )
            if reference not in pivot:
                continue
            for method in sorted(set(pivot.columns) - {reference}):
                paired = pivot[[reference, method]].dropna()
                if len(paired) < 5:
                    continue
                differences = (
                    paired[method].to_numpy(dtype=float)
                    - paired[reference].to_numpy(dtype=float)
                )
                if np.allclose(differences, 0.0):
                    statistic, p_value = 0.0, 1.0
                else:
                    test = stats.wilcoxon(
                        paired[method],
                        paired[reference],
                        alternative="two-sided",
                        zero_method="wilcox",
                    )
                    statistic, p_value = float(test.statistic), float(test.pvalue)
                rows.append(
                    {
                        "group": group,
                        "metric": metric,
                        "reference": reference,
                        "method": method,
                        "n": len(paired),
                        "statistic": statistic,
                        "p_value": p_value,
                        "rank_biserial": _rank_biserial(differences),
                    }
                )
    if not rows:
        return pd.DataFrame()
    ordered = sorted(range(len(rows)), key=lambda index: rows[index]["p_value"])
    total = len(rows)
    running = 0.0
    adjusted = [1.0] * total
    for rank, index in enumerate(ordered):
        candidate = min(1.0, (total - rank) * rows[index]["p_value"])
        running = max(running, candidate)
        adjusted[index] = running
    for index, value in enumerate(adjusted):
        rows[index]["holm_adjusted_p"] = value
    return pd.DataFrame(rows)


def _write_markdown_table(frame: pd.DataFrame, path: Path) -> None:
    if frame.empty:
        path.write_text("_No rows._\n", encoding="utf-8")
        return
    columns = [str(column) for column in frame.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for values in frame.itertuples(index=False, name=None):
        cells = [str(value).replace("|", "\\|") for value in values]
        lines.append("| " + " | ".join(cells) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_figures(summary: pd.DataFrame, figures: Path) -> list[str]:
    figures.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    for group in sorted(summary["group"].unique()) if not summary.empty else []:
        selected = summary[
            (summary["group"] == group)
            & summary["metric"].isin(
                ["mean_return", "sharpe", "validation_score", "task_success_rate"]
            )
        ]
        if selected.empty:
            continue
        metric = sorted(selected["metric"].unique())[0]
        selected = selected[selected["metric"] == metric].sort_values("method")
        output = figures / f"group_{group}_{metric}.svg"
        lows = selected["ci95_low"].to_numpy(dtype=float)
        highs = selected["ci95_high"].to_numpy(dtype=float)
        minimum = float(np.min(lows))
        maximum = float(np.max(highs))
        span = maximum - minimum or 1.0
        width = max(640, len(selected) * 110)
        height = 420

        def y(
            value: float,
            lower: float = minimum,
            value_span: float = span,
        ) -> float:
            return 330.0 - (value - lower) / value_span * 250.0

        elements = [
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
                f'height="{height}" viewBox="0 0 {width} {height}">'
            ),
            '<rect width="100%" height="100%" fill="white"/>',
            (
                f'<text x="{width / 2:.1f}" y="28" text-anchor="middle" '
                'font-family="sans-serif" font-size="18">'
                f"Phase 12 Group {escape(str(group))}: mean and 95% CI</text>"
            ),
            '<line x1="70" y1="60" x2="70" y2="340" stroke="black"/>',
            f'<text x="18" y="200" font-family="sans-serif" font-size="13">{escape(metric)}</text>',
        ]
        for index, row in enumerate(selected.itertuples(index=False)):
            x = 100 + index * 100
            low_y = y(float(row.ci95_low))
            high_y = y(float(row.ci95_high))
            mean_y = y(float(row.mean))
            elements.extend(
                [
                    f'<line x1="{x}" y1="{low_y:.2f}" x2="{x}" y2="{high_y:.2f}" stroke="#2855a6"/>',
                    f'<line x1="{x - 5}" y1="{low_y:.2f}" x2="{x + 5}" y2="{low_y:.2f}" stroke="#2855a6"/>',
                    f'<line x1="{x - 5}" y1="{high_y:.2f}" x2="{x + 5}" y2="{high_y:.2f}" stroke="#2855a6"/>',
                    f'<circle cx="{x}" cy="{mean_y:.2f}" r="4" fill="#b22222"/>',
                    (
                        f'<text x="{x}" y="365" text-anchor="end" '
                        'transform="rotate(-35 '
                        f'{x} 365)" font-family="sans-serif" font-size="11">'
                        f"{escape(str(row.method))}</text>"
                    ),
                ]
            )
        elements.append("</svg>")
        output.write_text("\n".join(elements) + "\n", encoding="utf-8")
        outputs.append(output.name)
    return outputs


def _independent_review_blockers(
    path: Path,
    *,
    matrix: FormalRunMatrix,
    matrix_sha256: str,
) -> list[str]:
    if not path.is_file():
        return ["INDEPENDENT_REVIEW_MISSING"]
    text = path.read_text(encoding="utf-8")
    required_values = {
        "Reviewer identity": None,
        "Affiliation or independent role": None,
        "Review date": None,
        "Protocol SHA-256": matrix.protocol_sha256,
        "Dataset Manifest SHA-256": matrix.dataset_manifest_sha256,
        "Run-matrix SHA-256": matrix_sha256,
        "Code commit": matrix.code_commit,
    }
    blockers: list[str] = []
    for label, expected in required_values.items():
        prefix = f"- {label}:"
        line = next(
            (candidate.strip() for candidate in text.splitlines() if candidate.startswith(prefix)),
            "",
        )
        value = line[len(prefix) :].strip() if line else ""
        if not value or (expected is not None and value.strip("`") != expected):
            blockers.append(f"INDEPENDENT_REVIEW_FIELD_INVALID:{label}")
    check_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("- [")
    ]
    if len(check_lines) < 10 or any(
        not line.lower().startswith("- [x]") for line in check_lines
    ):
        blockers.append("INDEPENDENT_REVIEW_CHECKS_INCOMPLETE")
    normalized = text.replace("`", "")
    if "P0: 0" not in normalized or "P1: 0" not in normalized:
        blockers.append("INDEPENDENT_REVIEW_P0_P1_NOT_ZERO")
    if "Decision: approved" not in normalized:
        blockers.append("INDEPENDENT_REVIEW_NOT_APPROVED")
    return blockers


def generate_phase12_summary(
    *,
    matrix_path: Path,
    matrix_checksum_path: Path,
    results_root: Path,
    output_dir: Path,
    independent_review_path: Path,
) -> dict[str, Any]:
    """Generate all Phase 12 acceptance evidence without freezing a Benchmark."""
    matrix_sha256 = sha256_file(matrix_path)
    checksum = matrix_checksum_path.read_text(encoding="utf-8").split()
    if len(checksum) != 2 or checksum[0] != matrix_sha256:
        raise ValueError("run matrix checksum is invalid")
    matrix = load_run_matrix(matrix_path)
    raw, blockers = collect_formal_results(matrix=matrix, results_root=results_root)
    summary = summarize_metrics(raw)
    tests = paired_tests(raw)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "run_metrics.csv", index=False)
    summary.to_csv(output_dir / "descriptive_statistics.csv", index=False)
    tests.to_csv(output_dir / "paired_tests.csv", index=False)
    _write_markdown_table(summary, output_dir / "descriptive_statistics.md")
    _write_markdown_table(tests, output_dir / "paired_tests.md")
    figures = _write_figures(summary, output_dir / "figures")
    completed_ids = set(raw["run_id"]) if not raw.empty else set()
    for task in matrix.tasks:
        if task.group != "A":
            method_rows = raw[
                (raw["group"] == task.group)
                & (raw["method"] == task.method)
            ]
            if method_rows["seed"].nunique() < 5:
                code = f"INSUFFICIENT_SEEDS:{task.group}:{task.method}"
                if code not in blockers:
                    blockers.append(code)
    blockers.extend(
        _independent_review_blockers(
            independent_review_path,
            matrix=matrix,
            matrix_sha256=matrix_sha256,
        )
    )
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "matrix_id": matrix.matrix_id,
        "protocol_sha256": matrix.protocol_sha256,
        "dataset_manifest_sha256": matrix.dataset_manifest_sha256,
        "code_commit": matrix.code_commit,
        "planned_run_count": len(matrix.tasks),
        "completed_run_count": len(completed_ids),
        "failed_or_missing_run_count": len(matrix.tasks) - len(completed_ids),
        "five_seed_requirement": 5,
        "formal_results_only": True,
        "development_results_used": False,
        "hpo_test_access": False,
        "figures": figures,
        "blockers": sorted(set(blockers)),
        "phase12_complete": not blockers,
        "phase13_ready": not blockers,
    }
    (output_dir / "phase12_summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Phase 12 formal experiment summary",
        "",
        f"- Planned runs: {payload['planned_run_count']}",
        f"- Completed runs: {payload['completed_run_count']}",
        f"- Phase 12 complete: {payload['phase12_complete']}",
        f"- Phase 13 ready: {payload['phase13_ready']}",
        "",
        "## Blockers",
        "",
        *(
            [f"- `{blocker}`" for blocker in payload["blockers"]]
            or ["- None"]
        ),
        "",
    ]
    (output_dir / "phase12_summary.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
    return payload

"""One-command SoftwareX Markdown/HTML/table/figure generation."""

from __future__ import annotations

import csv
import hashlib
import html
import json
from pathlib import Path
from typing import Any

from jinja2 import Environment

from crossmarket_agentgym.reporting.benchmarks import build_benchmark_comparison
from crossmarket_agentgym.reporting.charts import write_bar_chart
from crossmarket_agentgym.reporting.indexer import build_run_index
from crossmarket_agentgym.reporting.io import combined_sha256, resolve_inside, sha256_file
from crossmarket_agentgym.reporting.models import (
    BenchmarkComparison,
    ExperimentDeclaration,
    ReportArtifact,
    ReportBuildSummary,
    ReportManifest,
    RunIndex,
    SoftwareXReportConfig,
)

_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none'; img-src 'self'; style-src 'unsafe-inline';">
  <title>{{ title }}</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0 auto; max-width: 1180px;
           padding: 2rem; color: #172033; line-height: 1.5; }
    h1, h2 { color: #0f172a; } .notice { padding: .8rem 1rem; background: #eff6ff;
    border-left: 4px solid #2563eb; } table { width: 100%; border-collapse: collapse;
    margin: 1rem 0 2rem; font-size: .9rem; } th, td { border: 1px solid #cbd5e1;
    padding: .5rem; text-align: left; } th { background: #f1f5f9; }
    img { width: 100%; height: auto; border: 1px solid #e2e8f0; margin-bottom: 1.5rem; }
    code { background: #f1f5f9; padding: .1rem .3rem; } .muted { color: #64748b; }
  </style>
</head>
<body>
  <h1>{{ title }}</h1>
  <p class="notice">This report is descriptive. It has no hyperparameter-selection authority and
  does not expose hidden test metrics to tuning.</p>
  <p class="muted">Source index: <code>{{ index_hash }}</code></p>
  <h2>SoftwareX experiment readiness</h2>{{ experiment_table | safe }}
  <img src="figures/experiment_readiness.svg" alt="SoftwareX experiment readiness">
  <h2>Run inventory</h2>{{ inventory_table | safe }}
  <p><a href="runs.html">Open the static run browser</a></p>
  <h2>{{ partition | capitalize }} benchmark</h2>{{ benchmark_table | safe }}
  <img src="figures/benchmark_return.svg" alt="Mean return comparison">
  <img src="figures/benchmark_drawdown.svg" alt="Maximum drawdown comparison">
  <h2>Agent and HPO ablation signals</h2>{{ ablation_table | safe }}
  <img src="figures/agent_hpo_signal.svg" alt="Agent and HPO signal comparison">
</body>
</html>
"""

_BROWSER_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport"
content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy"
content="default-src 'none'; style-src 'unsafe-inline'"><title>Run browser</title>
<style>body{font-family:system-ui,sans-serif;max-width:1180px;margin:2rem auto;padding:0 1rem}
table{width:100%;border-collapse:collapse}th,td{border:1px solid #cbd5e1;padding:.5rem}
th{background:#f1f5f9}code{font-size:.8rem}</style></head><body>
<h1>CrossMarketAgentGym run browser</h1><p>Whitelisted metadata only; raw messages,
credentials, checkpoints, and arbitrary files are not exposed.</p>{{ inventory_table | safe }}
</body></html>"""


def _fmt(value: object) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _html_table(headers: list[str], rows: list[list[object]]) -> str:
    head = "".join(f"<th>{html.escape(item)}</th>" for item in headers)
    body = "".join(
        "<tr>"
        + "".join(f"<td>{html.escape(_fmt(value))}</td>" for value in row)
        + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    def cell(value: object) -> str:
        return _fmt(value).replace("|", r"\|").replace("\n", " ")

    return "\n".join(
        (
            "| " + " | ".join(headers) + " |",
            "|" + "|".join("---" for _ in headers) + "|",
            *("| " + " | ".join(cell(value) for value in row) + " |" for row in rows),
        )
    )


def _inventory_rows(index: RunIndex) -> list[list[object]]:
    return [
        [
            run.run_id,
            run.kind,
            run.status,
            run.algorithm,
            ", ".join(run.partitions),
            run.artifact_count,
            run.fingerprint[:12],
        ]
        for run in index.runs
    ]


def _benchmark_rows(comparison: BenchmarkComparison) -> list[list[object]]:
    return [
        [
            row.run_id,
            row.algorithm,
            row.seed,
            row.mean_return,
            row.sharpe,
            row.sortino,
            row.max_drawdown,
            row.calmar,
            row.cvar_95,
            row.mean_turnover,
            row.total_cost,
            row.cross_seed_variance,
            row.runtime_seconds,
        ]
        for row in comparison.rows
    ]


def _experiment_rows(
    experiments: tuple[ExperimentDeclaration, ...],
) -> list[list[object]]:
    return [
        [
            experiment.category,
            experiment.label,
            experiment.status,
            ", ".join(experiment.evidence_paths) or "none",
            experiment.notes,
        ]
        for experiment in experiments
    ]


def _ablation_rows(index: RunIndex) -> list[list[object]]:
    rows: list[list[object]] = []
    for run in index.runs:
        if run.kind not in {"agent", "phase7", "tuning"}:
            continue
        namespace = "agent" if run.kind in {"agent", "phase7"} else "validation"
        metrics = run.metrics.get(namespace, {})
        signal_name = (
            "task_success_rate"
            if "task_success_rate" in metrics
            else "objective_0"
        )
        rows.append(
            [
                run.run_id,
                run.kind,
                run.attributes.get("preset"),
                signal_name,
                metrics.get(signal_name),
                run.status,
            ]
        )
    return rows


def _write_csv(path: Path, headers: list[str], rows: list[list[object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(rows)


def _evidence_paths(
    config: SoftwareXReportConfig,
    workspace: Path,
) -> list[Path]:
    paths: list[Path] = []
    for experiment in config.experiments:
        for evidence in experiment.evidence_paths:
            path = resolve_inside(evidence, workspace)
            if not path.is_file():
                raise FileNotFoundError(path)
            if path.stat().st_size > config.max_json_bytes:
                raise ValueError("evidence artifact exceeds report size limit")
            paths.append(path)
    return paths


def _render_markdown(
    config: SoftwareXReportConfig,
    index: RunIndex,
    comparison: BenchmarkComparison,
) -> str:
    inventory_headers = [
        "Run",
        "Kind",
        "Status",
        "Algorithm",
        "Partitions",
        "Artifacts",
        "Fingerprint",
    ]
    benchmark_headers = [
        "Run",
        "Algorithm",
        "Seed",
        "Return",
        "Sharpe",
        "Sortino",
        "Max drawdown",
        "Calmar",
        "CVaR 95%",
        "Turnover",
        "Cost",
        "Seed variance",
        "Runtime s",
    ]
    return "\n".join(
        (
            f"# {config.title}",
            "",
            "> Descriptive reporting only. This report has no hyperparameter-selection authority.",
            "",
            f"- Report ID: `{config.report_id}`",
            f"- Source index: `{index.fingerprint}`",
            f"- Benchmark partition: `{comparison.partition}`",
            "",
            "## SoftwareX experiment readiness",
            "",
            _markdown_table(
                ["Category", "Label", "Status", "Evidence", "Notes"],
                _experiment_rows(config.experiments),
            ),
            "",
            "![Experiment readiness](figures/experiment_readiness.svg)",
            "",
            "## Run inventory",
            "",
            _markdown_table(inventory_headers, _inventory_rows(index)),
            "",
            "## Benchmark comparison",
            "",
            _markdown_table(benchmark_headers, _benchmark_rows(comparison)),
            "",
            "![Return comparison](figures/benchmark_return.svg)",
            "",
            "![Drawdown comparison](figures/benchmark_drawdown.svg)",
            "",
            "## Agent and HPO ablation signals",
            "",
            _markdown_table(
                ["Run", "Kind", "Preset", "Signal", "Value", "Status"],
                _ablation_rows(index),
            ),
            "",
            "![Agent and HPO signal](figures/agent_hpo_signal.svg)",
            "",
        )
    )


def build_softwarex_report(config: SoftwareXReportConfig) -> ReportBuildSummary:
    """Generate deterministic tables, SVG figures, Markdown, HTML, and browser."""
    workspace = config.workspace_root.resolve()
    runs_root = resolve_inside(config.runs_root, workspace)
    output_root = resolve_inside(config.output_dir, workspace)
    report_dir = output_root / config.report_id
    if report_dir.is_relative_to(runs_root):
        raise ValueError("report output cannot be inside runs_root")
    report_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = report_dir / "figures"
    tables_dir = report_dir / "tables"
    figures_dir.mkdir(exist_ok=True)
    tables_dir.mkdir(exist_ok=True)

    evidence = _evidence_paths(config, workspace)
    index = build_run_index(
        workspace,
        runs_root,
        include_run_ids=config.include_run_ids,
        max_runs=config.max_runs,
        max_json_bytes=config.max_json_bytes,
    )
    comparison = build_benchmark_comparison(
        index,
        workspace,
        partition=config.partition,
        max_json_bytes=config.max_json_bytes,
    )

    inventory_headers = [
        "run_id",
        "kind",
        "status",
        "algorithm",
        "partitions",
        "artifact_count",
        "fingerprint",
    ]
    benchmark_headers = [
        "run_id",
        "algorithm",
        "seed",
        "mean_return",
        "sharpe",
        "sortino",
        "max_drawdown",
        "calmar",
        "cvar_95",
        "mean_turnover",
        "total_cost",
        "cross_seed_variance",
        "runtime_seconds",
    ]
    experiment_headers = ["category", "label", "status", "evidence", "notes"]
    ablation_headers = ["run_id", "kind", "preset", "signal", "value", "status"]
    _write_csv(tables_dir / "run_inventory.csv", inventory_headers, _inventory_rows(index))
    _write_csv(
        tables_dir / "benchmark_comparison.csv",
        benchmark_headers,
        _benchmark_rows(comparison),
    )
    _write_csv(
        tables_dir / "experiment_readiness.csv",
        experiment_headers,
        _experiment_rows(config.experiments),
    )
    _write_csv(
        tables_dir / "agent_hpo_ablation.csv",
        ablation_headers,
        _ablation_rows(index),
    )

    write_bar_chart(
        figures_dir / "benchmark_return.svg",
        title=f"{config.partition.capitalize()} mean return",
        y_label="Mean return",
        values=[(row.algorithm, row.mean_return) for row in comparison.rows],
    )
    write_bar_chart(
        figures_dir / "benchmark_drawdown.svg",
        title=f"{config.partition.capitalize()} maximum drawdown",
        y_label="Maximum drawdown",
        values=[(row.algorithm, row.max_drawdown) for row in comparison.rows],
        color="#dc2626",
    )
    status_value = {"completed": 2.0, "partial": 1.0, "planned": 0.0}
    write_bar_chart(
        figures_dir / "experiment_readiness.svg",
        title="SoftwareX experiment readiness",
        y_label="0 planned / 1 partial / 2 completed",
        values=[
            (experiment.category, status_value[experiment.status])
            for experiment in config.experiments
        ],
        color="#0f766e",
    )
    ablation = _ablation_rows(index)
    write_bar_chart(
        figures_dir / "agent_hpo_signal.svg",
        title="Agent and HPO acceptance signals",
        y_label="Recorded signal",
        values=[
            (
                str(row[0]),
                float(row[4]) if isinstance(row[4], int | float) else None,
            )
            for row in ablation
        ],
        color="#7c3aed",
    )

    report_data: dict[str, Any] = {
        "report_id": config.report_id,
        "selection_authority": False,
        "run_index": index.model_dump(mode="json"),
        "benchmark": comparison.model_dump(mode="json"),
        "experiments": [
            experiment.model_dump(mode="json") for experiment in config.experiments
        ],
    }
    (report_dir / "report_data.json").write_text(
        json.dumps(report_data, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (report_dir / "run_index.json").write_text(
        index.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    (report_dir / "report.md").write_text(
        _render_markdown(config, index, comparison),
        encoding="utf-8",
    )

    inventory_table = _html_table(
        ["Run", "Kind", "Status", "Algorithm", "Partitions", "Artifacts", "Fingerprint"],
        _inventory_rows(index),
    )
    environment = Environment(autoescape=True)
    html_report = environment.from_string(_HTML_TEMPLATE).render(
        title=config.title,
        index_hash=index.fingerprint,
        partition=config.partition,
        experiment_table=_html_table(
            ["Category", "Label", "Status", "Evidence", "Notes"],
            _experiment_rows(config.experiments),
        ),
        inventory_table=inventory_table,
        benchmark_table=_html_table(
            [
                "Run",
                "Algorithm",
                "Seed",
                "Return",
                "Sharpe",
                "Sortino",
                "Max drawdown",
                "Calmar",
                "CVaR",
                "Turnover",
                "Cost",
                "Seed variance",
                "Runtime s",
            ],
            _benchmark_rows(comparison),
        ),
        ablation_table=_html_table(
            ["Run", "Kind", "Preset", "Signal", "Value", "Status"],
            ablation,
        ),
    )
    (report_dir / "report.html").write_text(html_report + "\n", encoding="utf-8")
    browser = environment.from_string(_BROWSER_TEMPLATE).render(
        inventory_table=inventory_table
    )
    (report_dir / "runs.html").write_text(browser + "\n", encoding="utf-8")

    generated = sorted(
        (
            path
            for path in report_dir.rglob("*")
            if path.is_file() and path.name != "manifest.json"
        ),
        key=lambda item: item.as_posix(),
    )
    config_hash = hashlib.sha256(config.model_dump_json().encode()).hexdigest()
    manifest = ReportManifest(
        report_id=config.report_id,
        source_index_sha256=index.fingerprint,
        config_sha256=config_hash,
        evidence_sha256=combined_sha256(evidence, root=workspace),
        artifacts=tuple(
            ReportArtifact(
                relative_path=path.relative_to(report_dir).as_posix(),
                sha256=sha256_file(path),
                size_bytes=path.stat().st_size,
            )
            for path in generated
        ),
    )
    manifest_path = report_dir / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return ReportBuildSummary(
        report_id=config.report_id,
        report_dir=str(report_dir),
        markdown=str(report_dir / "report.md"),
        html=str(report_dir / "report.html"),
        run_browser=str(report_dir / "runs.html"),
        manifest=str(manifest_path),
        run_count=len(index.runs),
        benchmark_rows=len(comparison.rows),
        figure_count=4,
        source_index_sha256=index.fingerprint,
    )


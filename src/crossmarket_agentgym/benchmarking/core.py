"""Build and verify the immutable Phase 13 benchmark-v1 artifact."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import stat
import tempfile
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from crossmarket_agentgym.benchmarking.models import (
    BenchmarkCheck,
    BenchmarkResult,
    PaperExportResult,
)
from crossmarket_agentgym.benchmarking.render import (
    csv_text,
    html_text,
    latex_text,
    markdown_text,
    svg_chart,
    svg_line_chart,
)

BENCHMARK_ID = "benchmark-v1"
REQUIRED_DIRECTORIES = (
    "symbols",
    "splits",
    "metrics",
    "trades",
    "weights",
    "agent_logs",
    "tuning_logs",
    "tables",
    "figures",
    "statistical_tests",
)
REQUIRED_FILES = (
    "README.md",
    "protocol.yaml",
    "protocol.sha256",
    "dataset_manifest.json",
    "dataset_manifest.sha256",
    "code_commit.txt",
    "seeds.json",
    "runs.csv",
    "checksums.json",
    "benchmark_report.html",
    "IMMUTABLE.json",
)
TABLE_GROUPS = {
    "environment_validation": "A",
    "strategy_comparison": "B",
    "cross_market_generalization": "C",
    "market_mechanism_ablation": "D",
    "agent_ablation": "E",
    "hpo_comparison": "F",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, value: Any) -> None:
    _write(
        path,
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
    )


def _copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _source_file(source_root: Path, relative: str) -> Path:
    path = (source_root / relative).resolve()
    if source_root.resolve() not in path.parents:
        raise ValueError(f"source path escapes root: {relative}")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _verify_source_package(source_root: Path) -> None:
    manifest = _json(_source_file(source_root, "checksums.json"))
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("source checksums.json has no files")
    for relative, expected in files.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise ValueError("source checksum entry has invalid types")
        path = _source_file(source_root, relative)
        if _sha256(path) != expected:
            raise ValueError(f"source checksum mismatch: {relative}")
    if manifest.get("file_count") != len(files):
        raise ValueError("source checksum file_count mismatch")


def _protocol_hash(protocol_path: Path) -> str:
    digest = _sha256(protocol_path)
    checksum = protocol_path.with_suffix(".sha256")
    if checksum.is_file():
        expected = checksum.read_text(encoding="utf-8").split()[0]
        if expected != digest:
            raise ValueError("protocol checksum does not match protocol content")
    return digest


def _formal_runs(
    source_root: Path,
    matrix: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    tasks = matrix.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("run matrix contains no tasks")
    rows: list[dict[str, Any]] = []
    artifact_rows: list[dict[str, Any]] = []
    agent_rows: list[dict[str, Any]] = []
    for raw_task in tasks:
        if not isinstance(raw_task, dict):
            raise ValueError("invalid run matrix task")
        run_id = str(raw_task["run_id"])
        run_root = source_root / "runs" / run_id
        formal = _json(_source_file(run_root, "formal_run.json"))
        result_path = _source_file(run_root, "result.json")
        result = _json(result_path)
        recorded_task = formal.get("task")
        if recorded_task != raw_task:
            raise ValueError(f"configuration/run mismatch: {run_id}")
        status = str(formal.get("status"))
        failure = formal.get("failure_reason")
        if status != "completed" and not failure:
            raise ValueError(f"failed run lacks an explanation: {run_id}")
        artifacts = formal.get("artifacts")
        if not isinstance(artifacts, list):
            raise ValueError(f"run has no artifact inventory: {run_id}")
        configuration_hash = ""
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            relative = str(artifact.get("path", ""))
            if relative == "configuration_lock.json":
                configuration_hash = str(artifact.get("sha256", ""))
            category = (
                "trades"
                if "/trades" in relative
                else "weights"
                if "/weights" in relative
                else "checkpoints"
                if "checkpoint" in relative or relative.endswith(".zip")
                else "other"
            )
            artifact_rows.append(
                {
                    "run_id": run_id,
                    "group": raw_task["group"],
                    "method": raw_task["method"],
                    "category": category,
                    "artifact_path": relative,
                    "sha256": artifact.get("sha256", ""),
                    "size_bytes": artifact.get("size_bytes", ""),
                    "payload_in_benchmark": False,
                }
            )
        if raw_task["group"] == "E":
            replay_files = sorted(run_root.rglob("replay.jsonl"))
            directive_files = sorted(run_root.rglob("directive_replay.json"))
            if not replay_files and str(raw_task["method"]) != "no_llm":
                raise ValueError(f"Agent run lacks replay evidence: {run_id}")
            for path in (*replay_files, *directive_files):
                relative = path.relative_to(run_root).as_posix()
                agent_rows.append(
                    {
                        "run_id": run_id,
                        "method": raw_task["method"],
                        "source_path": relative,
                        "sha256": _sha256(path),
                        "line_count": sum(
                            1 for _ in path.open(encoding="utf-8")
                        ),
                    }
                )
        rows.append(
            {
                "run_id": run_id,
                "group": raw_task["group"],
                "method": raw_task["method"],
                "seed": raw_task["seed"],
                "status": status,
                "failure_reason": failure or "",
                "formal": raw_task.get("formal") is True,
                "protocol_sha256": raw_task["protocol_sha256"],
                "dataset_manifest_sha256": raw_task["dataset_manifest_sha256"],
                "code_commit": raw_task["code_commit"],
                "configuration_sha256": configuration_hash,
                "result_sha256": _sha256(result_path),
                "test_access_count": formal.get("test_partition_access_count", 0),
                "development_result_accessed": formal.get(
                    "development_result_accessed", False
                ),
                "runtime_seconds": result.get(
                    "runtime_seconds", formal.get("wall_time_seconds", "")
                ),
            }
        )
    return rows, artifact_rows, agent_rows


def _export_table(root: Path, name: str, rows: Sequence[Mapping[str, Any]]) -> None:
    for suffix, content in (
        ("csv", csv_text(rows)),
        ("md", markdown_text(rows)),
        ("html", html_text(rows)),
        ("tex", latex_text(rows)),
    ):
        _write(root / "tables" / f"{name}.{suffix}", content)


def _table_rows(
    descriptive: list[dict[str, str]],
    run_metrics: list[dict[str, str]],
    dataset: Mapping[str, Any],
    source_root: Path,
) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    files = dataset.get("files", [])
    market_rows: dict[str, int] = defaultdict(int)
    market_symbols: dict[str, set[str]] = defaultdict(set)
    if isinstance(files, list):
        for item in files:
            if not isinstance(item, dict) or item.get("role") != "ohlcv":
                continue
            for market in item.get("markets", []):
                market_rows[str(market)] += int(item.get("row_count", 0))
                market_symbols[str(market)].update(
                    str(symbol) for symbol in item.get("symbols", [])
                )
    tables["dataset_statistics"] = [
        {
            "market": market,
            "symbols": len(market_symbols[market]),
            "rows": market_rows[market],
            "date_start": dataset.get("date_start"),
            "date_end": dataset.get("date_end"),
            "manifest": "dataset_manifest.json",
        }
        for market in sorted(market_rows)
    ]
    for name, group in TABLE_GROUPS.items():
        tables[name] = [
            row for row in descriptive if row.get("group") == group
        ]
    cost_metrics = {
        "runtime_seconds",
        "additional_runtime_seconds",
        "token_cost",
        "api_cost",
        "total_cost",
    }
    tables["run_cost"] = [
        row for row in descriptive if row.get("metric") in cost_metrics
    ]
    tables["third_party_reproduction"] = [
        {
            "evidence_id": "phase11-cpu-independent-reproduction",
            "run_id": "repro-ppo-quickstart",
            "reproduction_level": "numerically_reproduced",
            "p0_count": 0,
            "p1_count": 0,
            "source_file": "metrics/third_party_reproduction.md",
        }
    ]
    run_ids: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for row in run_metrics:
        run_ids[(row["group"], row["method"], row["metric"])].append(row["run_id"])
    for rows in tables.values():
        for row in rows:
            key = (
                str(row.get("group", "")),
                str(row.get("method", "")),
                str(row.get("metric", "")),
            )
            if key in run_ids:
                row["source_run_ids"] = ";".join(sorted(run_ids[key]))
    return tables


def _copy_agent_logs(
    source_root: Path,
    target_root: Path,
    agent_rows: list[dict[str, Any]],
) -> None:
    for row in agent_rows:
        source = (
            source_root / "runs" / str(row["run_id"]) / str(row["source_path"])
        )
        target = (
            target_root
            / "agent_logs"
            / str(row["run_id"])
            / str(row["source_path"])
        )
        _copy(source, target)
    _write(target_root / "agent_logs" / "index.csv", csv_text(agent_rows))


def _tuning_logs(source_root: Path, target_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for run_root in sorted((source_root / "runs").glob("*-F-*")):
        result_path = run_root / "result.json"
        report_path = run_root / "study_report.json"
        if not result_path.is_file() or not report_path.is_file():
            continue
        result = _json(result_path)
        report = _json(report_path)
        run_id = run_root.name
        for point in result.get("convergence", []):
            if not isinstance(point, dict):
                continue
            objectives = point.get("objectives", [])
            rows.append(
                {
                    "run_id": run_id,
                    "method": result.get("method"),
                    "seed": result.get("seed"),
                    "trial_id": point.get("trial_id"),
                    "objective": objectives[0] if objectives else "",
                    "status": point.get("status"),
                }
            )
        audits.append(
            {
                "run_id": run_id,
                "partition_policy": report.get("partition_policy"),
                "test_metrics_present_during_search": report.get(
                    "test_metrics_present"
                ),
                "test_partition_visible_during_search": result.get(
                    "test_partition_visible_during_search"
                ),
                "test_evaluation_count": result.get("test_evaluation_count"),
                "scheduler_role": result.get("scheduler_role"),
                "trial_budget": result.get("trial_budget"),
            }
        )
        _copy(
            report_path,
            target_root / "tuning_logs" / run_id / "study_report.json",
        )
    _write(target_root / "tuning_logs" / "convergence.csv", csv_text(rows))
    _write(target_root / "tuning_logs" / "hpo_audit.csv", csv_text(audits))
    return rows


def _figure_specs(
    tables: Mapping[str, list[dict[str, Any]]],
    convergence: list[dict[str, Any]],
    agent_rows: list[dict[str, Any]],
) -> dict[str, tuple[str, list[dict[str, Any]], str, str, str | None]]:
    strategy = tables["strategy_comparison"]
    mean_return = [
        row for row in strategy if row.get("metric") == "mean_return"
    ]
    drawdown_by_method = {
        row["method"]: row.get("mean", "")
        for row in strategy
        if row.get("metric") == "max_drawdown"
    }
    for row in mean_return:
        row["mean_drawdown"] = drawdown_by_method.get(row["method"], "")
    turnover = [
        row for row in strategy if row.get("metric") == "mean_turnover"
    ]
    cross = [
        row
        for row in tables["cross_market_generalization"]
        if row.get("metric") == "mean_return"
    ]
    agent_counts = Counter(str(row["method"]) for row in agent_rows)
    agent_calls = [
        {"method": method, "log_count": count}
        for method, count in sorted(agent_counts.items())
    ]
    hpo_best: dict[str, float] = {}
    hpo_curve: list[dict[str, Any]] = []
    for row in convergence:
        try:
            value = float(row["objective"])
        except (TypeError, ValueError):
            continue
        method = str(row["method"])
        hpo_best[method] = max(value, hpo_best.get(method, float("-inf")))
        hpo_curve.append(
            {
                **row,
                "label": f"{method}:{row['trial_id']}",
            }
        )
    pareto = [
        {"method": method, "best_validation_objective": value}
        for method, value in sorted(hpo_best.items())
    ]
    return {
        "training_curve": (
            "HPO training objective by trial",
            hpo_curve,
            "label",
            "objective",
            None,
        ),
        "equity_and_drawdown": (
            "Final return and maximum drawdown",
            mean_return,
            "method",
            "mean",
            "mean_drawdown",
        ),
        "market_exposure": (
            "Cross-market evaluation return",
            cross,
            "method",
            "mean",
            None,
        ),
        "turnover": (
            "Mean strategy turnover",
            turnover,
            "method",
            "mean",
            None,
        ),
        "agent_tool_calls": (
            "Agent replay and directive log count",
            agent_calls,
            "method",
            "log_count",
            None,
        ),
        "hpo_convergence": (
            "HPO convergence across frozen trials",
            hpo_curve,
            "label",
            "objective",
            None,
        ),
        "pareto_front": (
            "Best validation objective by searcher",
            pareto,
            "method",
            "best_validation_objective",
            None,
        ),
        "cross_market_matrix": (
            "Cross-market generalization matrix data",
            cross,
            "method",
            "mean",
            None,
        ),
        "confidence_intervals": (
            "Strategy mean return with 95% interval endpoint",
            mean_return,
            "method",
            "mean",
            "ci95_high",
        ),
    }


def _verified_visual_payload(
    source_root: Path,
    visual_root: Path | None,
    target_root: Path,
    dataset: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    if visual_root is None:
        return {}
    run_id = "p12v4m6-B-ppo-s1024"
    run_root = source_root / "runs" / run_id
    formal = _json(_source_file(run_root, "formal_run.json"))
    artifacts = {
        str(item["path"]): str(item["sha256"])
        for item in formal.get("artifacts", [])
        if isinstance(item, dict) and "path" in item and "sha256" in item
    }
    relative_paths = (
        "model/training/training_metrics.jsonl",
        "model/training/test/trades.json",
        "model/training/test/weights.json",
    )
    payload_root = visual_root / run_id
    hashes: dict[str, str] = {}
    for relative in relative_paths:
        path = _source_file(payload_root, relative)
        actual = _sha256(path)
        if artifacts.get(relative) != actual:
            raise ValueError(f"visual payload hash mismatch: {run_id}/{relative}")
        hashes[relative] = actual
        _copy(
            path,
            target_root / "metrics" / "representative_run" / Path(relative).name,
        )
    training: list[dict[str, Any]] = []
    training_path = payload_root / relative_paths[0]
    with training_path.open(encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            if not isinstance(record, dict):
                continue
            values = record.get("portfolio_values", [])
            training.append(
                {
                    "timesteps": record.get("timesteps"),
                    "mean_reward": record.get("mean_reward"),
                    "portfolio_value": values[-1] if values else "",
                    "source_run_id": run_id,
                    "source_artifact_sha256": hashes[relative_paths[0]],
                }
            )
    weights = json.loads((payload_root / relative_paths[2]).read_text(encoding="utf-8"))
    if not isinstance(weights, list):
        raise ValueError("representative weights payload must be a JSON array")
    equity: list[dict[str, Any]] = []
    market_series: list[dict[str, Any]] = []
    symbol_markets: dict[str, str] = {}
    for item in dataset.get("files", []):
        if not isinstance(item, dict) or item.get("role") != "ohlcv":
            continue
        markets = item.get("markets", [])
        for symbol in item.get("symbols", []):
            if markets:
                symbol_markets[str(symbol)] = str(markets[0])
    symbols = [str(symbol) for symbol in dataset.get("symbols", [])]
    market_totals: dict[str, list[float]] = defaultdict(list)
    for record in weights:
        if not isinstance(record, dict):
            continue
        equity.append(
            {
                "execution_date": record.get("execution_date"),
                "portfolio_value": record.get("portfolio_value"),
                "drawdown": record.get("drawdown"),
                "source_run_id": run_id,
                "source_artifact_sha256": hashes[relative_paths[2]],
            }
        )
        realized = record.get("realized", [])
        if not isinstance(realized, list) or len(realized) != len(symbols) + 1:
            raise ValueError("representative weight vector does not match dataset symbols")
        per_market: dict[str, float] = defaultdict(float)
        for symbol, value in zip(symbols, realized[1:], strict=True):
            per_market[symbol_markets[symbol]] += float(value)
        for market, value in sorted(per_market.items()):
            market_totals[market].append(value)
            market_series.append(
                {
                    "execution_date": record.get("execution_date"),
                    "market": market,
                    "realized_weight": value,
                    "source_run_id": run_id,
                    "source_artifact_sha256": hashes[relative_paths[2]],
                }
            )
    market_rows = [
        {
            "market": name,
            "mean_realized_weight": sum(values) / len(values),
            "maximum_realized_weight": max(values),
            "source_run_id": run_id,
            "source_artifact_sha256": hashes[relative_paths[2]],
        }
        for name, values in sorted(market_totals.items())
    ]
    _write(
        target_root / "figures" / "market_exposure.timeseries.csv",
        csv_text(market_series),
    )
    _write_json(
        target_root / "metrics" / "representative_run" / "payload_manifest.json",
        {
            "run_id": run_id,
            "artifacts": hashes,
            "purpose": "Phase 13 training, equity/drawdown and market-exposure figures",
        },
    )
    return {"training": training, "equity": equity, "market": market_rows}


def _render_figures(
    target_root: Path,
    tables: Mapping[str, list[dict[str, Any]]],
    convergence: list[dict[str, Any]],
    agent_rows: list[dict[str, Any]],
    visual_payload: Mapping[str, list[dict[str, Any]]],
) -> None:
    architecture_nodes = [
        "frozen protocol",
        "dataset manifest",
        "formal run matrix",
        "Groups A-F",
        "tables and figures",
        "paper provenance",
    ]
    architecture_data: dict[str, Any] = {
        "nodes": architecture_nodes,
        "edges": [
            ["frozen protocol", "formal run matrix"],
            ["dataset manifest", "formal run matrix"],
            ["formal run matrix", "Groups A-F"],
            ["Groups A-F", "tables and figures"],
            ["tables and figures", "paper provenance"],
        ],
    }
    _write_json(target_root / "figures" / "architecture.data.json", architecture_data)
    _write(
        target_root / "figures" / "architecture.svg",
        svg_chart(
            "Benchmark-v1 architecture data",
            [
                {"label": node, "order": index + 1}
                for index, node in enumerate(architecture_nodes)
            ],
            label_key="label",
            value_key="order",
        ),
    )
    sources: dict[str, Any] = {
        "architecture.svg": {
            "source": "figures/architecture.data.json",
            "run_ids": [],
        }
    }
    specs = _figure_specs(
        tables, convergence, agent_rows
    )
    if visual_payload:
        specs["training_curve"] = (
            "PPO training reward and portfolio value",
            visual_payload["training"],
            "timesteps",
            "mean_reward",
            "portfolio_value",
        )
        specs["equity_and_drawdown"] = (
            "PPO locked-test equity and drawdown",
            visual_payload["equity"],
            "execution_date",
            "portfolio_value",
            "drawdown",
        )
        specs["market_exposure"] = (
            "PPO locked-test realized market exposure",
            visual_payload["market"],
            "market",
            "mean_realized_weight",
            "maximum_realized_weight",
        )
    for name, (title, rows, label, value, secondary) in specs.items():
        chart = (
            svg_line_chart(
                title,
                rows,
                value_key=value,
                secondary_key=secondary,
            )
            if visual_payload and name in {"training_curve", "equity_and_drawdown"}
            else svg_chart(
                title,
                rows,
                label_key=label,
                value_key=value,
                secondary_key=secondary,
            )
        )
        _write(target_root / "figures" / f"{name}.svg", chart)
        data_file = target_root / "figures" / f"{name}.data.csv"
        _write(data_file, csv_text(rows))
        run_ids = sorted(
            {
                run_id
                for row in rows
                for run_id in str(row.get("source_run_ids", row.get("run_id", ""))).split(
                    ";"
                )
                if run_id
            }
        )
        sources[f"{name}.svg"] = {
            "source": f"figures/{name}.data.csv",
            "run_ids": run_ids,
        }
    _write_json(target_root / "figures" / "sources.json", sources)


def _artifact_indexes(target_root: Path, rows: list[dict[str, Any]]) -> None:
    for category in ("trades", "weights"):
        selected = [row for row in rows if row["category"] == category]
        _write(target_root / category / "artifact_index.csv", csv_text(selected))
    _write(
        target_root / "metrics" / "artifact_index.csv",
        csv_text([row for row in rows if row["category"] not in {"trades", "weights"}]),
    )


def _checksums(target_root: Path) -> dict[str, Any]:
    files = {
        path.relative_to(target_root).as_posix(): _sha256(path)
        for path in sorted(target_root.rglob("*"))
        if path.is_file() and path.name != "checksums.json"
    }
    return {
        "schema_version": "1.0",
        "benchmark_id": BENCHMARK_ID,
        "algorithm": "sha256",
        "self_excluded": "checksums.json",
        "file_count": len(files),
        "files": files,
    }


def _seal(target_root: Path) -> None:
    for path in sorted(target_root.rglob("*"), reverse=True):
        mode = path.stat().st_mode
        if path.is_file():
            path.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        elif path.is_dir():
            path.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    mode = target_root.stat().st_mode
    target_root.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def _benchmark_report(
    run_rows: list[dict[str, Any]],
    protocol_hash: str,
    dataset_hash: str,
    code_commit: str,
) -> str:
    counts = Counter(str(row["group"]) for row in run_rows)
    group_html = "".join(
        f"<li>Group {group}: {count} runs</li>" for group, count in sorted(counts.items())
    )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<title>CrossMarketAgentGym benchmark-v1</title></head><body>"
        "<h1>benchmark-v1</h1>"
        "<p>Immutable, formal-results-only Phase 13 benchmark.</p>"
        f"<p>Protocol SHA-256: <code>{protocol_hash}</code></p>"
        f"<p>Dataset SHA-256: <code>{dataset_hash}</code></p>"
        f"<p>Formal code commit: <code>{code_commit}</code></p>"
        f"<p>Completed runs: {len(run_rows)}; failures: "
        f"{sum(row['status'] != 'completed' for row in run_rows)}</p>"
        f"<ul>{group_html}</ul>"
        "<p>Every table and figure has a machine-readable source mapping. HPO search "
        "used training/walk-forward validation only and performed one locked-test "
        "evaluation after configuration lock.</p>"
        "<p>This benchmark evaluates research software; it is not investment advice "
        "and does not claim live-trading profitability.</p>"
        "</body></html>\n"
    )


def build_benchmark(
    protocol: str | Path,
    *,
    source_root: str | Path = "results/phase12-review-v1",
    output: str | Path = "benchmarks/v1",
    visual_payload_root: str | Path | None = None,
    seal: bool = True,
) -> BenchmarkResult:
    """Build benchmark-v1 once from a checksummed Phase 12 review package."""
    protocol_path = Path(protocol).resolve()
    source = Path(source_root).resolve()
    visual_source = (
        Path(visual_payload_root).resolve()
        if visual_payload_root is not None
        else None
    )
    destination = Path(output).resolve()
    if destination.exists():
        raise FileExistsError(f"benchmark destination already exists: {destination}")
    if not protocol_path.is_file():
        raise FileNotFoundError(protocol_path)
    _verify_source_package(source)
    source_protocol = _source_file(source, "inputs/experiments/protocol_v4.yaml")
    protocol_hash = _protocol_hash(protocol_path)
    if protocol_hash != _sha256(source_protocol):
        raise ValueError("selected protocol is not the frozen formal-run protocol")
    protocol_data = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
    if not isinstance(protocol_data, dict) or protocol_data.get("status") != "frozen":
        raise ValueError("protocol must be frozen")
    matrix_path = _source_file(source, "inputs/experiments/run_matrix_v6.json")
    matrix = _json(matrix_path)
    dataset_path = _source_file(
        source,
        "inputs/data/processed/formal_v3/dataset_manifest.json",
    )
    dataset_hash = _sha256(dataset_path)
    if matrix.get("protocol_sha256") != protocol_hash:
        raise ValueError("matrix/protocol identity mismatch")
    if matrix.get("dataset_manifest_sha256") != dataset_hash:
        raise ValueError("matrix/dataset identity mismatch")
    code_commit = str(matrix.get("code_commit", ""))
    if len(code_commit) != 40:
        raise ValueError("matrix code commit is invalid")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=".benchmark-v1-", dir=destination.parent)
    )
    try:
        for directory in REQUIRED_DIRECTORIES:
            (temporary / directory).mkdir(parents=True, exist_ok=True)
        _copy(protocol_path, temporary / "protocol.yaml")
        _write(temporary / "protocol.sha256", f"{protocol_hash}  protocol.yaml\n")
        _copy(dataset_path, temporary / "dataset_manifest.json")
        _write(
            temporary / "dataset_manifest.sha256",
            f"{dataset_hash}  dataset_manifest.json\n",
        )
        _write(temporary / "code_commit.txt", code_commit + "\n")
        dataset = _json(dataset_path)
        market_symbols: dict[str, list[str]] = defaultdict(list)
        for item in dataset.get("files", []):
            if not isinstance(item, dict) or item.get("role") != "ohlcv":
                continue
            for market in item.get("markets", []):
                market_symbols[str(market)].extend(
                    str(symbol) for symbol in item.get("symbols", [])
                )
        for market, symbols in sorted(market_symbols.items()):
            rows = [{"market": market, "symbol": symbol} for symbol in sorted(set(symbols))]
            _write(temporary / "symbols" / f"{market}.csv", csv_text(rows))
        _write_json(
            temporary / "splits" / "partitions.json",
            protocol_data.get("partitions", {}),
        )
        seeds = protocol_data.get("compute", {}).get("seeds", [])
        _write_json(temporary / "seeds.json", {"seeds": seeds})
        run_rows, artifacts, agent_rows = _formal_runs(source, matrix)
        _write(temporary / "runs.csv", csv_text(run_rows))
        _artifact_indexes(temporary, artifacts)
        _copy_agent_logs(source, temporary, agent_rows)
        summary_root = source / "evidence" / "summary"
        for name in (
            "run_metrics.csv",
            "descriptive_statistics.csv",
            "phase12_summary.json",
            "additional_safety_audit.json",
            "statistical_output_audit.json",
        ):
            _copy(_source_file(summary_root, name), temporary / "metrics" / name)
        for name in ("paired_tests.csv", "paired_tests.md"):
            _copy(
                _source_file(summary_root, name),
                temporary / "statistical_tests" / name,
            )
        reproduction_source = Path("reproducibility_tests/reproducibility_report.md")
        if reproduction_source.is_file():
            _copy(
                reproduction_source,
                temporary / "metrics" / "third_party_reproduction.md",
            )
        else:
            _write(
                temporary / "metrics" / "third_party_reproduction.md",
                "# Phase 11 third-party reproduction\n\n"
                "See the release evidence bundle for the checksummed report.\n",
            )
        descriptive = _read_csv(summary_root / "descriptive_statistics.csv")
        run_metrics = _read_csv(summary_root / "run_metrics.csv")
        tables = _table_rows(descriptive, run_metrics, dataset, source)
        for name, rows in tables.items():
            _export_table(temporary, name, rows)
        table_sources = {
            name: {
                "artifact": f"tables/{name}.csv",
                "source": (
                    "dataset_manifest.json"
                    if name == "dataset_statistics"
                    else "metrics/third_party_reproduction.md"
                    if name == "third_party_reproduction"
                    else "metrics/descriptive_statistics.csv"
                ),
                "run_ids": (
                    []
                    if name == "third_party_reproduction"
                    else sorted(
                        {
                            run_id
                            for row in rows
                            for run_id in str(
                                row.get("source_run_ids", row.get("run_id", ""))
                            ).split(";")
                            if run_id
                        }
                    )
                ),
            }
            for name, rows in tables.items()
        }
        _write_json(temporary / "tables" / "sources.json", table_sources)
        convergence = _tuning_logs(source, temporary)
        visual_payload = _verified_visual_payload(
            source,
            visual_source,
            temporary,
            dataset,
        )
        _render_figures(
            temporary,
            tables,
            convergence,
            agent_rows,
            visual_payload,
        )
        immutable = {
            "schema_version": "1.0",
            "benchmark_id": BENCHMARK_ID,
            "immutability": "write_once_checksums_and_filesystem_read_only",
            "overwrite_allowed": False,
            "filesystem_sealed": seal,
            "formal_results_only": True,
            "source_matrix": matrix.get("matrix_id"),
            "source_review_storage": "external_audit_not_embedded",
            "protocol_sha256": protocol_hash,
            "dataset_manifest_sha256": dataset_hash,
            "code_commit": code_commit,
            "run_count": len(run_rows),
        }
        _write_json(temporary / "IMMUTABLE.json", immutable)
        _write(
            temporary / "README.md",
            "# CrossMarketAgentGym benchmark-v1\n\n"
            "This directory is a write-once Phase 13 snapshot generated only from "
            "the frozen Phase 12 formal matrix. It must never be overwritten. "
            "Create `benchmarks/v2` for a revised protocol or reviewer-requested "
            "experiment.\n\n"
            "Large trades, weights, and checkpoints are represented by immutable "
            "path/size/SHA-256 indexes; small metrics, statistical results, Agent "
            "Replay, and HPO audit evidence are included directly.\n",
        )
        _write(
            temporary / "benchmark_report.html",
            _benchmark_report(run_rows, protocol_hash, dataset_hash, code_commit),
        )
        _write_json(temporary / "checksums.json", _checksums(temporary))
        temporary_verification = verify_benchmark(temporary)
        if not temporary_verification.is_valid:
            failed = [
                check.name
                for check in temporary_verification.checks
                if not check.passed
            ]
            raise ValueError(f"generated benchmark failed verification: {failed}")
        os.replace(temporary, destination)
        if seal:
            _seal(destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return verify_benchmark(destination)


def _check(name: str, passed: bool, detail: str) -> BenchmarkCheck:
    return BenchmarkCheck(name=name, passed=passed, detail=detail)


def verify_benchmark(benchmark: str | Path) -> BenchmarkResult:
    """Verify hashes, provenance, run/config bindings, leakage and Agent evidence."""
    root = Path(benchmark).resolve()
    checks: list[BenchmarkCheck] = []
    if not root.is_dir():
        return BenchmarkResult(
            benchmark=root,
            benchmark_id=BENCHMARK_ID,
            is_valid=False,
            file_count=0,
            run_count=0,
            checks=(_check("benchmark_exists", False, "directory is missing"),),
        )
    missing = [
        relative
        for relative in (*REQUIRED_DIRECTORIES, *REQUIRED_FILES)
        if not (root / relative).exists()
    ]
    checks.append(_check("required_tree", not missing, f"missing={missing}"))
    checksum_path = root / "checksums.json"
    checksum_files: dict[str, Any] = {}
    mismatches: list[str] = []
    extras: list[str] = []
    if checksum_path.is_file():
        checksum_data = _json(checksum_path)
        raw_files = checksum_data.get("files", {})
        checksum_files = raw_files if isinstance(raw_files, dict) else {}
        for relative, expected in checksum_files.items():
            path = root / relative
            if not path.is_file() or _sha256(path) != expected:
                mismatches.append(relative)
        actual = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file() and path.name != "checksums.json"
        }
        extras = sorted(actual - set(checksum_files))
        if checksum_data.get("file_count") != len(checksum_files):
            mismatches.append("checksums.json:file_count")
    else:
        mismatches.append("checksums.json")
    checks.append(
        _check(
            "file_hashes",
            not mismatches and not extras,
            f"mismatches={mismatches}; extras={extras}",
        )
    )
    run_rows = _read_csv(root / "runs.csv") if (root / "runs.csv").is_file() else []
    immutable = _json(root / "IMMUTABLE.json") if (root / "IMMUTABLE.json").is_file() else {}
    identities = {
        (
            row.get("protocol_sha256"),
            row.get("dataset_manifest_sha256"),
            row.get("code_commit"),
        )
        for row in run_rows
    }
    expected_identity = (
        immutable.get("protocol_sha256"),
        immutable.get("dataset_manifest_sha256"),
        immutable.get("code_commit"),
    )
    runs_valid = (
        bool(run_rows)
        and len(identities) == 1
        and expected_identity in identities
        and all(
            row.get("status") == "completed" or row.get("failure_reason")
            for row in run_rows
        )
        and all(row.get("formal") == "True" for row in run_rows)
        and all(row.get("development_result_accessed") == "False" for row in run_rows)
    )
    checks.append(
        _check(
            "config_run_correspondence",
            runs_valid,
            f"runs={len(run_rows)} identities={len(identities)}",
        )
    )
    hpo_rows = (
        _read_csv(root / "tuning_logs" / "hpo_audit.csv")
        if (root / "tuning_logs" / "hpo_audit.csv").is_file()
        else []
    )
    hpo_valid = bool(hpo_rows) and all(
        row.get("partition_policy") == "train_and_validation_only"
        and row.get("test_metrics_present_during_search") == "False"
        and row.get("test_partition_visible_during_search") == "False"
        and row.get("test_evaluation_count") == "1"
        and row.get("scheduler_role") == "resource_only"
        for row in hpo_rows
    )
    checks.append(
        _check(
            "hpo_test_isolation",
            hpo_valid,
            f"audited_hpo_runs={len(hpo_rows)}",
        )
    )
    agent_index = root / "agent_logs" / "index.csv"
    agent_rows = _read_csv(agent_index) if agent_index.is_file() else []
    agent_methods = {
        str(row["method"]) for row in agent_rows if row.get("method") is not None
    }
    required_agent_methods = {
        row.get("method")
        for row in run_rows
        if row.get("group") == "E" and row.get("method") != "no_llm"
    }
    agent_valid = bool(agent_rows) and required_agent_methods <= agent_methods
    checks.append(
        _check(
            "agent_log_completeness",
            agent_valid,
            f"log_rows={len(agent_rows)} methods={sorted(agent_methods)}",
        )
    )
    provenance_errors: list[str] = []
    for relative in ("tables/sources.json", "figures/sources.json"):
        path = root / relative
        if not path.is_file():
            provenance_errors.append(relative)
            continue
        for artifact, record in _json(path).items():
            if not isinstance(record, dict):
                provenance_errors.append(f"{relative}:{artifact}")
                continue
            source = root / str(record.get("source", ""))
            directory = "tables" if relative.startswith("tables") else "figures"
            artifact_path = root / str(
                record.get("artifact", f"{directory}/{artifact}")
            )
            if not source.is_file() or not artifact_path.is_file():
                provenance_errors.append(f"{relative}:{artifact}")
            unknown = set(record.get("run_ids", [])) - {
                row["run_id"] for row in run_rows
            }
            if unknown:
                provenance_errors.append(f"{relative}:{artifact}:unknown_runs")
    checks.append(
        _check(
            "table_figure_provenance",
            not provenance_errors,
            f"errors={provenance_errors}",
        )
    )
    payload_manifest_path = (
        root / "metrics" / "representative_run" / "payload_manifest.json"
    )
    payload_errors: list[str] = []
    payload_count = 0
    if payload_manifest_path.is_file():
        payload_manifest = _json(payload_manifest_path)
        payload_run_id = str(payload_manifest.get("run_id", ""))
        raw_artifacts = payload_manifest.get("artifacts", {})
        if not isinstance(raw_artifacts, dict):
            payload_errors.append("invalid_payload_manifest")
            raw_artifacts = {}
        indexed: set[tuple[str, str, str]] = set()
        for index_path in (
            root / "metrics" / "artifact_index.csv",
            root / "trades" / "artifact_index.csv",
            root / "weights" / "artifact_index.csv",
        ):
            for row in _read_csv(index_path):
                indexed.add(
                    (
                        row.get("run_id", ""),
                        row.get("artifact_path", ""),
                        row.get("sha256", ""),
                    )
                )
        for relative, expected in raw_artifacts.items():
            payload_count += 1
            embedded = (
                root / "metrics" / "representative_run" / Path(relative).name
            )
            if (
                not embedded.is_file()
                or _sha256(embedded) != expected
                or (payload_run_id, relative, expected) not in indexed
            ):
                payload_errors.append(str(relative))
    elif immutable.get("run_count") == 215:
        payload_errors.append("formal_visual_payload_missing")
    checks.append(
        _check(
            "representative_visual_payload",
            not payload_errors,
            f"verified_artifacts={payload_count}; errors={payload_errors}",
        )
    )
    readonly = immutable.get("overwrite_allowed") is False
    sealed = immutable.get("filesystem_sealed") is True
    checks.append(
        _check(
            "immutable_snapshot",
            readonly,
            (
                f"{immutable.get('immutability', 'missing marker')}; "
                f"filesystem_sealed={sealed}"
            ),
        )
    )
    return BenchmarkResult(
        benchmark=root,
        benchmark_id=str(immutable.get("benchmark_id", BENCHMARK_ID)),
        is_valid=all(check.passed for check in checks),
        file_count=len(checksum_files) + (1 if checksum_path.is_file() else 0),
        run_count=len(run_rows),
        checks=tuple(checks),
    )


def export_paper_artifacts(
    benchmark: str | Path,
    artifact_kind: str,
    *,
    output: str | Path | None = None,
) -> PaperExportResult:
    """Copy verified tables or figures without mutating the frozen benchmark."""
    if artifact_kind not in {"tables", "figures"}:
        raise ValueError("artifact_kind must be tables or figures")
    root = Path(benchmark).resolve()
    verification = verify_benchmark(root)
    if not verification.is_valid:
        raise ValueError("benchmark verification failed")
    destination = (
        Path(output).resolve()
        if output is not None
        else Path("paper/generated/benchmark-v1").resolve() / artifact_kind
    )
    if destination.exists():
        raise FileExistsError(f"paper export destination exists: {destination}")
    shutil.copytree(root / artifact_kind, destination)
    files = sum(1 for path in destination.rglob("*") if path.is_file())
    return PaperExportResult(
        benchmark=root,
        output=destination,
        artifact_kind=artifact_kind,
        file_count=files,
        is_valid=True,
    )

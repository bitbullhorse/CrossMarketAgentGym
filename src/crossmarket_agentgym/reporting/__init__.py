"""Deterministic auditable Markdown/HTML reporting and run-browser APIs."""

from crossmarket_agentgym.reporting.benchmarks import build_benchmark_comparison
from crossmarket_agentgym.reporting.indexer import build_run_index
from crossmarket_agentgym.reporting.models import (
    BenchmarkComparison,
    BenchmarkRow,
    ExperimentDeclaration,
    ReportBuildSummary,
    ReportManifest,
    RunIndex,
    RunRecord,
    SoftwareXReportConfig,
    load_softwarex_report_config,
)
from crossmarket_agentgym.reporting.workflow import build_softwarex_report

__all__ = [
    "BenchmarkComparison",
    "BenchmarkRow",
    "ExperimentDeclaration",
    "ReportBuildSummary",
    "ReportManifest",
    "RunIndex",
    "RunRecord",
    "SoftwareXReportConfig",
    "build_benchmark_comparison",
    "build_run_index",
    "build_softwarex_report",
    "load_softwarex_report_config",
]

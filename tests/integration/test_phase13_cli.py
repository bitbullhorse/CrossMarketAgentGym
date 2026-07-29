from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from crossmarket_agentgym.cli.app import app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = PROJECT_ROOT / "benchmarks" / "v1"


def test_benchmark_verify_cli_and_paper_export(tmp_path: Path) -> None:
    runner = CliRunner()
    verification = runner.invoke(
        app,
        ["benchmark", "verify", "--benchmark", str(BENCHMARK)],
    )
    assert verification.exit_code == 0
    assert '"is_valid": true' in verification.stdout
    tables = runner.invoke(
        app,
        [
            "paper",
            "export-tables",
            "--benchmark",
            str(BENCHMARK),
            "--output",
            str(tmp_path / "tables"),
        ],
    )
    assert tables.exit_code == 0
    assert (tmp_path / "tables" / "strategy_comparison.csv").is_file()
    figures = runner.invoke(
        app,
        [
            "paper",
            "export-figures",
            "--benchmark",
            str(BENCHMARK),
            "--output",
            str(tmp_path / "figures"),
        ],
    )
    assert figures.exit_code == 0
    assert (tmp_path / "figures" / "cross_market_matrix.svg").is_file()

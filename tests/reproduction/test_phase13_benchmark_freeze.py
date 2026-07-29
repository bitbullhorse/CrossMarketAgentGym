from __future__ import annotations

import stat
from pathlib import Path

from crossmarket_agentgym.benchmarking.core import verify_benchmark

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = PROJECT_ROOT / "benchmarks" / "v1"


def test_benchmark_verification_is_reproducible() -> None:
    first = verify_benchmark(BENCHMARK)
    second = verify_benchmark(BENCHMARK)
    assert first.is_valid
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.run_count == 215
    assert first.file_count == 233
    assert all(
        not path.stat().st_mode & stat.S_IWUSR
        for path in BENCHMARK.rglob("*")
        if path.is_file()
    )

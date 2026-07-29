"""Internal subprocess entry points used by the guarded GUI job manager."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from crossmarket_agentgym.reporting.io import resolve_inside
from crossmarket_agentgym.rl.workflow import _evaluate_saved_run

_PORTABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _validation_backtest(
    *,
    workspace_root: Path,
    run_id: str,
    output_dir: Path,
) -> int:
    workspace = workspace_root.resolve()
    if _PORTABLE_ID.fullmatch(run_id) is None:
        raise ValueError("run_id contains unsupported path characters")
    run_dir = resolve_inside(Path("runs") / run_id, workspace)
    isolated_output = resolve_inside(output_dir, workspace)
    result = _evaluate_saved_run(
        run_dir,
        partition="validation",
        config_override=None,
        output_dir_override=isolated_output,
    )
    print(result.model_dump_json(indent=2))
    return 0


def main() -> int:
    """Parse the private worker CLI without extending the frozen cmag contract."""
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    backtest = subcommands.add_parser("validation-backtest")
    backtest.add_argument("--workspace-root", type=Path, default=Path.cwd())
    backtest.add_argument("--run-id", required=True)
    backtest.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "validation-backtest":
        return _validation_backtest(
            workspace_root=arguments.workspace_root,
            run_id=arguments.run_id,
            output_dir=arguments.output_dir,
        )
    raise AssertionError("unreachable worker command")


if __name__ == "__main__":
    raise SystemExit(main())

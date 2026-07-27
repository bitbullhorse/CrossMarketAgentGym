"""Typer command tree for CrossMarketAgentGym."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from crossmarket_agentgym import __version__
from crossmarket_agentgym.data.config import load_data_config
from crossmarket_agentgym.data.dataset import validate_configured_dataset
from crossmarket_agentgym.environments.checks import (
    load_environment_check_config,
    run_environment_checks,
)

app = typer.Typer(
    name="cmag",
    help="Auditable cross-market agent research platform.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
data_app = typer.Typer(help="Inspect, import, and validate market data.", no_args_is_help=True)
env_app = typer.Typer(help="Validate portfolio environments.", no_args_is_help=True)
agent_app = typer.Typer(help="Run single-agent or multi-agent teams.", no_args_is_help=True)
report_app = typer.Typer(
    help="Build reports and browse run evidence.",
    no_args_is_help=False,
    invoke_without_command=True,
)
service_app = typer.Typer(help="Run the optional read-only report service.", no_args_is_help=True)
release_app = typer.Typer(help="Validate local release artifacts.", no_args_is_help=True)
app.add_typer(data_app, name="data")
app.add_typer(env_app, name="env")
app.add_typer(agent_app, name="agent")
app.add_typer(report_app, name="report")
app.add_typer(service_app, name="service")
app.add_typer(release_app, name="release")


def _version_callback(value: bool) -> None:
    """Print the version and terminate before command dispatch."""
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def root(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the installed version and exit.",
        ),
    ] = False,
) -> None:
    """Expose global CLI options."""
    del version


@report_app.callback()
def report_root(
    context: typer.Context,
    run_id: Annotated[str | None, typer.Option("--run-id")] = None,
    workspace_root: Annotated[Path, typer.Option("--workspace-root")] = Path("."),
    runs_root: Annotated[Path, typer.Option("--runs-root")] = Path("runs"),
) -> None:
    """Print one whitelisted run when no report subcommand is selected."""
    if context.invoked_subcommand is not None:
        return
    if run_id is None:
        typer.echo(context.get_help())
        raise typer.Exit()
    from crossmarket_agentgym.reporting import build_run_index

    index = build_run_index(
        workspace_root,
        runs_root,
        include_run_ids=(run_id,),
    )
    typer.echo(index.runs[0].model_dump_json(indent=2))


@data_app.command("validate")
def data_validate(
    config: Annotated[
        Path | None,
        typer.Option("--config", exists=True, dir_okay=False),
    ] = None,
    max_files_per_market: Annotated[
        int | None,
        typer.Option(
            "--max-files-per-market",
            min=1,
            help="Bound legacy source inspection per market; canonical manifests ignore this.",
        ),
    ] = None,
) -> None:
    """Validate source quality and manifest integrity without modifying data."""
    if config is None:
        raise typer.BadParameter("--config is required")
    summary = validate_configured_dataset(
        load_data_config(config),
        max_files_per_market=max_files_per_market,
    )
    typer.echo(summary.model_dump_json(indent=2))
    if not summary.is_valid:
        raise typer.Exit(code=1)


@env_app.command("check")
def env_check(
    config: Annotated[
        Path | None,
        typer.Option("--config", exists=True, dir_okay=False),
    ] = None,
) -> None:
    """Check Gym APIs, random actions, finite values, and accounting invariants."""
    if config is None:
        raise typer.BadParameter("--config is required")
    summary = run_environment_checks(load_environment_check_config(config))
    typer.echo(summary.model_dump_json(indent=2))
    if not summary.is_valid:
        raise typer.Exit(code=1)


@app.command()
def train(
    config: Annotated[
        Path | None,
        typer.Option("--config", exists=True, dir_okay=False),
    ] = None,
) -> None:
    """Train a partition-safe RL policy and persist validation artifacts."""
    if config is None:
        raise typer.BadParameter("--config is required")
    from crossmarket_agentgym.rl import load_train_run_config
    from crossmarket_agentgym.rl.workflow import execute_training_run

    summary = execute_training_run(load_train_run_config(config))
    typer.echo(summary.model_dump_json(indent=2))


@app.command()
def evaluate(
    run_id: Annotated[str | None, typer.Option("--run-id")] = None,
) -> None:
    """Evaluate a saved run once on its locked test partition."""
    if run_id is None:
        raise typer.BadParameter("--run-id is required")
    from crossmarket_agentgym.rl.workflow import evaluate_saved_run

    candidate = Path(run_id)
    run_dir = candidate if candidate.exists() else Path("runs") / run_id
    result = evaluate_saved_run(run_dir, partition="test")
    typer.echo(result.model_dump_json(indent=2))


@app.command()
def tune(
    config: Annotated[
        Path | None,
        typer.Option("--config", exists=True, dir_okay=False),
    ] = None,
) -> None:
    """Tune on training and validation data only."""
    if config is None:
        raise typer.BadParameter("--config is required")
    from crossmarket_agentgym.tuning.config import load_tuning_run_config
    from crossmarket_agentgym.tuning.workflow import execute_tuning_run

    summary = execute_tuning_run(load_tuning_run_config(config))
    typer.echo(summary.model_dump_json(indent=2))


@agent_app.command("run")
def agent_run(
    config: Annotated[
        Path | None,
        typer.Option("--config", exists=True, dir_okay=False),
    ] = None,
) -> None:
    """Run a Phase 6 team or Phase 7 three-layer stack."""
    if config is None:
        raise typer.BadParameter("--config is required")
    import yaml

    with config.open(encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    if isinstance(raw, dict) and "preset" in raw:
        from crossmarket_agentgym.agents.layer_config import (
            load_phase7_run_config,
        )
        from crossmarket_agentgym.agents.layer_stack import execute_phase7_stack

        phase7_summary = execute_phase7_stack(load_phase7_run_config(config))
        typer.echo(phase7_summary.model_dump_json(indent=2))
        return
    from crossmarket_agentgym.agents.config import load_agent_runtime_config
    from crossmarket_agentgym.agents.runtime_workflow import execute_agent_runtime

    runtime_summary = execute_agent_runtime(load_agent_runtime_config(config))
    typer.echo(runtime_summary.model_dump_json(indent=2))


@agent_app.command("provider-check")
def agent_provider_check(
    config: Annotated[
        Path | None,
        typer.Option("--config", exists=True, dir_okay=False),
    ] = None,
) -> None:
    """Run the Phase 5 provider, tool, audit, and replay acceptance loop."""
    if config is None:
        raise typer.BadParameter("--config is required")
    from crossmarket_agentgym.agents.config import load_provider_check_config
    from crossmarket_agentgym.agents.workflow import execute_provider_check

    summary = execute_provider_check(load_provider_check_config(config))
    typer.echo(summary.model_dump_json(indent=2))


@report_app.command("softwarex")
def report_softwarex(
    config: Annotated[
        Path | None,
        typer.Option("--config", exists=True, dir_okay=False),
    ] = None,
) -> None:
    """Generate SoftwareX Markdown, HTML, tables, figures, and run browser."""
    if config is None:
        raise typer.BadParameter("--config is required")
    from crossmarket_agentgym.reporting import (
        build_softwarex_report,
        load_softwarex_report_config,
    )

    summary = build_softwarex_report(load_softwarex_report_config(config))
    typer.echo(summary.model_dump_json(indent=2))


@report_app.command("runs")
def report_runs(
    workspace_root: Annotated[Path, typer.Option("--workspace-root")] = Path("."),
    runs_root: Annotated[Path, typer.Option("--runs-root")] = Path("runs"),
) -> None:
    """Print the whitelisted read-only run index."""
    from crossmarket_agentgym.reporting import build_run_index

    index = build_run_index(workspace_root, runs_root)
    typer.echo(index.model_dump_json(indent=2))


@service_app.command("run")
def service_run(
    config: Annotated[
        Path | None,
        typer.Option("--config", exists=True, dir_okay=False),
    ] = None,
) -> None:
    """Start the optional read-only FastAPI service."""
    if config is None:
        raise typer.BadParameter("--config is required")
    from crossmarket_agentgym.api import load_service_config, run_service

    run_service(load_service_config(config))


@app.command()
def quickstart(
    workspace_root: Annotated[Path, typer.Option("--workspace-root")] = Path("."),
    smoke_steps: Annotated[int, typer.Option("--smoke-steps", min=1)] = 64,
) -> None:
    """Run the packaged four-market CPU validation quickstart."""
    from crossmarket_agentgym.release import run_cpu_quickstart

    summary = run_cpu_quickstart(workspace_root, smoke_steps=smoke_steps)
    typer.echo(summary.model_dump_json(indent=2))
    if not summary.is_valid:
        raise typer.Exit(code=1)


@app.command()
def reproduce(
    run_id: Annotated[str | None, typer.Option("--run-id")] = None,
    workspace_root: Annotated[Path, typer.Option("--workspace-root")] = Path("."),
    runs_root: Annotated[Path, typer.Option("--runs-root")] = Path("runs"),
    verify_only: Annotated[bool, typer.Option("--verify-only")] = False,
    execute: Annotated[bool, typer.Option("--execute")] = False,
    compare: Annotated[bool, typer.Option("--compare")] = False,
    tolerance_config: Annotated[
        Path | None,
        typer.Option("--tolerance-config", exists=True, dir_okay=False),
    ] = None,
    replay_run_id: Annotated[
        str | None,
        typer.Option("--replay-run-id"),
    ] = None,
) -> None:
    """Verify artifacts or explicitly execute an isolated computational replay."""
    if run_id is None:
        raise typer.BadParameter("--run-id is required")
    if verify_only and (execute or compare):
        raise typer.BadParameter("--verify-only cannot be combined with replay flags")
    if execute != compare:
        raise typer.BadParameter("--execute and --compare must be supplied together")
    if not execute and (tolerance_config is not None or replay_run_id is not None):
        raise typer.BadParameter(
            "--tolerance-config and --replay-run-id require --execute --compare"
        )
    from crossmarket_agentgym.release.reproduction import (
        execute_training_replay,
        load_reproduction_tolerance_config,
        verify_run_artifacts,
    )

    result = (
        execute_training_replay(
            workspace_root,
            runs_root,
            run_id,
            tolerance=load_reproduction_tolerance_config(tolerance_config),
            replay_run_id=replay_run_id,
        )
        if execute
        else verify_run_artifacts(workspace_root, runs_root, run_id)
    )
    typer.echo(result.model_dump_json(indent=2))
    if not result.is_valid:
        raise typer.Exit(code=1)


@release_app.command("check")
def release_check(
    workspace_root: Annotated[Path, typer.Option("--workspace-root")] = Path("."),
) -> None:
    """Run local pre-publish checks without changing external state."""
    from crossmarket_agentgym.release import check_release_readiness

    result = check_release_readiness(workspace_root)
    typer.echo(result.model_dump_json(indent=2))
    if not result.is_ready:
        raise typer.Exit(code=1)


@release_app.command("manifest")
def release_manifest(
    dist_dir: Annotated[Path, typer.Option("--dist-dir")] = Path("dist"),
) -> None:
    """Hash locally built wheel and source archives."""
    from crossmarket_agentgym.release import build_release_manifest

    result = build_release_manifest(dist_dir)
    typer.echo(result.model_dump_json(indent=2))


@release_app.command("verify")
def release_verify(
    dist_dir: Annotated[Path, typer.Option("--dist-dir")] = Path("dist"),
) -> None:
    """Inspect built archive metadata, resources, and exclusions."""
    from crossmarket_agentgym.release import verify_distributions

    result = verify_distributions(dist_dir)
    typer.echo(result.model_dump_json(indent=2))
    if not result.is_valid:
        raise typer.Exit(code=1)


@release_app.command("freeze")
def release_freeze(
    workspace_root: Annotated[Path, typer.Option("--workspace-root")] = Path("."),
    write: Annotated[
        bool,
        typer.Option(
            "--write",
            help="Write reviewed inventory and Schema snapshots; default is read-only verify.",
        ),
    ] = False,
) -> None:
    """Export or verify the Phase 10 API and persisted-format freeze."""
    from crossmarket_agentgym.release.freeze import (
        export_frozen_contracts,
        verify_frozen_contracts,
    )

    result = (
        export_frozen_contracts(workspace_root)
        if write
        else verify_frozen_contracts(workspace_root)
    )
    typer.echo(result.model_dump_json(indent=2))
    if not result.is_valid:
        raise typer.Exit(code=1)


def main() -> None:
    """Run the Typer application."""
    app(prog_name="cmag")

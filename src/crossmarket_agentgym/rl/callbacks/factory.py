"""Build required callbacks from one strict configuration."""

from __future__ import annotations

from pathlib import Path

from stable_baselines3.common.callbacks import BaseCallback

from crossmarket_agentgym.environments import CrossMarketPortfolioEnv
from crossmarket_agentgym.rl.callbacks.core import (
    AuditCallback,
    EarlyStopCallback,
    FiniteGuardCallback,
    MaxDrawdownGuardCallback,
    MetricsWriterCallback,
    ModelCheckpointCallback,
    ResourceMonitorCallback,
    ValidationEvaluationCallback,
    ValidationTracker,
)
from crossmarket_agentgym.rl.config import CallbackConfig, TrainerConfig


def build_callbacks(
    config: CallbackConfig,
    trainer: TrainerConfig,
    run_dir: Path,
    *,
    validation_env: CrossMarketPortfolioEnv | None,
) -> tuple[list[BaseCallback], ValidationTracker]:
    """Build callbacks in deterministic evaluation-before-early-stop order."""
    callbacks: list[BaseCallback] = []
    tracker = ValidationTracker()
    if config.checkpoint_freq:
        callbacks.append(
            ModelCheckpointCallback(
                save_freq=config.checkpoint_freq,
                save_path=str(run_dir / "checkpoints"),
                name_prefix="step",
            )
        )
    if config.validation_freq:
        if validation_env is None:
            raise ValueError("validation callback requires a validation environment")
        callbacks.append(
            ValidationEvaluationCallback(
                validation_env,
                frequency=config.validation_freq,
                episodes=trainer.eval_episodes,
                deterministic=trainer.deterministic_eval,
                seed=trainer.seed,
                tracker=tracker,
                output_path=run_dir / "validation.jsonl",
            )
        )
        if config.early_stop_patience:
            callbacks.append(EarlyStopCallback(tracker, config.early_stop_patience))
    if config.finite_guard:
        callbacks.append(FiniteGuardCallback())
    if config.max_drawdown is not None:
        callbacks.append(MaxDrawdownGuardCallback(config.max_drawdown))
    if config.resource_monitor_freq:
        callbacks.append(
            ResourceMonitorCallback(
                config.resource_monitor_freq,
                run_dir / "resources.jsonl",
            )
        )
    if config.audit_freq:
        callbacks.append(AuditCallback(config.audit_freq, run_dir / "audit.jsonl"))
    if config.metrics_freq:
        callbacks.append(
            MetricsWriterCallback(config.metrics_freq, run_dir / "training_metrics.jsonl")
        )
    return callbacks, tracker

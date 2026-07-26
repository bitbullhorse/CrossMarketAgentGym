"""Evaluate every deterministic baseline on the synthetic smoke environment."""

from pathlib import Path

from crossmarket_agentgym.environments import (
    CrossMarketPortfolioEnv,
    EnvironmentConfig,
    MarketDataPanel,
)
from crossmarket_agentgym.evaluation import BASELINES, baseline_by_name, evaluate_policy


def main() -> None:
    """Print smoke-only metrics for every non-RL strategy."""
    panel = MarketDataPanel.from_manifest(Path("data/sample"))
    for name in sorted(BASELINES):
        env = CrossMarketPortfolioEnv(panel, EnvironmentConfig(lookback=2))
        strategy = baseline_by_name(name)
        result = evaluate_policy(env, strategy, algorithm=name)
        print(name, result.metrics)


if __name__ == "__main__":
    main()

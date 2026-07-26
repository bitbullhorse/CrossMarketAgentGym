"""Factories that preserve the SearchAlgorithm/TrialScheduler boundary."""

from __future__ import annotations

from crossmarket_agentgym.tuning.config import SchedulerConfig, SearcherConfig
from crossmarket_agentgym.tuning.models import Direction
from crossmarket_agentgym.tuning.schedulers import (
    ASHAScheduler,
    FIFOScheduler,
    HyperBandScheduler,
    MedianStoppingScheduler,
    PopulationBasedTrainingScheduler,
    ensure_compatible,
)
from crossmarket_agentgym.tuning.schedulers.base import TrialScheduler
from crossmarket_agentgym.tuning.searchers import (
    CMAESSearch,
    DifferentialEvolutionSearch,
    GeneticAlgorithmSearch,
    GridSearch,
    NSGAIISearch,
    ParticleSwarmSearch,
    RandomSearch,
    SimulatedAnnealingSearch,
    TPESearch,
)
from crossmarket_agentgym.tuning.searchers.base import SearchAlgorithm


def create_searcher(config: SearcherConfig) -> SearchAlgorithm:
    """Construct one of the nine search algorithms."""
    if config.type == "random":
        return RandomSearch(config.seed)
    if config.type == "grid":
        return GridSearch(config.seed)
    if config.type == "tpe":
        return TPESearch(
            config.seed,
            startup_trials=config.startup_trials,
            candidate_count=config.candidate_count,
            gamma=config.gamma,
        )
    if config.type == "cma_es":
        return CMAESSearch(
            config.seed,
            population_size=config.population_size,
            sigma=config.sigma,
        )
    if config.type == "nsga_ii":
        return NSGAIISearch(
            config.seed,
            population_size=config.population_size,
            mutation_rate=config.mutation_rate,
        )
    if config.type == "pso":
        return ParticleSwarmSearch(
            config.seed,
            population_size=config.population_size,
            inertia=config.inertia,
            cognitive=config.cognitive,
            social=config.social,
        )
    if config.type == "genetic":
        return GeneticAlgorithmSearch(
            config.seed,
            population_size=config.population_size,
            mutation_rate=config.mutation_rate,
        )
    if config.type == "differential_evolution":
        return DifferentialEvolutionSearch(
            config.seed,
            population_size=config.population_size,
            differential_weight=config.differential_weight,
            crossover_rate=config.crossover_rate,
        )
    return SimulatedAnnealingSearch(
        config.seed,
        temperature=config.temperature,
        cooling=config.cooling,
        step_scale=config.step_scale,
    )


def create_scheduler(
    config: SchedulerConfig,
    *,
    searcher_name: str,
    primary_direction: Direction,
) -> TrialScheduler:
    """Construct a compatible resource scheduler independently of the searcher."""
    ensure_compatible(searcher_name, config.type)
    direction = config.direction or primary_direction
    if config.type == "fifo":
        return FIFOScheduler()
    if config.type == "median":
        return MedianStoppingScheduler(
            grace_period=config.grace_period,
            min_trials=config.min_trials,
            direction=direction,
        )
    if config.type == "asha":
        return ASHAScheduler(
            grace_period=config.grace_period,
            max_resource=config.max_resource,
            reduction_factor=config.reduction_factor,
            direction=direction,
        )
    if config.type == "hyperband":
        return HyperBandScheduler(
            min_resource=config.min_resource,
            max_resource=config.max_resource,
            reduction_factor=config.reduction_factor,
            direction=direction,
        )
    return PopulationBasedTrainingScheduler(
        perturbation_interval=config.perturbation_interval,
        quantile_fraction=config.quantile_fraction,
        direction=direction,
        perturbation_factors=config.perturbation_factors,
    )

"""Nine core SearchAlgorithm implementations."""

from crossmarket_agentgym.tuning.searchers.algorithms import (
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
from crossmarket_agentgym.tuning.searchers.base import BaseSearcher, SearchAlgorithm

SEARCHERS: dict[str, type[BaseSearcher]] = {
    "random": RandomSearch,
    "grid": GridSearch,
    "tpe": TPESearch,
    "cma_es": CMAESSearch,
    "nsga_ii": NSGAIISearch,
    "pso": ParticleSwarmSearch,
    "genetic": GeneticAlgorithmSearch,
    "differential_evolution": DifferentialEvolutionSearch,
    "simulated_annealing": SimulatedAnnealingSearch,
}

__all__ = [
    "SEARCHERS",
    "BaseSearcher",
    "CMAESSearch",
    "DifferentialEvolutionSearch",
    "GeneticAlgorithmSearch",
    "GridSearch",
    "NSGAIISearch",
    "ParticleSwarmSearch",
    "RandomSearch",
    "SearchAlgorithm",
    "SimulatedAnnealingSearch",
    "TPESearch",
]

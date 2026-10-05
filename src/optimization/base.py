"""
Abstract Base Optimizer Module.

Defines the common optimization interface for parameter proposal (suggest),
result registration (register), history tracking, and best candidate extraction.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple


class BaseOptimizer(ABC):
    """Abstract Base Class for optimization engines (Random Search, Bayesian Optimization, etc.)."""

    def __init__(self, search_space: Dict[str, Any], seed: Optional[int] = None):
        """
        Args:
            search_space: Dictionary containing parameter bounds (wn_min, wn_max, wp_min, wp_max, step_size).
            seed: Optional random seed for reproducible sampling.
        """
        self.search_space = search_space
        self.seed = seed
        self.history: List[Dict[str, Any]] = []
        self.best_score: float = -float('inf')
        self.best_candidate_record: Optional[Dict[str, Any]] = None

    @abstractmethod
    def suggest(self) -> Dict[str, float]:
        """Propose the next candidate parameter dictionary.

        Returns:
            Dictionary mapping parameter names to float values, e.g. {'wn': 0.5e-6, 'wp': 1.0e-6}
        """
        pass

    @abstractmethod
    def register(self, candidate: Dict[str, float], result: Dict[str, Any]) -> None:
        """Register the evaluation result of a proposed candidate.

        Args:
            candidate: Parameter dictionary suggested previously.
            result: Evaluation dictionary containing status, metrics, and scalar objective_score.
        """
        pass

    def get_history(self) -> List[Dict[str, Any]]:
        """Return the complete list of registered evaluation records."""
        return self.history

    def get_best_candidate(self) -> Optional[Dict[str, Any]]:
        """Return the evaluation record of the best feasible candidate evaluated so far."""
        return self.best_candidate_record

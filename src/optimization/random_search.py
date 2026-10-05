"""
Random Search Optimizer Module.

Implements uniform i.i.d. random sampling across bounded transistor sizing space (Wn, Wp),
supporting seed reproducibility, optional DRC grid snapping, evaluation history tracking,
and graceful handling of non-oscillating/failed simulation candidates.
"""

from typing import Dict, Any, Optional, Union
from pathlib import Path
import random
import numpy as np

from src.optimization.base import BaseOptimizer


class RandomSearchOptimizer(BaseOptimizer):
    """Uniform i.i.d. Random Search Optimizer for Ring Oscillator transistor sizing."""

    def __init__(self, search_space: Dict[str, Any], seed: Optional[int] = None):
        """
        Args:
            search_space: Dictionary specifying bounds and optional grid step:
                - wn_min: float (minimum NMOS width in meters)
                - wn_max: float (maximum NMOS width in meters)
                - wp_min: float (minimum PMOS width in meters)
                - wp_max: float (maximum PMOS width in meters)
                - step_size: float (optional DRC grid step size in meters, e.g. 10e-9)
            seed: Optional integer seed for reproducible random sampling.
        """
        super().__init__(search_space=search_space, seed=seed)

        # Validate search bounds
        self.wn_min = float(search_space["wn_min"])
        self.wn_max = float(search_space["wn_max"])
        self.wp_min = float(search_space["wp_min"])
        self.wp_max = float(search_space["wp_max"])

        if self.wn_min >= self.wn_max:
            raise ValueError(f"wn_min ({self.wn_min}) must be strictly less than wn_max ({self.wn_max})")
        if self.wp_min >= self.wp_max:
            raise ValueError(f"wp_min ({self.wp_min}) must be strictly less than wp_max ({self.wp_max})")

        self.step_size = search_space.get("step_size")
        if self.step_size is not None:
            self.step_size = float(self.step_size)
            if self.step_size <= 0:
                raise ValueError("step_size must be strictly positive if specified")

        # Initialize random generator
        self.rng = np.random.RandomState(seed) if seed is not None else np.random.RandomState()

    def _snap_to_grid(self, value: float, min_val: float, max_val: float) -> float:
        """Snap a continuous float to the nearest discrete DRC grid step within [min_val, max_val]."""
        if self.step_size is None:
            return value
        snapped = round((value - min_val) / self.step_size) * self.step_size + min_val
        snapped = max(min_val, min(max_val, snapped))
        return round(snapped, 12)

    def suggest(self) -> Dict[str, float]:
        """Generate a random candidate parameter vector [Wn, Wp] within bounds.

        Returns:
            Dictionary with keys 'wn' and 'wp' (in meters).
        """
        raw_wn = self.rng.uniform(self.wn_min, self.wn_max)
        raw_wp = self.rng.uniform(self.wp_min, self.wp_max)

        wn = self._snap_to_grid(raw_wn, self.wn_min, self.wn_max)
        wp = self._snap_to_grid(raw_wp, self.wp_min, self.wp_max)

        return {"wn": wn, "wp": wp}

    def register(self, candidate: Dict[str, float], result: Dict[str, Any]) -> None:
        """Register evaluation output for a proposed candidate.

        Args:
            candidate: Dictionary containing 'wn' and 'wp'.
            result: Result dictionary containing status, metrics, objective_score, and feasibility flag.
        """
        score = float(result.get("objective_score", -float('inf')))
        is_feasible = bool(result.get("is_feasible", False))

        record = {
            "iteration": len(self.history),
            "candidate": candidate,
            "result": result,
            "objective_score": score,
            "is_feasible": is_feasible,
            "status": result.get("status", "UNKNOWN")
        }

        self.history.append(record)

        if is_feasible and score > self.best_score:
            self.best_score = score
            self.best_candidate_record = record

    def evaluate_candidate(self,
                           candidate: Dict[str, float],
                           parameterizer: Any,
                           runner: Any,
                           extractor: Any,
                           objective_evaluator: Any,
                           work_dir: Union[str, Path],
                           iteration_idx: Optional[int] = None) -> Dict[str, Any]:
        """Execute end-to-end evaluation pipeline for a candidate parameter set.

        Args:
            candidate: Dictionary containing 'wn' and 'wp'.
            parameterizer: NetlistParameterizer instance.
            runner: LTspiceRunner instance.
            extractor: MetricExtractor instance.
            objective_evaluator: ObjectiveEvaluator instance.
            work_dir: Working directory for generated netlist and log files.
            iteration_idx: Optional evaluation iteration index.

        Returns:
            Dictionary containing evaluation breakdown, candidate parameters, and objective score.
        """
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

        iter_str = f"iter_{iteration_idx:04d}" if iteration_idx is not None else "iter_temp"
        netlist_path = work_dir / f"run_{iter_str}.net"

        # 1. Parameter Injection (Wn, Wp)
        params_map = {"Wn": candidate["wn"], "Wp": candidate["wp"]}
        parameterizer.generate_netlist(params_map, netlist_path)

        # 2. Simulation Execution
        sim_res = runner.run(netlist_path)

        # 3. Measurement Extraction & Oscillation Check
        metrics = extractor.extract(sim_res)

        # 4. Scalar Objective Calculation
        score, is_feasible, breakdown = objective_evaluator.evaluate(metrics)

        result_payload = {
            "status": metrics.get("status", "FAILED"),
            "is_feasible": is_feasible,
            "objective_score": score,
            "metrics": metrics,
            "breakdown": breakdown,
            "sim_time_sec": sim_res.elapsed_time
        }

        # 5. Register with optimizer
        self.register(candidate, result_payload)

        return result_payload

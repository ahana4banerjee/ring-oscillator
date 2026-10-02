"""
Objective Evaluator & Penalty Engine module.

Calculates scalar objective fitness scores for circuit candidates using weighted
multi-objective utility formulation or Power-Delay Product (PDP).
Handles non-oscillating/failed candidates by applying configurable penalty scores.
"""

from typing import Dict, Any, Optional, Tuple


class ObjectiveEvaluator:
    """Evaluates multi-metric electrical results into a scalar fitness score."""

    def __init__(self,
                 baseline_freq_hz: float = 28491793124.8,
                 baseline_power_w: float = 0.141160332486,
                 w_f: float = 0.5,
                 w_p: float = 0.5,
                 objective_mode: str = "weighted",
                 penalty_value: float = -1.0e9):
        """
        Args:
            baseline_freq_hz: Baseline oscillation frequency (Hz) for normalization (Phase 1-3 baseline).
            baseline_power_w: Baseline power consumption (W) for normalization (Phase 1-3 baseline).
            w_f: Weight for frequency component (e.g. 0.5 for Balanced, 0.7 for Speed-biased).
            w_p: Weight for power component (e.g. 0.5 for Balanced, 0.3 for Speed-biased).
            objective_mode: "weighted" for multi-objective utility or "pdp" for PDP minimization.
            penalty_value: Scalar penalty assigned to invalid/failed/non-oscillating candidates.
        """
        if baseline_freq_hz <= 0:
            raise ValueError("baseline_freq_hz must be strictly positive")
        if baseline_power_w <= 0:
            raise ValueError("baseline_power_w must be strictly positive")

        self.baseline_freq_hz = baseline_freq_hz
        self.baseline_power_w = baseline_power_w
        self.w_f = w_f
        self.w_p = w_p
        self.objective_mode = objective_mode.lower()
        self.penalty_value = penalty_value

    def evaluate(self, metrics: Dict[str, Any]) -> Tuple[float, bool, Dict[str, Any]]:
        """Compute scalar fitness score and evaluation metadata from metrics dictionary.

        Args:
            metrics: Extraction result dictionary returned by MetricExtractor.

        Returns:
            Tuple of (objective_score, is_feasible, breakdown_dict)
            where breakdown_dict includes unweighted components, normalized values, and penalty info.
        """
        is_oscillating = metrics.get("is_oscillating", False)
        status = metrics.get("status", "FAILED")

        # Handle failed or non-oscillating candidates
        if not is_oscillating or status != "SUCCESS":
            breakdown = {
                "objective_mode": self.objective_mode,
                "is_feasible": False,
                "status": status,
                "penalty_applied": True,
                "raw_freq_ghz": metrics.get("freq_ghz"),
                "raw_power_mw": metrics.get("power_mw"),
                "norm_freq": None,
                "norm_power": None,
                "w_f": self.w_f,
                "w_p": self.w_p,
                "objective_score": self.penalty_value
            }
            return self.penalty_value, False, breakdown

        freq_hz = metrics.get("freq_hz")
        power_w = metrics.get("power_w")
        pdp_j = metrics.get("pdp_j")

        if freq_hz is None or power_w is None or freq_hz <= 0 or power_w <= 0:
            breakdown = {
                "objective_mode": self.objective_mode,
                "is_feasible": False,
                "status": "INVALID_METRIC_VALUE",
                "penalty_applied": True,
                "objective_score": self.penalty_value
            }
            return self.penalty_value, False, breakdown

        # Normalize metrics against Phase 1-3 baseline
        norm_freq = freq_hz / self.baseline_freq_hz
        norm_power = power_w / self.baseline_power_w

        if self.objective_mode == "weighted":
            # Multi-objective utility: F = w_f * (f / f_baseline) - w_p * (P / P_baseline)
            score = (self.w_f * norm_freq) - (self.w_p * norm_power)
        elif self.objective_mode == "pdp":
            # Minimize Power-Delay Product (return negative PDP for maximization compatibility)
            score = -pdp_j if pdp_j is not None else self.penalty_value
        else:
            raise ValueError(f"Unknown objective_mode: {self.objective_mode}")

        breakdown = {
            "objective_mode": self.objective_mode,
            "is_feasible": True,
            "status": "SUCCESS",
            "penalty_applied": False,
            "raw_freq_ghz": metrics.get("freq_ghz"),
            "raw_power_mw": metrics.get("power_mw"),
            "norm_freq": norm_freq,
            "norm_power": norm_power,
            "freq_component": self.w_f * norm_freq if self.objective_mode == "weighted" else None,
            "power_component": -self.w_p * norm_power if self.objective_mode == "weighted" else None,
            "w_f": self.w_f,
            "w_p": self.w_p,
            "objective_score": score
        }

        return score, True, breakdown

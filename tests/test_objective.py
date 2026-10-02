"""
Unit tests for Phase 4: Objective Function & Penalty Engine.
"""

import pytest
from src.evaluation.objective import ObjectiveEvaluator

# Normalization constants from Phase 1-3 baseline (Wn=0.5u, Wp=1.0u @ 1.8V)
BASELINE_FREQ_HZ = 28491793124.8  # 28.492 GHz
BASELINE_POWER_W = 0.141160332486  # 141.16 mW


def test_baseline_evaluator_balanced():
    evaluator = ObjectiveEvaluator(
        baseline_freq_hz=BASELINE_FREQ_HZ,
        baseline_power_w=BASELINE_POWER_W,
        w_f=0.5,
        w_p=0.5,
        objective_mode="weighted"
    )

    baseline_metrics = {
        "status": "SUCCESS",
        "is_oscillating": True,
        "freq_hz": BASELINE_FREQ_HZ,
        "freq_ghz": 28.492,
        "power_w": BASELINE_POWER_W,
        "power_mw": 141.16,
        "delay_ps": 3.51,
        "pdp_j": 4.954e-13
    }

    score, feasible, breakdown = evaluator.evaluate(baseline_metrics)

    assert feasible is True
    assert breakdown["penalty_applied"] is False
    assert abs(breakdown["norm_freq"] - 1.0) < 1e-5
    assert abs(breakdown["norm_power"] - 1.0) < 1e-5
    # For baseline under Config B (0.5/0.5): F = 0.5*(1.0) - 0.5*(1.0) = 0.0
    assert abs(score - 0.0) < 1e-5


def test_speed_biased_evaluator():
    evaluator = ObjectiveEvaluator(
        baseline_freq_hz=BASELINE_FREQ_HZ,
        baseline_power_w=BASELINE_POWER_W,
        w_f=0.7,
        w_p=0.3,
        objective_mode="weighted"
    )

    # Fast candidate (Candidate 2: 39.773 GHz, 225.5 mW)
    candidate2_metrics = {
        "status": "SUCCESS",
        "is_oscillating": True,
        "freq_hz": 39773000000.0,
        "freq_ghz": 39.773,
        "power_w": 0.225498,
        "power_mw": 225.498,
        "delay_ps": 2.51,
        "pdp_j": 5.67e-13
    }

    score, feasible, breakdown = evaluator.evaluate(candidate2_metrics)

    assert feasible is True
    assert breakdown["penalty_applied"] is False
    norm_f = 39773000000.0 / BASELINE_FREQ_HZ  # ~ 1.3959
    norm_p = 0.225498 / BASELINE_POWER_W        # ~ 1.5975
    expected_score = (0.7 * norm_f) - (0.3 * norm_p)
    assert abs(score - expected_score) < 1e-4


def test_penalty_handling_non_oscillating():
    evaluator = ObjectiveEvaluator(penalty_value=-1.0e9)

    failed_metrics = {
        "status": "NO_OSCILLATION",
        "is_oscillating": False,
        "error_message": "Measurement failed",
        "freq_hz": None,
        "power_w": 0.10
    }

    score, feasible, breakdown = evaluator.evaluate(failed_metrics)

    assert feasible is False
    assert breakdown["penalty_applied"] is True
    assert score == -1.0e9


def test_pdp_mode():
    evaluator = ObjectiveEvaluator(objective_mode="pdp")

    metrics = {
        "status": "SUCCESS",
        "is_oscillating": True,
        "freq_hz": 28.492e9,
        "power_w": 0.141,
        "pdp_j": 1e-13
    }

    score, feasible, breakdown = evaluator.evaluate(metrics)

    assert feasible is True
    assert score == -1e-13


if __name__ == "__main__":
    pytest.main(["-v", __file__])

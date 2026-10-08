"""
Unit tests for Phase 4: Objective Function & Penalty Engine.
"""

import pytest
from src.evaluation.objective import ObjectiveEvaluator

# Normalization constants from 40nm verified baseline (Wn=0.5u, Wp=1.0u @ 1.1V)
BASELINE_FREQ_HZ = 41069756649.1       # 41.0697566491 GHz
BASELINE_POWER_W = 0.000140169553568   # 140.169553568 uW


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
        "freq_ghz": 41.0697566491,
        "power_w": BASELINE_POWER_W,
        "power_mw": 0.140169553568,
        "delay_ps": 2.434881727,
        "pdp_j": 3.413e-16
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

    candidate_metrics = {
        "status": "SUCCESS",
        "is_oscillating": True,
        "freq_hz": 50000000000.0,
        "freq_ghz": 50.0,
        "power_w": 0.000200,
        "power_mw": 0.200,
        "delay_ps": 2.00,
        "pdp_j": 4.0e-16
    }

    score, feasible, breakdown = evaluator.evaluate(candidate_metrics)

    assert feasible is True
    assert breakdown["penalty_applied"] is False
    norm_f = 50000000000.0 / BASELINE_FREQ_HZ
    norm_p = 0.000200 / BASELINE_POWER_W
    expected_score = (0.7 * norm_f) - (0.3 * norm_p)
    assert abs(score - expected_score) < 1e-4


def test_penalty_handling_non_oscillating():
    evaluator = ObjectiveEvaluator(penalty_value=-1.0e9)

    failed_metrics = {
        "status": "NO_OSCILLATION",
        "is_oscillating": False,
        "error_message": "Measurement failed",
        "freq_hz": None,
        "power_w": 0.0001
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
        "freq_hz": BASELINE_FREQ_HZ,
        "power_w": BASELINE_POWER_W,
        "pdp_j": 3.413e-16
    }

    score, feasible, breakdown = evaluator.evaluate(metrics)

    assert feasible is True
    assert score == -3.413e-16


if __name__ == "__main__":
    pytest.main(["-v", __file__])

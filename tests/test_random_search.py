"""
Unit tests for Phase 5.1: Random Search Optimizer.
"""

import pytest
import numpy as np
from pathlib import Path
from src.optimization.random_search import RandomSearchOptimizer


@pytest.fixture
def search_space():
    return {
        "wn_min": 0.18e-6,
        "wn_max": 0.80e-6,
        "wp_min": 0.36e-6,
        "wp_max": 1.60e-6,
        "step_size": 10e-9  # 10nm
    }


def test_random_search_bounds_enforcement(search_space):
    optimizer = RandomSearchOptimizer(search_space=search_space, seed=42)

    for _ in range(50):
        candidate = optimizer.suggest()
        assert "wn" in candidate
        assert "wp" in candidate
        assert search_space["wn_min"] <= candidate["wn"] <= search_space["wn_max"]
        assert search_space["wp_min"] <= candidate["wp"] <= search_space["wp_max"]


def test_random_search_reproducibility(search_space):
    opt1 = RandomSearchOptimizer(search_space=search_space, seed=123)
    opt2 = RandomSearchOptimizer(search_space=search_space, seed=123)

    samples1 = [opt1.suggest() for _ in range(10)]
    samples2 = [opt2.suggest() for _ in range(10)]

    assert samples1 == samples2


def test_random_search_grid_snapping(search_space):
    optimizer = RandomSearchOptimizer(search_space=search_space, seed=99)

    for _ in range(20):
        candidate = optimizer.suggest()
        # Verify candidate values are snapped to multiples of 10nm offset from min
        wn_offset = candidate["wn"] - search_space["wn_min"]
        wp_offset = candidate["wp"] - search_space["wp_min"]
        
        # Check remainder when divided by step_size is near zero
        assert abs(wn_offset % 10e-9) < 1e-12 or abs(10e-9 - (wn_offset % 10e-9)) < 1e-12
        assert abs(wp_offset % 10e-9) < 1e-12 or abs(10e-9 - (wp_offset % 10e-9)) < 1e-12


def test_random_search_register_and_best_tracking(search_space):
    optimizer = RandomSearchOptimizer(search_space=search_space, seed=42)

    cand1 = {"wn": 0.5e-6, "wp": 1.0e-6}
    res1 = {"status": "SUCCESS", "is_feasible": True, "objective_score": 0.0}

    cand2 = {"wn": 0.8e-6, "wp": 1.6e-6}
    res2 = {"status": "SUCCESS", "is_feasible": True, "objective_score": 0.25}

    cand3 = {"wn": 0.36e-6, "wp": 0.72e-6}
    res3 = {"status": "NO_OSCILLATION", "is_feasible": False, "objective_score": -1.0e9}

    optimizer.register(cand1, res1)
    optimizer.register(cand2, res2)
    optimizer.register(cand3, res3)

    history = optimizer.get_history()
    assert len(history) == 3
    assert history[0]["candidate"] == cand1
    assert history[1]["candidate"] == cand2
    assert history[2]["candidate"] == cand3

    best = optimizer.get_best_candidate()
    assert best is not None
    assert best["candidate"] == cand2
    assert best["objective_score"] == 0.25


def test_random_search_invalid_bounds_error():
    invalid_space = {
        "wn_min": 0.80e-6,
        "wn_max": 0.18e-6,  # min > max
        "wp_min": 0.36e-6,
        "wp_max": 1.60e-6
    }
    with pytest.raises(ValueError, match="wn_min"):
        RandomSearchOptimizer(search_space=invalid_space)


if __name__ == "__main__":
    pytest.main(["-v", __file__])

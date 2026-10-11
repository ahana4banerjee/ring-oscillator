"""
Unit Tests for Bayesian Optimization Engine (Phase 6).

Verifies:
- Parameter bounds and grid validation.
- Discrete 10 nm DRC grid generation (28,013 valid points).
- Phase 1: Latin Hypercube Sampling (N_init = 10, reproducibility, bounds, snapping).
- Gaussian Process Regression with Matérn 5/2 kernel.
- Expected Improvement acquisition calculation.
- Phase 2: Adaptive Bayesian Optimization transition.
- Strict duplicate mitigation and coordinate uniqueness.
- Registration, history tracking, and best candidate extraction.
"""

import pytest
import numpy as np
from src.optimization.bayesian import BayesianOptimizer, GaussianProcessMatern52


@pytest.fixture
def frozen_search_space():
    return {
        "wn_min": 0.12e-6,
        "wn_max": 1.20e-6,
        "wp_min": 0.24e-6,
        "wp_max": 2.80e-6,
        "step_size": 10e-9
    }


def test_search_space_grid_dimensions(frozen_search_space):
    """Verify that the frozen search space yields exactly 109 x 257 = 28,013 discrete points."""
    opt = BayesianOptimizer(search_space=frozen_search_space, seed=2026)
    assert len(opt.wn_grid_vals) == 109  # (1.20 - 0.12)/0.01 + 1 = 109
    assert len(opt.wp_grid_vals) == 257  # (2.80 - 0.24)/0.01 + 1 = 257
    assert opt.num_grid_points == 28013
    assert len(opt.grid_coords) == 28013


def test_invalid_bounds_rejection():
    """Verify invalid bounds (min >= max or negative step) raise ValueError."""
    with pytest.raises(ValueError, match="wn_min"):
        BayesianOptimizer(search_space={"wn_min": 1.0e-6, "wn_max": 0.5e-6, "wp_min": 0.5e-6, "wp_max": 1.0e-6})

    with pytest.raises(ValueError, match="wp_min"):
        BayesianOptimizer(search_space={"wn_min": 0.5e-6, "wn_max": 1.0e-6, "wp_min": 2.0e-6, "wp_max": 1.0e-6})

    with pytest.raises(ValueError, match="step_size"):
        BayesianOptimizer(search_space={"wn_min": 0.5e-6, "wn_max": 1.0e-6, "wp_min": 0.5e-6, "wp_max": 1.0e-6, "step_size": -1e-9})


def test_phase1_lhs_schedule_properties(frozen_search_space):
    """Verify Phase 1 produces exactly 10 distinct, valid, grid-snapped candidates via LHS."""
    opt = BayesianOptimizer(search_space=frozen_search_space, seed=2026, n_initial_samples=10)
    assert len(opt.initial_candidates) == 10

    coords = set()
    for c in opt.initial_candidates:
        wn = c["wn"]
        wp = c["wp"]

        # Check bounds
        assert 0.12e-6 - 1e-12 <= wn <= 1.20e-6 + 1e-12
        assert 0.24e-6 - 1e-12 <= wp <= 2.80e-6 + 1e-12

        # Check 10 nm grid snapping
        wn_nm = round(wn * 1e9, 2)
        wp_nm = round(wp * 1e9, 2)
        assert abs(wn_nm - round(wn_nm / 10.0) * 10.0) < 1e-6
        assert abs(wp_nm - round(wp_nm / 10.0) * 10.0) < 1e-6

        coords.add((round(wn, 12), round(wp, 12)))

    # Confirm all 10 initial candidates are unique
    assert len(coords) == 10


def test_deterministic_seed_reproducibility(frozen_search_space):
    """Verify that identical seeds produce identical candidate schedules."""
    opt1 = BayesianOptimizer(search_space=frozen_search_space, seed=42, n_initial_samples=10)
    opt2 = BayesianOptimizer(search_space=frozen_search_space, seed=42, n_initial_samples=10)

    for _ in range(10):
        c1 = opt1.suggest()
        c2 = opt2.suggest()
        assert c1 == c2


def test_distinct_seeds_produce_different_schedules(frozen_search_space):
    """Verify that different seeds produce distinct LHS schedules."""
    opt1 = BayesianOptimizer(search_space=frozen_search_space, seed=1001, n_initial_samples=10)
    opt2 = BayesianOptimizer(search_space=frozen_search_space, seed=2002, n_initial_samples=10)

    c1 = opt1.suggest()
    c2 = opt2.suggest()
    assert (c1["wn"], c1["wp"]) != (c2["wn"], c2["wp"])


def test_gaussian_process_matern52_fit_and_predict():
    """Verify GaussianProcessMatern52 fits training data and predicts with low variance at training points."""
    gp = GaussianProcessMatern52(nugget=1e-6, random_state=np.random.RandomState(42))

    # Synthetic 2D objective function
    X_train = np.array([
        [0.1, 0.2],
        [0.5, 0.5],
        [0.8, 0.3],
        [0.2, 0.9],
        [0.9, 0.9]
    ])
    y_train = np.array([0.15, 0.85, 0.40, -0.20, 0.05])

    gp.fit(X_train, y_train)

    # Predict at training points
    mu_train, sigma_train = gp.predict(X_train)

    # Predictions should be extremely close to targets at training locations
    np.testing.assert_allclose(mu_train, y_train, atol=1e-3)
    # Predictive uncertainty should be near zero (on order of nugget)
    assert np.all(sigma_train < 0.05)

    # Predict at unobserved point
    X_test = np.array([[0.3, 0.3]])
    mu_test, sigma_test = gp.predict(X_test)
    assert sigma_test[0] > 0.1  # Substantial uncertainty away from training points


def test_expected_improvement_calculation(frozen_search_space):
    """Verify Expected Improvement handles positive, zero, and small sigma values correctly."""
    opt = BayesianOptimizer(search_space=frozen_search_space, seed=2026, xi=0.01)

    mu = np.array([1.2, 0.8, 0.5])
    sigma = np.array([0.3, 0.1, 0.0])
    best_y = 1.0

    ei = opt._compute_expected_improvement(mu, sigma, best_y)

    assert ei[0] > 0.0  # High mean + good variance -> large EI
    assert ei[1] >= 0.0
    assert ei[2] == 0.0  # Zero variance and mean < best_y + xi -> 0.0 EI


def test_phase_transition_and_adaptive_optimization(frozen_search_space):
    """Verify transition from Phase 1 (LHS, 10 samples) to Phase 2 (Adaptive BO) and registration."""
    opt = BayesianOptimizer(search_space=frozen_search_space, seed=2026, n_initial_samples=5)

    # Phase 1: 5 initial LHS samples
    for i in range(5):
        cand = opt.suggest()
        assert len(opt.history) == i
        # Synthetic objective function: higher score for larger Wn
        score = cand["wn"] * 1e6 - 0.5 * cand["wp"] * 1e6
        result = {
            "status": "SUCCESS",
            "is_feasible": True,
            "objective_score": score,
            "metrics": {"freq_ghz": 40.0, "power_mw": 0.15}
        }
        opt.register(cand, result)
        assert opt.history[-1]["acquisition_phase"] == "LHS"

    # Phase 2: Iteration 6 must be ADAPTIVE_BO
    cand_adaptive = opt.suggest()
    assert opt.gp is not None  # GP surrogate was fitted
    result_adaptive = {
        "status": "SUCCESS",
        "is_feasible": True,
        "objective_score": 0.5,
        "metrics": {"freq_ghz": 45.0, "power_mw": 0.18}
    }
    opt.register(cand_adaptive, result_adaptive)
    assert opt.history[-1]["acquisition_phase"] == "ADAPTIVE_BO"


def test_duplicate_mitigation_enforcement(frozen_search_space):
    """Verify that BayesianOptimizer never suggests an already-evaluated coordinate."""
    opt = BayesianOptimizer(search_space=frozen_search_space, seed=2026, n_initial_samples=3)

    evaluated_set = set()
    for _ in range(8):
        cand = opt.suggest()
        coord = (round(cand["wn"], 12), round(cand["wp"], 12))
        assert coord not in evaluated_set, f"Duplicate coordinate suggested: {coord}"
        evaluated_set.add(coord)

        score = float(np.sin(cand["wn"] * 1e7) + np.cos(cand["wp"] * 1e7))
        opt.register(cand, {
            "status": "SUCCESS",
            "is_feasible": True,
            "objective_score": score
        })

    assert len(evaluated_set) == 8
    assert len(opt.history) == 8


def test_best_candidate_tracking(frozen_search_space):
    """Verify that best candidate and score are updated monotonically."""
    opt = BayesianOptimizer(search_space=frozen_search_space, seed=2026, n_initial_samples=3)

    c1 = opt.suggest()
    opt.register(c1, {"status": "SUCCESS", "is_feasible": True, "objective_score": 0.10})
    assert opt.best_score == 0.10
    assert opt.get_best_candidate()["candidate"] == c1

    c2 = opt.suggest()
    opt.register(c2, {"status": "SUCCESS", "is_feasible": True, "objective_score": 0.25})
    assert opt.best_score == 0.25
    assert opt.get_best_candidate()["candidate"] == c2

    # Infeasible candidate should not overwrite best
    c3 = opt.suggest()
    opt.register(c3, {"status": "NO_OSCILLATION", "is_feasible": False, "objective_score": -1e9})
    assert opt.best_score == 0.25
    assert opt.get_best_candidate()["candidate"] == c2

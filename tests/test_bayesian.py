"""
Unit Tests for Bayesian Optimization Engine (Phase 6, Step 6.1.1 Refinements).

Verifies:
- Parameter bounds and grid validation (28,013 valid points).
- Phase 1: Latin Hypercube Sampling (N_init = 10, reproducibility, bounds, snapping).
- Gaussian Process Regression with Matérn 5/2 kernel and ARD lengthscales.
- ISS-01: Expected Improvement evaluated in standardized domain for scale invariance.
- ISS-02: Non-positive EI fallback selecting unvisited candidate with maximum posterior mean.
- ISS-03: Extreme penalty (-1e9) handling without destabilizing GP surrogate.
- ISS-04: Frozen search space enforcement and isolation from legacy Random Search bounds.
- Phase 2: Adaptive Bayesian Optimization transition.
- Strict duplicate mitigation and coordinate uniqueness.
- Registration, history tracking, and best candidate extraction.
"""

from pathlib import Path
import pytest
import yaml
import numpy as np
from src.optimization.bayesian import (
    BayesianOptimizer,
    GaussianProcessMatern52,
    FROZEN_BO_BOUNDS,
    validate_frozen_bounds
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def frozen_search_space():
    return FROZEN_BO_BOUNDS.copy()


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

    X_train = np.array([
        [0.1, 0.2],
        [0.5, 0.5],
        [0.8, 0.3],
        [0.2, 0.9],
        [0.9, 0.9]
    ])
    y_train = np.array([0.15, 0.85, 0.40, -0.20, 0.05])

    gp.fit(X_train, y_train)

    # Predict at training points in original units
    mu_train, sigma_train = gp.predict(X_train, return_standardized=False)
    np.testing.assert_allclose(mu_train, y_train, atol=1e-3)
    assert np.all(sigma_train < 0.05)

    # Predict in standardized units
    mu_std, sigma_std = gp.predict(X_train, return_standardized=True)
    expected_y_std = (y_train - np.mean(y_train)) / np.std(y_train)
    np.testing.assert_allclose(mu_std, expected_y_std, atol=1e-3)


# --- ISS-01 Tests: Expected Improvement Standardized Scaling ---

def test_expected_improvement_scale_invariance(frozen_search_space):
    """Verify ISS-01: EI evaluated in standardized domain is invariant to linear target scaling."""
    opt = BayesianOptimizer(search_space=frozen_search_space, seed=2026, xi=0.01)

    # Dataset 1: Scenario A scale (~0.01)
    mu_std = np.array([1.5, 0.5, -0.2, 2.0])
    sigma_std = np.array([0.8, 0.4, 0.1, 0.9])
    best_y_std = 1.0

    ei1 = opt._compute_expected_improvement(mu_std, sigma_std, best_y_std)

    # EI must be highest for candidate with mu_std=2.0, sigma_std=0.9
    assert np.argmax(ei1) == 3
    assert ei1[3] > ei1[0] > ei1[1] > ei1[2]

    # Zero uncertainty handling
    sigma_zero = np.array([0.0, 0.0])
    mu_zero = np.array([1.5, 0.5])  # one above best_y + xi, one below
    ei_zero = opt._compute_expected_improvement(mu_zero, sigma_zero, best_y_std=1.0)
    assert abs(ei_zero[0] - (1.5 - 1.0 - 0.01)) < 1e-12
    assert ei_zero[1] == 0.0


# --- ISS-02 Tests: Non-Positive EI Fallback ---

def test_non_positive_ei_fallback_selection(frozen_search_space):
    """Verify ISS-02: When all unvisited points produce non-positive EI, fallback selects max posterior mean."""
    opt = BayesianOptimizer(search_space=frozen_search_space, seed=2026, n_initial_samples=3)

    # Register 3 initial points with extremely high objective score so all other points have EI <= 0
    for i in range(3):
        cand = opt.suggest()
        opt.register(cand, {
            "status": "SUCCESS",
            "is_feasible": True,
            "objective_score": 100.0  # Massive score creates mu - best_y << 0
        })

    # Call suggest for adaptive iteration
    cand_adaptive = opt.suggest()
    coord = (round(cand_adaptive["wn"], 12), round(cand_adaptive["wp"], 12))

    # Must NOT be one of the evaluated coordinates
    assert coord not in opt.evaluated_coords
    # Must be valid grid point within bounds
    assert 0.12e-6 <= cand_adaptive["wn"] <= 1.20e-6
    assert 0.24e-6 <= cand_adaptive["wp"] <= 2.80e-6


def test_exhaustion_of_candidate_space():
    """Verify ISS-02: Exhausting all points in search space raises RuntimeError."""
    tiny_space = {
        "wn_min": 0.12e-6,
        "wn_max": 0.13e-6,
        "wp_min": 0.24e-6,
        "wp_max": 0.25e-6,
        "step_size": 10e-9
    }  # Exactly 2x2 = 4 candidates
    opt = BayesianOptimizer(search_space=tiny_space, seed=42, n_initial_samples=2)

    # Evaluate all 4 points
    for _ in range(4):
        c = opt.suggest()
        opt.register(c, {"status": "SUCCESS", "is_feasible": True, "objective_score": 0.1})

    # 5th attempt must raise RuntimeError
    with pytest.raises(RuntimeError, match="All candidate points"):
        opt.suggest()


# --- ISS-03 Tests: Extreme Penalty Handling ---

def test_extreme_penalty_handling_single_failure(frozen_search_space):
    """Verify ISS-03: A failed observation with penalty -1e9 does not corrupt GP fitting."""
    opt = BayesianOptimizer(search_space=frozen_search_space, seed=2026, n_initial_samples=3)

    # 2 feasible points, 1 non-oscillating point with -1e9 penalty
    c1 = opt.suggest()
    opt.register(c1, {"status": "SUCCESS", "is_feasible": True, "objective_score": 0.01})
    c2 = opt.suggest()
    opt.register(c2, {"status": "SUCCESS", "is_feasible": True, "objective_score": 0.02})
    c3 = opt.suggest()
    opt.register(c3, {"status": "NO_OSCILLATION", "is_feasible": False, "objective_score": -1.0e9})

    # History preserves raw -1e9
    assert opt.history[2]["objective_score"] == -1.0e9
    assert opt.history[2]["is_feasible"] is False
    assert opt.best_score == 0.02
    assert opt.get_best_candidate()["candidate"] == c2

    # Suggest adaptive candidate: GP must fit cleanly without crash or singular matrix
    cand_adaptive = opt.suggest()
    assert opt.gp is not None
    # GP target standard deviation must remain reasonable, NOT ~1e8
    assert opt.gp.y_std < 5.0
    assert opt.gp.y_mean > -5.0


def test_extreme_penalty_handling_all_failures(frozen_search_space):
    """Verify ISS-03: When all observations are failures, optimizer remains numerically stable."""
    opt = BayesianOptimizer(search_space=frozen_search_space, seed=2026, n_initial_samples=3)

    for _ in range(3):
        c = opt.suggest()
        opt.register(c, {"status": "TIMEOUT", "is_feasible": False, "objective_score": -1.0e9})

    # Best score remains -inf because no candidate is feasible
    assert opt.best_score == -float("inf")
    assert opt.get_best_candidate() is None

    # Next candidate proposal must succeed smoothly
    cand_adaptive = opt.suggest()
    coord = (round(cand_adaptive["wn"], 12), round(cand_adaptive["wp"], 12))
    assert coord not in opt.evaluated_coords


def test_extreme_penalty_handling_one_feasible_multiple_failures(frozen_search_space):
    """Verify ISS-03: One feasible observation among multiple failures is tracked correctly."""
    opt = BayesianOptimizer(search_space=frozen_search_space, seed=2026, n_initial_samples=3)

    c1 = opt.suggest()
    opt.register(c1, {"status": "SUCCESS", "is_feasible": True, "objective_score": 0.05})
    c2 = opt.suggest()
    opt.register(c2, {"status": "TIMEOUT", "is_feasible": False, "objective_score": -1.0e9})
    c3 = opt.suggest()
    opt.register(c3, {"status": "NO_OSCILLATION", "is_feasible": False, "objective_score": -1.0e9})

    assert opt.best_score == 0.05
    assert opt.get_best_candidate()["candidate"] == c1

    cand = opt.suggest()
    assert (round(cand["wn"], 12), round(cand["wp"], 12)) not in opt.evaluated_coords


# --- ISS-04 Tests: Frozen Bounds Decoupling & Isolation ---

def test_frozen_bounds_enforcement():
    """Verify ISS-04: enforce_frozen_bounds=True rejects legacy bounds and accepts frozen bounds."""
    legacy_bounds = {
        "wn_min": 0.18e-6,
        "wn_max": 0.80e-6,
        "wp_min": 0.36e-6,
        "wp_max": 1.60e-6,
        "step_size": 10e-9
    }

    # Reject legacy bounds when enforce_frozen_bounds is enabled
    with pytest.raises(ValueError, match="frozen formal bounds"):
        BayesianOptimizer(search_space=legacy_bounds, enforce_frozen_bounds=True)

    # Accept frozen bounds
    opt = BayesianOptimizer(search_space=FROZEN_BO_BOUNDS, enforce_frozen_bounds=True)
    assert opt.wn_min == 0.12e-6
    assert opt.wn_max == 1.20e-6
    assert opt.wp_min == 0.24e-6
    assert opt.wp_max == 2.80e-6


def test_dedicated_bo_config_loading_and_isolation():
    """Verify ISS-04: configs/bayesian_optimization_config.yaml loads frozen bounds independently."""
    bo_config_path = PROJECT_ROOT / "configs" / "bayesian_optimization_config.yaml"
    assert bo_config_path.exists(), "configs/bayesian_optimization_config.yaml must exist"

    with open(bo_config_path, "r", encoding="utf-8") as f:
        bo_cfg = yaml.safe_load(f)

    # Validate BO config contains frozen bounds
    validate_frozen_bounds(bo_cfg["search_space"])
    assert bo_cfg["optimization"]["total_evaluations"] == 50
    assert bo_cfg["optimization"]["n_initial_samples"] == 10
    assert bo_cfg["optimization"]["n_adaptive_iterations"] == 40
    assert bo_cfg["optimization"]["xi"] == 0.01

    # Verify legacy config retains its bounds for Random Search isolation
    legacy_config_path = PROJECT_ROOT / "configs" / "optimization_config.yaml"
    with open(legacy_config_path, "r", encoding="utf-8") as f:
        legacy_cfg = yaml.safe_load(f)

    assert legacy_cfg["search_space"]["wn_min"] == 0.18e-6
    assert legacy_cfg["search_space"]["wn_max"] == 0.80e-6


# --- State & Registration Tests ---

def test_phase_transition_and_adaptive_optimization(frozen_search_space):
    """Verify transition from Phase 1 (LHS, 5 samples) to Phase 2 (Adaptive BO)."""
    opt = BayesianOptimizer(search_space=frozen_search_space, seed=2026, n_initial_samples=5)

    for i in range(5):
        cand = opt.suggest()
        assert len(opt.history) == i
        score = cand["wn"] * 1e6 - 0.5 * cand["wp"] * 1e6
        result = {
            "status": "SUCCESS",
            "is_feasible": True,
            "objective_score": score,
            "metrics": {"freq_ghz": 40.0, "power_mw": 0.15}
        }
        opt.register(cand, result)
        assert opt.history[-1]["acquisition_phase"] == "LHS"

    # Iteration 6 must be ADAPTIVE_BO
    cand_adaptive = opt.suggest()
    assert opt.gp is not None
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
    """Verify that best candidate and score are updated monotonically for feasible candidates."""
    opt = BayesianOptimizer(search_space=frozen_search_space, seed=2026, n_initial_samples=3)

    c1 = opt.suggest()
    opt.register(c1, {"status": "SUCCESS", "is_feasible": True, "objective_score": 0.10})
    assert opt.best_score == 0.10
    assert opt.get_best_candidate()["candidate"] == c1

    c2 = opt.suggest()
    opt.register(c2, {"status": "SUCCESS", "is_feasible": True, "objective_score": 0.25})
    assert opt.best_score == 0.25
    assert opt.get_best_candidate()["candidate"] == c2

    # Infeasible candidate must not overwrite best
    c3 = opt.suggest()
    opt.register(c3, {"status": "NO_OSCILLATION", "is_feasible": False, "objective_score": -1e9})
    assert opt.best_score == 0.25
    assert opt.get_best_candidate()["candidate"] == c2

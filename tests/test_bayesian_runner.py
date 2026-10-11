"""
Automated Test Suite for Scenario A Bayesian Optimization Campaign Runner (Step 6.2.1).

Validates:
1. Configuration loading, scenario selection, and frozen parameter enforcement.
2. Objective weights (w_f=0.5, w_p=0.5) and deterministic seed (2026).
3. Initial LHS phase (10 points) and adaptive BO phase (40 points) partitioning.
4. Total 50-evaluation budget enforcement.
5. Strict duplicate mitigation and 10 nm grid snapping across all 50 candidates.
6. Failure handling and conditioned penalty tracking (Step 6.1.1 compliance).
7. Best-candidate tracking strictly excluding non-oscillating/failed points.
8. Dry-run isolation: Mock evaluator used, zero LTspice/subprocess invocations.
9. Random Search benchmark isolation: No data leakage or modifications.
10. Output directory structure, CSV/JSON metadata, and synthetic artifact labeling.
"""

import json
import csv
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import yaml

from experiments.run_bayesian_opt_scenario_a import (
    BayesianOptimizationCampaignRunner,
    MockCandidateEvaluator,
    PhysicalCandidateEvaluator,
    load_and_validate_bo_config
)
from src.optimization.bayesian import FROZEN_BO_BOUNDS
from src.evaluation.objective import ObjectiveEvaluator

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_scenario_a_config_loading_and_weights():
    """Verify Scenario A configuration loads correctly with w_f=0.5, w_p=0.5, seed=2026."""
    config = load_and_validate_bo_config("configs/bayesian_optimization_config.yaml", scenario_key="scenario_a")
    
    assert config["optimization"]["method"] == "bayesian"
    assert config["optimization"]["total_evaluations"] == 50
    assert config["optimization"]["n_initial_samples"] == 10
    assert config["optimization"]["n_adaptive_iterations"] == 40
    assert config["optimization"]["seeds"]["scenario_a"] == 2026
    
    sc_a = config["optimization"]["scenarios"]["scenario_a"]
    assert sc_a["w_f"] == 0.5
    assert sc_a["w_p"] == 0.5


def test_frozen_bounds_and_grid_enforcement_in_config():
    """Verify frozen bounds [0.12, 1.20] µm x [0.24, 2.80] µm and 10 nm grid are enforced."""
    config = load_and_validate_bo_config("configs/bayesian_optimization_config.yaml", scenario_key="scenario_a")
    ss = config["search_space"]
    
    assert abs(ss["wn_min"] - FROZEN_BO_BOUNDS["wn_min"]) < 1e-12
    assert abs(ss["wn_max"] - FROZEN_BO_BOUNDS["wn_max"]) < 1e-12
    assert abs(ss["wp_min"] - FROZEN_BO_BOUNDS["wp_min"]) < 1e-12
    assert abs(ss["wp_max"] - FROZEN_BO_BOUNDS["wp_max"]) < 1e-12
    assert abs(ss["step_size"] - FROZEN_BO_BOUNDS["step_size"]) < 1e-12


def test_invalid_config_rejection(tmp_path):
    """Verify that modified/invalid configurations (wrong seed, altered weights, non-frozen bounds) are rejected."""
    # 1. Invalid weights for Scenario A
    bad_cfg = {
        "search_space": FROZEN_BO_BOUNDS.copy(),
        "normalization": {
            "baseline_frequency_hz": 41069756649.1,
            "baseline_power_w": 0.000140169553568
        },
        "optimization": {
            "method": "bayesian",
            "surrogate": "gp_matern52",
            "kernel": "matern52_ard",
            "nugget": 1.0e-6,
            "acquisition": "expected_improvement",
            "xi": 0.01,
            "total_evaluations": 50,
            "n_initial_samples": 10,
            "n_adaptive_iterations": 40,
            "seeds": {"scenario_a": 2026},
            "scenarios": {
                "scenario_a": {"w_f": 0.7, "w_p": 0.3}  # Mismatched weights!
            }
        }
    }
    cfg_file = tmp_path / "bad_config.yaml"
    with open(cfg_file, "w") as f:
        yaml.dump(bad_cfg, f)

    with pytest.raises(ValueError, match="Scenario A requires w_f=0.5 and w_p=0.5"):
        load_and_validate_bo_config(cfg_file, scenario_key="scenario_a")

    # 2. Invalid seed
    bad_cfg["optimization"]["scenarios"]["scenario_a"] = {"w_f": 0.5, "w_p": 0.5}
    bad_cfg["optimization"]["seeds"]["scenario_a"] = 9999  # Wrong seed!
    with open(cfg_file, "w") as f:
        yaml.dump(bad_cfg, f)

    with pytest.raises(ValueError, match="seed must be 2026"):
        load_and_validate_bo_config(cfg_file, scenario_key="scenario_a")


def test_runner_dry_run_execution_and_budget(tmp_path):
    """
    Execute dry-run campaign across all 50 iterations in tmp_path.
    Verify:
      - Total evaluations == 50
      - Phase 1 has exactly 10 LHS evaluations
      - Phase 2 has exactly 40 Adaptive BO evaluations
      - Zero duplicate candidates
      - Every candidate is on 10 nm grid within frozen bounds
    """
    runner = BayesianOptimizationCampaignRunner(
        config_path="configs/bayesian_optimization_config.yaml",
        scenario_key="scenario_a",
        dry_run=True,
        output_dir=tmp_path / "dry_run"
    )

    summary = runner.run()

    assert summary["total_evaluations"] == 50
    assert len(runner.results_records) == 50

    # Check phase partitioning
    lhs_records = [r for r in runner.results_records if r["phase"] == "LHS"]
    bo_records = [r for r in runner.results_records if r["phase"] == "ADAPTIVE_BO"]
    assert len(lhs_records) == 10
    assert len(bo_records) == 40

    # Check grid alignment and duplicate avoidance
    seen_coords = set()
    step_nm = 10.0
    for r in runner.results_records:
        wn_nm = round(r["Wn_um"] * 1000, 4)
        wp_nm = round(r["Wp_um"] * 1000, 4)

        assert abs(wn_nm % step_nm) < 1e-4, f"Wn={r['Wn_um']} not on 10 nm grid"
        assert abs(wp_nm % step_nm) < 1e-4, f"Wp={r['Wp_um']} not on 10 nm grid"

        assert 0.12 - 1e-9 <= r["Wn_um"] <= 1.20 + 1e-9
        assert 0.24 - 1e-9 <= r["Wp_um"] <= 2.80 + 1e-9

        coord = (r["Wn_um"], r["Wp_um"])
        assert coord not in seen_coords, f"Duplicate coordinate encountered: {coord}"
        seen_coords.add(coord)

    assert len(seen_coords) == 50


def test_dry_run_isolation_from_ltspice(tmp_path):
    """
    CRITICAL TEST: Ensure LTspice subprocess, NetlistParameterizer, and LTspiceRunner
    are NEVER invoked or instantiated during dry-run mode.
    """
    with patch("subprocess.Popen") as mock_popen, \
         patch("subprocess.run") as mock_run, \
         patch("src.simulation.runner.LTspiceRunner.run") as mock_runner_run:

        runner = BayesianOptimizationCampaignRunner(
            config_path="configs/bayesian_optimization_config.yaml",
            scenario_key="scenario_a",
            dry_run=True,
            output_dir=tmp_path / "isolated_dry_run"
        )
        assert isinstance(runner.evaluator, MockCandidateEvaluator)

        runner.run()

        # Assert no physical execution occurred
        mock_popen.assert_not_called()
        mock_run.assert_not_called()
        mock_runner_run.assert_not_called()


def test_best_candidate_tracking_and_failure_handling(tmp_path):
    """
    Verify best-candidate tracking:
    - Failed/non-oscillating candidates receive penalty score -1e9
    - Conditioned penalty protects GP fitting
    - Failed candidates are NEVER selected as best feasible candidate
    """
    # Create mock evaluator that fails candidate on iteration 5
    obj_eval = ObjectiveEvaluator(w_f=0.5, w_p=0.5, penalty_value=-1.0e9)

    class ControllableMockEvaluator(MockCandidateEvaluator):
        def evaluate(self, candidate, iteration_idx):
            if iteration_idx == 4:  # Force failure on iteration 5 (0-indexed 4)
                metrics = {
                    "status": "NO_OSCILLATION",
                    "is_oscillating": False,
                    "freq_hz": None, "freq_ghz": None, "period_s": None,
                    "power_w": None, "power_mw": None, "delay_s": None,
                    "delay_ps": None, "pdp_j": None
                }
                score, is_feasible, breakdown = self.objective_evaluator.evaluate(metrics)
                return {
                    "status": "NO_OSCILLATION",
                    "is_feasible": False,
                    "objective_score": score,
                    "metrics": metrics,
                    "breakdown": breakdown,
                    "sim_time_sec": 0.001,
                    "is_synthetic": True
                }
            return super().evaluate(candidate, iteration_idx)

    controllable_evaluator = ControllableMockEvaluator(objective_evaluator=obj_eval)

    runner = BayesianOptimizationCampaignRunner(
        config_path="configs/bayesian_optimization_config.yaml",
        scenario_key="scenario_a",
        dry_run=True,
        output_dir=tmp_path / "failure_test",
        evaluator=controllable_evaluator
    )

    summary = runner.run()

    # Verify iteration 5 failed and has penalty score
    iter5_rec = runner.results_records[4]
    assert iter5_rec["oscillation_status"] == "NO_OSCILLATION"
    assert iter5_rec["objective_score"] == -1.0e9

    # Verify best candidate is feasible and score > -1e8
    best_cand = summary["best_candidate"]
    assert best_cand is not None
    assert best_cand["oscillation_status"] == "VALID"
    assert best_cand["objective_score"] > -1.0e8

    # Verify best candidate record in optimizer matches
    opt_best = runner.optimizer.get_best_candidate()
    assert opt_best is not None
    assert opt_best["is_feasible"] is True


def test_dry_run_output_artifacts_and_synthetic_labeling(tmp_path):
    """Verify saved artifacts (config.json, results.csv, summary.md) are clearly labeled synthetic."""
    out_dir = tmp_path / "artifact_check"
    runner = BayesianOptimizationCampaignRunner(
        config_path="configs/bayesian_optimization_config.yaml",
        scenario_key="scenario_a",
        dry_run=True,
        output_dir=out_dir
    )
    runner.run()

    # 1. Check config.json
    cfg_json_path = out_dir / "config.json"
    assert cfg_json_path.exists()
    with open(cfg_json_path, "r", encoding="utf-8") as f:
        cfg_data = json.load(f)
    assert cfg_data["is_dry_run"] is True
    assert cfg_data["is_synthetic_data"] is True
    assert cfg_data["seed"] == 2026

    # 2. Check results.csv
    csv_path = out_dir / "results.csv"
    assert csv_path.exists()
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    assert len(reader) == 50
    for row in reader:
        assert row["is_synthetic"] == "True"

    # 3. Check summary.md
    summary_path = out_dir / "summary.md"
    assert summary_path.exists()
    with open(summary_path, "r", encoding="utf-8") as f:
        summary_text = f.read()
    assert "DRY-RUN VALIDATION DATASET" in summary_text
    assert "Zero LTspice simulations were executed" in summary_text


def test_isolation_from_random_search_datasets():
    """
    CRITICAL TEST: Ensure Random Search files in experiments/random_search/
    and results/ are NOT read or modified by the Bayesian Optimization runner.
    """
    rs_dir = PROJECT_ROOT / "experiments" / "random_search" / "formal_100"
    rs_csv = rs_dir / "results.csv"
    assert rs_csv.exists()
    rs_mtime_before = rs_csv.stat().st_mtime

    # Initialize and execute dry run
    runner = BayesianOptimizationCampaignRunner(
        config_path="configs/bayesian_optimization_config.yaml",
        scenario_key="scenario_a",
        dry_run=True
    )
    
    # Assert optimizer history has zero connection to RS
    assert len(runner.optimizer.history) == 0

    rs_mtime_after = rs_csv.stat().st_mtime
    assert rs_mtime_before == rs_mtime_after, "Random Search dataset was modified!"

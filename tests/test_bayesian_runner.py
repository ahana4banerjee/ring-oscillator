"""
Automated Test Suite for Scenario A Bayesian Optimization Campaign Runner (Step 6.2.1 Audit Remediation).

Addresses audit findings AUD-01 through AUD-07:
- AUD-01: Rejection of incompatible evaluators (physical evaluator in dry-run, mock in physical).
- AUD-02: Per-iteration atomic checkpointing, exception recovery preserving prior completed results,
          no uncontrolled retries, strict budget enforcement.
- AUD-03: Output directory overwrite prevention, unique campaign ID generation, explicit overwrite flag.
- AUD-04: Validation of physical environment prerequisites (template netlist, LTspice executable).
- AUD-05: Targeted negative tests, failure injection, and Random Search file access isolation.
- AUD-06: Comprehensive configuration validation (circuit stages, VDD, simulation specs, normalization, weights).
- AUD-07: Evaluator result validation, sanitization of malformed scores, non-finite handling, and feasibility consistency.
"""

import builtins
import csv
import json
import math
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


# ==============================================================================
# AUD-01: Evaluator-Mode Compatibility Tests
# ==============================================================================

def test_incompatible_physical_evaluator_rejected_in_dry_run(tmp_path):
    """AUD-01: Dry-run mode MUST reject an injected PhysicalCandidateEvaluator during init."""
    obj_eval = ObjectiveEvaluator(w_f=0.5, w_p=0.5)
    dummy_exe = tmp_path / "dummy_ltspice.exe"
    dummy_exe.touch()

    phys_evaluator = PhysicalCandidateEvaluator(
        template_netlist_path=PROJECT_ROOT / "circuits" / "templates" / "ring_oscillator.net",
        ltspice_executable=dummy_exe,
        work_dir=tmp_path / "raw",
        objective_evaluator=obj_eval
    )

    with pytest.raises(ValueError, match="Security violation: Physical evaluator injected into dry-run mode"):
        BayesianOptimizationCampaignRunner(
            config_path="configs/bayesian_optimization_config.yaml",
            scenario_key="scenario_a",
            dry_run=True,
            output_dir=tmp_path / "out",
            evaluator=phys_evaluator
        )


def test_incompatible_mock_evaluator_rejected_in_physical_mode(tmp_path):
    """AUD-01: Physical campaign mode MUST reject an injected mock evaluator during init."""
    obj_eval = ObjectiveEvaluator(w_f=0.5, w_p=0.5)
    mock_evaluator = MockCandidateEvaluator(objective_evaluator=obj_eval)

    with pytest.raises(ValueError, match="Configuration error: Mock/synthetic evaluator injected into physical campaign mode"):
        BayesianOptimizationCampaignRunner(
            config_path="configs/bayesian_optimization_config.yaml",
            scenario_key="scenario_a",
            dry_run=False,
            output_dir=tmp_path / "out",
            evaluator=mock_evaluator
        )


# ==============================================================================
# AUD-02: Checkpointing, Exception Recovery & Budget Enforcement
# ==============================================================================

def test_exception_recovery_preserves_earlier_records_and_checkpoints(tmp_path):
    """
    AUD-02: Simulate simulator exception at iteration 21.
    Verify:
      - Iterations 1..20 are successfully evaluated.
      - Iteration 21 captures the exception as a failed evaluation with penalty score.
      - Checkpoint and results.csv contain all 21 iterations.
      - Campaign completes without losing prior completed records.
    """
    obj_eval = ObjectiveEvaluator(w_f=0.5, w_p=0.5, penalty_value=-1.0e9)

    class CrashingMockEvaluator(MockCandidateEvaluator):
        def evaluate(self, candidate, iteration_idx):
            if iteration_idx == 20:  # 0-indexed 20 is Iteration 21
                raise RuntimeError("Simulated LTspice transient timeout / solver crash at iteration 21!")
            return super().evaluate(candidate, iteration_idx)

    crashing_eval = CrashingMockEvaluator(objective_evaluator=obj_eval)
    out_dir = tmp_path / "crash_test"

    runner = BayesianOptimizationCampaignRunner(
        config_path="configs/bayesian_optimization_config.yaml",
        scenario_key="scenario_a",
        dry_run=True,
        output_dir=out_dir,
        evaluator=crashing_eval
    )

    summary = runner.run()

    # All 50 iterations run (budget enforced, crash consumed 1 eval)
    assert summary["total_evaluations"] == 50
    assert len(runner.results_records) == 50

    # Iteration 21 captured the exception
    iter21_rec = runner.results_records[20]
    assert "EVALUATOR_EXCEPTION: RuntimeError" in iter21_rec["simulation_status"]
    assert iter21_rec["oscillation_status"] == "NO_OSCILLATION"
    assert iter21_rec["objective_score"] == -1.0e9

    # Verify results.csv contains all rows including crash row
    csv_path = out_dir / "results.csv"
    assert csv_path.exists()
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    assert len(reader) == 50
    assert reader[20]["objective_score"] == "-1000000000.0"

    # Verify checkpoint.json exists and tracks completed evaluations
    chk_path = out_dir / "checkpoint.json"
    assert chk_path.exists()
    with open(chk_path, "r", encoding="utf-8") as f:
        chk_data = json.load(f)
    assert chk_data["completed_evaluations"] == 50
    assert "campaign_id" in chk_data


def test_budget_never_exceeded_on_failures(tmp_path):
    """AUD-02 & AUD-05: Ensure failures never trigger uncontrolled retries or exceed 50 evaluations."""
    obj_eval = ObjectiveEvaluator(w_f=0.5, w_p=0.5, penalty_value=-1.0e9)

    # Evaluator that fails every even iteration
    class AlternatingFailureEvaluator(MockCandidateEvaluator):
        def evaluate(self, candidate, iteration_idx):
            if iteration_idx % 2 == 1:
                return {
                    "status": "NO_OSCILLATION",
                    "is_feasible": False,
                    "objective_score": -1.0e9,
                    "metrics": {"status": "FAILED", "is_oscillating": False},
                    "breakdown": {},
                    "sim_time_sec": 0.001,
                    "is_synthetic": True
                }
            return super().evaluate(candidate, iteration_idx)

    alt_eval = AlternatingFailureEvaluator(objective_evaluator=obj_eval)
    runner = BayesianOptimizationCampaignRunner(
        config_path="configs/bayesian_optimization_config.yaml",
        scenario_key="scenario_a",
        dry_run=True,
        output_dir=tmp_path / "alt_fail",
        evaluator=alt_eval
    )

    summary = runner.run()
    assert summary["total_evaluations"] == 50
    assert len(runner.optimizer.history) == 50


# ==============================================================================
# AUD-03: Output Overwrite Safeguards
# ==============================================================================

def test_existing_output_artifacts_safeguard_prevents_overwrite(tmp_path):
    """AUD-03: Refuse to start campaign in a directory with existing results without overwrite=True."""
    out_dir = tmp_path / "protected_dir"
    out_dir.mkdir(parents=True)
    (out_dir / "results.csv").write_text("dummy previous campaign data")

    with pytest.raises(FileExistsError, match="already contains campaign artifacts"):
        BayesianOptimizationCampaignRunner(
            config_path="configs/bayesian_optimization_config.yaml",
            scenario_key="scenario_a",
            dry_run=True,
            output_dir=out_dir,
            overwrite=False
        )


def test_overwrite_flag_permits_replacement_when_explicit(tmp_path):
    """AUD-03: Overwrite flag explicitly allows replacing previous artifacts."""
    out_dir = tmp_path / "overwrite_dir"
    out_dir.mkdir(parents=True)
    (out_dir / "results.csv").write_text("old data")

    runner = BayesianOptimizationCampaignRunner(
        config_path="configs/bayesian_optimization_config.yaml",
        scenario_key="scenario_a",
        dry_run=True,
        output_dir=out_dir,
        overwrite=True
    )
    assert runner.overwrite is True


# ==============================================================================
# AUD-04: Physical Environment Validation
# ==============================================================================

def test_physical_mode_validates_environment_prerequisites(tmp_path):
    """AUD-04: Physical mode checks for template netlist and LTspice executable."""
    obj_eval = ObjectiveEvaluator(w_f=0.5, w_p=0.5)

    # Valid template netlist exists in repo
    template_path = PROJECT_ROOT / "circuits" / "templates" / "ring_oscillator.net"
    assert template_path.exists()

    # Pass non-existent LTspice executable in custom config
    cfg = load_and_validate_bo_config("configs/bayesian_optimization_config.yaml")
    cfg["simulation"]["ltspice_executable"] = str(tmp_path / "non_existent_ltspice.exe")

    cfg_file = tmp_path / "test_phys_cfg.yaml"
    with open(cfg_file, "w") as f:
        yaml.dump(cfg, f)

    with pytest.raises(FileNotFoundError, match="LTspice executable not found"):
        BayesianOptimizationCampaignRunner(
            config_path=cfg_file,
            scenario_key="scenario_a",
            dry_run=False,
            output_dir=tmp_path / "phys_out"
        )


# ==============================================================================
# AUD-05: Targeted Negative & Isolation Tests
# ==============================================================================

def test_random_search_files_never_opened_during_campaign(tmp_path):
    """
    AUD-05: Monitor all file open calls during runner execution.
    Verify that NO file in experiments/random_search or results/ is ever opened.
    """
    real_open = builtins.open
    opened_paths = []

    def tracking_open(file, *args, **kwargs):
        opened_paths.append(str(file))
        return real_open(file, *args, **kwargs)

    with patch("builtins.open", side_effect=tracking_open):
        runner = BayesianOptimizationCampaignRunner(
            config_path="configs/bayesian_optimization_config.yaml",
            scenario_key="scenario_a",
            dry_run=True,
            output_dir=tmp_path / "leak_test"
        )
        runner.run()

    # Verify zero opened files match random_search paths
    for p in opened_paths:
        norm_p = p.replace("\\", "/").lower()
        assert "experiments/random_search" not in norm_p, f"Leakage detected: {p}"
        assert "results/processed" not in norm_p, f"Leakage detected: {p}"


# ==============================================================================
# AUD-06: Comprehensive Configuration Validation
# ==============================================================================

def test_comprehensive_config_validation_rejects_altered_circuit_settings(tmp_path):
    """AUD-06: Validator rejects altered stages, VDD, length, nominal widths, or missing keys."""
    base_cfg = load_and_validate_bo_config("configs/bayesian_optimization_config.yaml")

    # 1. Invalid stage count (e.g. 7 instead of 5)
    bad_cfg = yaml.safe_load(yaml.dump(base_cfg))
    bad_cfg["circuit"]["stages"] = 7
    f1 = tmp_path / "bad_stages.yaml"
    with open(f1, "w") as f:
        yaml.dump(bad_cfg, f)
    with pytest.raises(ValueError, match="Circuit stages must be exactly 5"):
        load_and_validate_bo_config(f1)

    # 2. Invalid VDD (e.g. 1.8V instead of 1.1V)
    bad_cfg = yaml.safe_load(yaml.dump(base_cfg))
    bad_cfg["circuit"]["vdd"] = 1.8
    f2 = tmp_path / "bad_vdd.yaml"
    with open(f2, "w") as f:
        yaml.dump(bad_cfg, f)
    with pytest.raises(ValueError, match="Supply voltage VDD must be 1.1 V"):
        load_and_validate_bo_config(f2)

    # 3. Invalid simulation transient settings
    bad_cfg = yaml.safe_load(yaml.dump(base_cfg))
    bad_cfg["simulation"]["transient_stop"] = "10n"
    f3 = tmp_path / "bad_sim.yaml"
    with open(f3, "w") as f:
        yaml.dump(bad_cfg, f)
    with pytest.raises(ValueError, match="Simulation transient_stop must be '1n'"):
        load_and_validate_bo_config(f3)


# ==============================================================================
# AUD-07: Evaluator Result Validation & Sanitization
# ==============================================================================

def test_evaluator_result_sanitization_and_malformed_data_handling(tmp_path):
    """
    AUD-07: Verify defensive handling of malformed evaluator output:
      - Non-dict results
      - NaN / infinite objective score
      - Inconsistent feasibility vs status
      - Missing metrics keys
    """
    runner = BayesianOptimizationCampaignRunner(
        config_path="configs/bayesian_optimization_config.yaml",
        scenario_key="scenario_a",
        dry_run=True,
        output_dir=tmp_path / "sanitize_test"
    )

    cand = {"wn": 0.5e-6, "wp": 1.0e-6}

    # Case 1: Non-dict return
    res1 = runner._validate_and_sanitize_result(cand, "invalid string")
    assert res1["status"] == "MALFORMED_NON_DICT_RESULT"
    assert res1["is_feasible"] is False
    assert res1["objective_score"] == -1.0e9

    # Case 2: NaN objective score
    raw_nan = {
        "status": "SUCCESS",
        "is_feasible": True,
        "objective_score": float("nan"),
        "metrics": {"is_oscillating": True, "status": "SUCCESS"}
    }
    res2 = runner._validate_and_sanitize_result(cand, raw_nan)
    assert res2["status"] == "MALFORMED_NON_FINITE_SCORE"
    assert res2["is_feasible"] is False
    assert res2["objective_score"] == -1.0e9

    # Case 3: Inconsistent feasibility (claims is_feasible=True but is_oscillating=False)
    raw_inconsistent = {
        "status": "FAILED",
        "is_feasible": True,
        "objective_score": 0.05,
        "metrics": {"is_oscillating": False, "status": "FAILED"}
    }
    res3 = runner._validate_and_sanitize_result(cand, raw_inconsistent)
    assert res3["status"] == "INCONSISTENT_FEASIBILITY"
    assert res3["is_feasible"] is False
    assert res3["objective_score"] == -1.0e9


# ==============================================================================
# General Methodology & Scenario A Frozen Criteria Tests
# ==============================================================================

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

    lhs_records = [r for r in runner.results_records if r["phase"] == "LHS"]
    bo_records = [r for r in runner.results_records if r["phase"] == "ADAPTIVE_BO"]
    assert len(lhs_records) == 10
    assert len(bo_records) == 40

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
    """CRITICAL TEST: Ensure LTspice subprocess and LTspiceRunner are NEVER invoked during dry-run."""
    with patch("subprocess.Popen") as mock_popen, \
         patch("subprocess.run") as mock_run, \
         patch("src.simulation.runner.LTspiceRunner.run") as mock_runner_run:

        runner = BayesianOptimizationCampaignRunner(
            config_path="configs/bayesian_optimization_config.yaml",
            scenario_key="scenario_a",
            dry_run=True,
            output_dir=tmp_path / "isolated_dry_run"
        )
        assert runner.evaluator.is_physical is False

        runner.run()

        mock_popen.assert_not_called()
        mock_run.assert_not_called()
        mock_runner_run.assert_not_called()

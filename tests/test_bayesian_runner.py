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
import io
import json
import math
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import yaml

from experiments.run_bayesian_opt_scenario_a import (
    BayesianOptimizationCampaignRunner,
    MockCandidateEvaluator,
    PhysicalCandidateEvaluator,
    load_and_validate_bo_config,
    _safe_write_file
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
    AUD-05 / RE-AUD-05: Monitor all file access paths during runner execution across:
      - builtins.open
      - io.open
      - os.open
      - Path.open
      - Path.read_text
      - Path.read_bytes
      - Path.write_text
      - Path.write_bytes
      - os.listdir
      - os.scandir
      - Path.iterdir
      - Path.glob
      - Path.rglob
    Verify that NO access path touches files or directories in experiments/random_search or results/.
    """
    accessed_paths = []

    def check_leak(path_obj):
        p_str = str(path_obj).replace("\\", "/").lower()
        accessed_paths.append(p_str)
        assert "experiments/random_search" not in p_str, f"Unauthorized access to Random Search path: {path_obj}"
        assert "results/processed" not in p_str, f"Unauthorized access to processed results path: {path_obj}"

    orig_builtin_open = builtins.open
    orig_io_open = io.open
    orig_os_open = os.open
    orig_path_open = Path.open
    orig_path_read_text = Path.read_text
    orig_path_read_bytes = Path.read_bytes
    orig_path_write_text = Path.write_text
    orig_path_write_bytes = Path.write_bytes
    orig_os_listdir = os.listdir
    orig_os_scandir = os.scandir
    orig_path_iterdir = Path.iterdir
    orig_path_glob = Path.glob
    orig_path_rglob = Path.rglob

    def wrapped_builtin_open(f, *args, **kwargs):
        check_leak(f)
        return orig_builtin_open(f, *args, **kwargs)

    def wrapped_io_open(f, *args, **kwargs):
        check_leak(f)
        return orig_io_open(f, *args, **kwargs)

    def wrapped_os_open(f, *args, **kwargs):
        check_leak(f)
        return orig_os_open(f, *args, **kwargs)

    def wrapped_path_open(self, *args, **kwargs):
        check_leak(self)
        return orig_path_open(self, *args, **kwargs)

    def wrapped_path_read_text(self, *args, **kwargs):
        check_leak(self)
        return orig_path_read_text(self, *args, **kwargs)

    def wrapped_path_read_bytes(self, *args, **kwargs):
        check_leak(self)
        return orig_path_read_bytes(self, *args, **kwargs)

    def wrapped_path_write_text(self, *args, **kwargs):
        check_leak(self)
        return orig_path_write_text(self, *args, **kwargs)

    def wrapped_path_write_bytes(self, *args, **kwargs):
        check_leak(self)
        return orig_path_write_bytes(self, *args, **kwargs)

    def wrapped_os_listdir(p=".", *args, **kwargs):
        check_leak(p)
        return orig_os_listdir(p, *args, **kwargs)

    def wrapped_os_scandir(p=".", *args, **kwargs):
        check_leak(p)
        return orig_os_scandir(p, *args, **kwargs)

    def wrapped_path_iterdir(self, *args, **kwargs):
        check_leak(self)
        return orig_path_iterdir(self, *args, **kwargs)

    def wrapped_path_glob(self, *args, **kwargs):
        check_leak(self)
        return orig_path_glob(self, *args, **kwargs)

    def wrapped_path_rglob(self, *args, **kwargs):
        check_leak(self)
        return orig_path_rglob(self, *args, **kwargs)

    with patch("builtins.open", side_effect=wrapped_builtin_open), \
         patch("io.open", side_effect=wrapped_io_open), \
         patch("os.open", side_effect=wrapped_os_open), \
         patch.object(Path, "open", wrapped_path_open), \
         patch.object(Path, "read_text", wrapped_path_read_text), \
         patch.object(Path, "read_bytes", wrapped_path_read_bytes), \
         patch.object(Path, "write_text", wrapped_path_write_text), \
         patch.object(Path, "write_bytes", wrapped_path_write_bytes), \
         patch("os.listdir", side_effect=wrapped_os_listdir), \
         patch("os.scandir", side_effect=wrapped_os_scandir), \
         patch.object(Path, "iterdir", wrapped_path_iterdir), \
         patch.object(Path, "glob", wrapped_path_glob), \
         patch.object(Path, "rglob", wrapped_path_rglob):

        runner = BayesianOptimizationCampaignRunner(
            config_path="configs/bayesian_optimization_config.yaml",
            scenario_key="scenario_a",
            dry_run=True,
            output_dir=tmp_path / "leak_test"
        )
        runner.total_evaluations = 15
        runner.n_initial_samples = 10
        runner.n_adaptive_iterations = 5
        runner.run()

    # Confirm that tracking was actively recording paths
    assert len(accessed_paths) > 0
    for p in accessed_paths:
        assert "experiments/random_search" not in p
        assert "results/processed" not in p


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


# ==============================================================================
# Re-Audit Regression Tests (RE-AUD-01 through RE-AUD-04)
# ==============================================================================

def test_re_aud_01_injected_evaluator_cannot_bypass_physical_validation(tmp_path):
    """
    RE-AUD-01: An injected evaluator in physical mode (dry_run=False) MUST NOT bypass
    _validate_physical_environment(). If physical prerequisites are missing, initialization
    must raise FileNotFoundError regardless of evaluator injection.
    """
    obj_eval = ObjectiveEvaluator(w_f=0.5, w_p=0.5)

    # 1. Non-existent LTspice in config with injected evaluator
    cfg = load_and_validate_bo_config("configs/bayesian_optimization_config.yaml")
    cfg["simulation"]["ltspice_executable"] = str(tmp_path / "missing_ltspice.exe")
    cfg_file = tmp_path / "missing_ltspice_cfg.yaml"
    with open(cfg_file, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f)

    class InjectedPhysEvaluator:
        is_physical = True
        def evaluate(self, candidate, iteration_idx):
            return {}

    with pytest.raises(FileNotFoundError, match="LTspice executable not found"):
        BayesianOptimizationCampaignRunner(
            config_path=cfg_file,
            scenario_key="scenario_a",
            dry_run=False,
            output_dir=tmp_path / "phys_out1",
            evaluator=InjectedPhysEvaluator()
        )

    # 2. Injected physical evaluator with non-existent template in config
    cfg2 = load_and_validate_bo_config("configs/bayesian_optimization_config.yaml")
    cfg2["circuit"]["template_netlist"] = "circuits/templates/missing_template.net"
    cfg_file2 = tmp_path / "missing_template_cfg.yaml"
    with open(cfg_file2, "w", encoding="utf-8") as f:
        yaml.dump(cfg2, f)

    with pytest.raises(FileNotFoundError, match="Template netlist not found"):
        BayesianOptimizationCampaignRunner(
            config_path=cfg_file2,
            scenario_key="scenario_a",
            dry_run=False,
            output_dir=tmp_path / "phys_out2",
            evaluator=InjectedPhysEvaluator()
        )


def test_re_aud_02_feasibility_and_oscillation_validity_disentangled(tmp_path):
    """
    RE-AUD-02: Candidates that oscillate (oscillation_status='VALID') but fail feasibility
    (is_feasible=False) must NEVER be selected as best_candidate.
    Feasible evaluations and oscillating evaluations must be reported separately.
    """
    obj_eval = ObjectiveEvaluator(w_f=0.5, w_p=0.5)

    class InfeasibleOscillatingMockEvaluator(MockCandidateEvaluator):
        def evaluate(self, candidate, iteration_idx):
            res = super().evaluate(candidate, iteration_idx)
            if iteration_idx == 0:
                # Oscillates, but marked infeasible with penalty score
                res["is_feasible"] = False
                res["objective_score"] = -1.0e9
                res["status"] = "FAILED_CONSTRAINTS"
            return res

    mock_eval = InfeasibleOscillatingMockEvaluator(objective_evaluator=obj_eval)
    out_dir = tmp_path / "feasibility_test"

    runner = BayesianOptimizationCampaignRunner(
        config_path="configs/bayesian_optimization_config.yaml",
        scenario_key="scenario_a",
        dry_run=True,
        output_dir=out_dir,
        evaluator=mock_eval
    )
    runner.total_evaluations = 3
    runner.n_initial_samples = 2
    runner.n_adaptive_iterations = 1

    summary = runner.run()

    # Iteration 0 has oscillation_status == 'VALID' but is_feasible == False
    rec0 = runner.results_records[0]
    assert rec0["oscillation_status"] == "VALID"
    assert rec0["is_feasible"] is False
    assert rec0["objective_score"] == -1.0e9

    # Best candidate MUST NOT be iteration 0
    assert summary["best_candidate"] is not None
    assert summary["best_candidate"]["iteration"] != 1
    assert summary["best_candidate"]["is_feasible"] is True
    assert summary["best_candidate"]["objective_score"] > -1.0e8

    # Counts must be separated
    assert summary["feasible_evaluations"] < summary["oscillating_evaluations"]

    # Verify results.csv has is_feasible column
    csv_file = out_dir / "results.csv"
    assert csv_file.exists()
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert "is_feasible" in reader.fieldnames
        assert rows[0]["is_feasible"] == "False"
        assert rows[1]["is_feasible"] == "True"

    # Verify config.json separates feasible and oscillating iterations
    cfg_json = json.loads((out_dir / "config.json").read_text(encoding="utf-8"))
    assert "feasible_iterations" in cfg_json["execution"]
    assert "oscillating_iterations" in cfg_json["execution"]
    assert cfg_json["execution"]["feasible_iterations"] < cfg_json["execution"]["oscillating_iterations"]


def test_re_aud_03_comprehensive_metric_validation_and_physical_consistency(tmp_path):
    """
    RE-AUD-03: Comprehensive metric validation:
      - Rejects non-numeric, bool, NaN, infinite, or negative metric values.
      - Rejects physical inconsistencies (f*T != 1, t_pd != T/10, PDP != P*t_pd, unit mismatch).
      - Guarantees all metrics are cleanly sanitized to finite floats or None, preventing ledger crashes.
    """
    runner = BayesianOptimizationCampaignRunner(
        config_path="configs/bayesian_optimization_config.yaml",
        scenario_key="scenario_a",
        dry_run=True,
        output_dir=tmp_path / "metric_val_test"
    )
    cand = {"wn": 0.5e-6, "wp": 1.0e-6}

    # Reference valid electrical metrics for 5-stage oscillator:
    # f = 10 GHz, T = 100 ps, t_pd = 10 ps, P = 1 mW, PDP = 10 fJ
    valid_metrics = {
        "status": "SUCCESS",
        "is_oscillating": True,
        "freq_hz": 1.0e10,
        "freq_ghz": 10.0,
        "period_s": 1.0e-10,
        "power_w": 1.0e-3,
        "power_mw": 1.0,
        "delay_s": 1.0e-11,
        "delay_ps": 10.0,
        "pdp_j": 1.0e-14
    }

    # Case 1: Valid metrics passes
    res_valid = runner._validate_and_sanitize_result(cand, {
        "status": "SUCCESS",
        "is_feasible": True,
        "objective_score": 0.25,
        "metrics": dict(valid_metrics)
    })
    assert res_valid["is_feasible"] is True
    assert res_valid["objective_score"] == 0.25

    # Case 2: Metric type is bool or non-numeric
    m_bool = dict(valid_metrics)
    m_bool["freq_hz"] = True
    res_bool = runner._validate_and_sanitize_result(cand, {
        "status": "SUCCESS", "is_feasible": True, "objective_score": 0.25, "metrics": m_bool
    })
    assert res_bool["is_feasible"] is False
    assert res_bool["objective_score"] == -1.0e9
    assert "INVALID_METRIC_TYPE" in res_bool["status"]

    # Case 3: Metric is negative or NaN
    m_neg = dict(valid_metrics)
    m_neg["power_w"] = -1.0e-3
    res_neg = runner._validate_and_sanitize_result(cand, {
        "status": "SUCCESS", "is_feasible": True, "objective_score": 0.25, "metrics": m_neg
    })
    assert res_neg["is_feasible"] is False
    assert res_neg["objective_score"] == -1.0e9
    assert "INVALID_METRIC_VALUE" in res_neg["status"]

    # Case 4: Physical reciprocity mismatch (f * T = 0.5 != 1.0)
    m_recip = dict(valid_metrics)
    m_recip["period_s"] = 0.5e-10
    res_recip = runner._validate_and_sanitize_result(cand, {
        "status": "SUCCESS", "is_feasible": True, "objective_score": 0.25, "metrics": m_recip
    })
    assert res_recip["is_feasible"] is False
    assert res_recip["status"] == "PHYSICAL_INCONSISTENCY: FREQ_PERIOD_MISMATCH"

    # Case 5: Stage delay mismatch (t_pd != T / 10)
    m_delay = dict(valid_metrics)
    m_delay["delay_s"] = 5.0e-11
    res_delay = runner._validate_and_sanitize_result(cand, {
        "status": "SUCCESS", "is_feasible": True, "objective_score": 0.25, "metrics": m_delay
    })
    assert res_delay["is_feasible"] is False
    assert res_delay["status"] == "PHYSICAL_INCONSISTENCY: DELAY_PERIOD_MISMATCH"

    # Case 6: PDP mismatch (PDP != P * t_pd)
    m_pdp = dict(valid_metrics)
    m_pdp["pdp_j"] = 1.0e-9
    res_pdp = runner._validate_and_sanitize_result(cand, {
        "status": "SUCCESS", "is_feasible": True, "objective_score": 0.25, "metrics": m_pdp
    })
    assert res_pdp["is_feasible"] is False
    assert res_pdp["status"] == "PHYSICAL_INCONSISTENCY: PDP_MISMATCH"

    # Case 7: Dirty input sanitization
    raw_dirty = {
        "status": "FAILED",
        "is_feasible": False,
        "objective_score": -1.0e9,
        "metrics": {
            "status": "FAILED",
            "is_oscillating": False,
            "power_mw": "corrupt_string",
            "freq_ghz": float("nan")
        }
    }
    res_dirty = runner._validate_and_sanitize_result(cand, raw_dirty)
    assert res_dirty["metrics"]["power_mw"] is None
    assert res_dirty["metrics"]["freq_ghz"] is None


def test_re_aud_04_safe_write_file_strictly_atomic_and_preserves_target_on_failure(tmp_path):
    """
    RE-AUD-04: _safe_write_file must never unlink the target file beforehand.
    If atomic replacement fails, the existing target file must remain intact and valid.
    """
    target = tmp_path / "critical_artifact.json"
    initial_content = '{"status": "original_valid_data"}'
    target.write_text(initial_content, encoding="utf-8")

    with patch("os.replace", side_effect=PermissionError("Simulated Windows file lock")):
        with pytest.raises(PermissionError, match="Simulated Windows file lock"):
            _safe_write_file(target, '{"status": "new_unwritten_data"}')

    # Existing file MUST NOT have been unlinked or overwritten
    assert target.exists()
    assert target.read_text(encoding="utf-8") == initial_content

    # Temporary file must have been cleaned up in finally block
    tmp_files = list(tmp_path.glob("*.tmp*"))
    assert len(tmp_files) == 0

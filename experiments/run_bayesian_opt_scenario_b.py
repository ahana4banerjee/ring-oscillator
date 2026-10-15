"""
Scenario B Bayesian Optimization Campaign Runner.

Executes or dry-runs the 50-evaluation Bayesian Optimization campaign for Scenario B:
  - Objective: Frequency-Priority (w_f = 0.7, w_p = 0.3)
  - Search Space: Frozen [0.12, 1.20] µm x [0.24, 2.80] µm on 10 nm grid (28,013 valid points)
  - Budget: 10 LHS space-filling initial evaluations + 40 adaptive BO evaluations = 50 total
  - Random Seed: 3031
  - Model: Gaussian Process Regression with Matérn 5/2 kernel and ARD lengthscales
  - Acquisition: Expected Improvement (xi = 0.01 in standardized objective domain)
  - Duplicate Mitigation: Strict discrete grid exclusion
  - Evaluator Isolation: Explicit mode compatibility check (AUD-01)
  - Atomic Checkpointing: Per-iteration flush, checkpoint state, exception recovery (AUD-02, RE-AUD-04)
  - Output Protection: Overwrite prevention and unique campaign identification (AUD-03)
  - Result Validation: Strict sanity checks before optimizer registration (AUD-07, RE-AUD-03)
  - Configuration Validation: Complete frozen specification verification (AUD-06)
  - Strict Isolation: Operates in dedicated directory (scenario_07_03), isolated from Scenario A and RS

Master Source of Truth: SRS.md (Section 12, 13, 16)
"""

import argparse
import csv
import io
import json
import math
import os
import sys
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union, Set

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.optimization.bayesian import (
    BayesianOptimizer,
    FROZEN_BO_BOUNDS,
    validate_frozen_bounds
)
from src.evaluation.objective import ObjectiveEvaluator
from src.ltspice.parameterizer import NetlistParameterizer
from src.simulation.runner import LTspiceRunner
from src.evaluation.extractor import MetricExtractor


# ==============================================================================
# Configuration Loading & Comprehensive Validation
# ==============================================================================

def load_and_validate_bo_config(
    config_path: Union[str, Path] = "configs/bayesian_optimization_config.yaml",
    scenario_key: str = "scenario_b"
) -> Dict[str, Any]:
    """
    Load and strictly validate the dedicated Bayesian Optimization configuration for Scenario B.
    """
    config_file = Path(config_path)
    if not config_file.is_absolute():
        config_file = PROJECT_ROOT / config_file

    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 1. Validate search space against frozen bounds
    if "search_space" not in config:
        raise ValueError("Missing 'search_space' section in configuration.")
    for k in ["wn_min", "wn_max", "wp_min", "wp_max", "step_size"]:
        if k not in config["search_space"]:
            raise ValueError(f"Missing required search_space key '{k}'.")
        config["search_space"][k] = float(config["search_space"][k])
    validate_frozen_bounds(config["search_space"])

    # 2. Validate circuit specifications
    circ_cfg = config.get("circuit", {})
    if int(circ_cfg.get("stages", 0)) != 5:
        raise ValueError(f"Circuit stages must be exactly 5, got {circ_cfg.get('stages')}")
    if abs(float(circ_cfg.get("vdd", 0.0)) - 1.1) > 1e-12:
        raise ValueError(f"Supply voltage VDD must be 1.1 V, got {circ_cfg.get('vdd')}")
    if abs(float(circ_cfg.get("length", 0.0)) - 0.04e-6) > 1e-12:
        raise ValueError(f"Channel length must be 0.04 µm (40 nm), got {circ_cfg.get('length')}")
    if abs(float(circ_cfg.get("nominal_wn", 0.0)) - 0.5e-6) > 1e-12:
        raise ValueError(f"Nominal Wn must be 0.5 µm, got {circ_cfg.get('nominal_wn')}")
    if abs(float(circ_cfg.get("nominal_wp", 0.0)) - 1.0e-6) > 1e-12:
        raise ValueError(f"Nominal Wp must be 1.0 µm, got {circ_cfg.get('nominal_wp')}")

    template_rel = circ_cfg.get("template_netlist", "")
    if not template_rel:
        raise ValueError("Missing 'template_netlist' path in circuit configuration.")
    template_path = PROJECT_ROOT / template_rel
    if not template_path.exists():
        raise FileNotFoundError(f"Template netlist not found at: {template_path}")

    # 3. Validate simulation specifications
    sim_cfg = config.get("simulation", {})
    if sim_cfg.get("transient_stop") != "1n":
        raise ValueError(f"Simulation transient_stop must be '1n', got {sim_cfg.get('transient_stop')}")
    if sim_cfg.get("transient_start_save") != "0.2n":
        raise ValueError(f"Simulation transient_start_save must be '0.2n', got {sim_cfg.get('transient_start_save')}")
    if sim_cfg.get("max_step") != "0.01p":
        raise ValueError(f"Simulation max_step must be '0.01p', got {sim_cfg.get('max_step')}")
    if float(sim_cfg.get("timeout_seconds", 0.0)) <= 0:
        raise ValueError(f"Simulation timeout_seconds must be positive, got {sim_cfg.get('timeout_seconds')}")

    # 4. Validate optimization parameters
    opt_cfg = config.get("optimization", {})
    if opt_cfg.get("method") != "bayesian":
        raise ValueError(f"Expected optimization method 'bayesian', got '{opt_cfg.get('method')}'")
    if opt_cfg.get("surrogate") != "gp_matern52":
        raise ValueError(f"Expected surrogate 'gp_matern52', got '{opt_cfg.get('surrogate')}'")
    if opt_cfg.get("kernel") != "matern52_ard":
        raise ValueError(f"Expected kernel 'matern52_ard', got '{opt_cfg.get('kernel')}'")
    if abs(float(opt_cfg.get("nugget", 0.0)) - 1.0e-6) > 1e-12:
        raise ValueError(f"Expected nugget 1.0e-6, got {opt_cfg.get('nugget')}")
    if opt_cfg.get("acquisition") != "expected_improvement":
        raise ValueError(f"Expected acquisition 'expected_improvement', got '{opt_cfg.get('acquisition')}'")
    if abs(float(opt_cfg.get("xi", 0.0)) - 0.01) > 1e-12:
        raise ValueError(f"Expected xi 0.01, got {opt_cfg.get('xi')}")
    if abs(float(opt_cfg.get("penalty_value", 0.0)) - (-1.0e9)) > 1e-3:
        raise ValueError(f"Expected penalty_value -1.0e9, got {opt_cfg.get('penalty_value')}")

    # 5. Validate budget partitioning
    total_evals = int(opt_cfg.get("total_evaluations", 0))
    n_init = int(opt_cfg.get("n_initial_samples", 0))
    n_adaptive = int(opt_cfg.get("n_adaptive_iterations", 0))

    if total_evals != 50:
        raise ValueError(f"Total evaluation budget must be exactly 50, got {total_evals}")
    if n_init != 10:
        raise ValueError(f"Initial LHS design must be exactly 10, got {n_init}")
    if n_adaptive != 40:
        raise ValueError(f"Adaptive BO phase must be exactly 40, got {n_adaptive}")
    if n_init + n_adaptive != total_evals:
        raise ValueError(f"Sum of initial ({n_init}) and adaptive ({n_adaptive}) must equal total ({total_evals})")

    # 6. Validate Scenario B specifics
    scenarios = opt_cfg.get("scenarios", {})
    if scenario_key not in scenarios:
        raise ValueError(f"Target scenario '{scenario_key}' not defined in configuration.")

    sc_cfg = scenarios[scenario_key]
    if scenario_key == "scenario_b":
        if sc_cfg.get("name") != "frequency_priority":
            raise ValueError(f"Scenario B name must be 'frequency_priority', got '{sc_cfg.get('name')}'")
        if abs(float(sc_cfg.get("w_f", 0.0)) - 0.7) > 1e-12 or abs(float(sc_cfg.get("w_p", 0.0)) - 0.3) > 1e-12:
            raise ValueError(f"Scenario B requires w_f=0.7 and w_p=0.3, got w_f={sc_cfg.get('w_f')}, w_p={sc_cfg.get('w_p')}")

        seeds = opt_cfg.get("seeds", {})
        seed_b = int(seeds.get("scenario_b", 0))
        if seed_b != 3031:
            raise ValueError(f"Scenario B deterministic seed must be 3031, got {seed_b}")

    # 7. Validate normalization baselines
    norm_cfg = config.get("normalization", {})
    f0 = float(norm_cfg.get("baseline_frequency_hz", 0.0))
    p0 = float(norm_cfg.get("baseline_power_w", 0.0))
    if abs(f0 - 41069756649.1) > 1.0:
        raise ValueError(f"Baseline frequency must be 41.0697566491 GHz, got {f0} Hz")
    if abs(p0 - 0.000140169553568) > 1e-12:
        raise ValueError(f"Baseline power must be 140.169553568 µW, got {p0} W")

    return config


# ==============================================================================
# Evaluator Interfaces
# ==============================================================================

class BaseCandidateEvaluator(ABC):
    """Abstract interface for candidate sizing evaluation."""

    @property
    @abstractmethod
    def is_physical(self) -> bool:
        pass

    @abstractmethod
    def evaluate(self, candidate: Dict[str, float], iteration_idx: int) -> Dict[str, Any]:
        pass


class MockCandidateEvaluator(BaseCandidateEvaluator):
    """Mock Candidate Evaluator for Dry-Run and Automated Testing."""

    @property
    def is_physical(self) -> bool:
        return False

    def __init__(
        self,
        objective_evaluator: ObjectiveEvaluator,
        seed: int = 3031,
        fail_extreme_ratios: bool = True
    ):
        self.objective_evaluator = objective_evaluator
        self.seed = seed
        self.fail_extreme_ratios = fail_extreme_ratios
        self.call_count = 0

    def evaluate(self, candidate: Dict[str, float], iteration_idx: int) -> Dict[str, Any]:
        self.call_count += 1
        wn = candidate["wn"]
        wp = candidate["wp"]
        ratio = wp / wn

        if self.fail_extreme_ratios and (ratio > 18.0 or ratio < 0.25):
            metrics = {
                "status": "NO_OSCILLATION",
                "is_oscillating": False,
                "freq_hz": None,
                "freq_ghz": None,
                "period_s": None,
                "power_w": None,
                "power_mw": None,
                "delay_s": None,
                "delay_ps": None,
                "pdp_j": None
            }
        else:
            wn_um = wn * 1e6
            wp_um = wp * 1e6
            
            drive_eff = (wn_um * wp_um) / (wn_um + 0.5 * wp_um + 0.1)
            cap_eff = 0.5 + 0.8 * (wn_um + wp_um)
            freq_ghz = 25.0 + 35.0 * (drive_eff / cap_eff)
            freq_hz = freq_ghz * 1e9

            period_s = 1.0 / freq_hz
            delay_ps = (period_s / 10.0) * 1e12

            power_uw = 40.0 + (cap_eff * 1.5) * (freq_ghz / 40.0) * (1.1 ** 2) * 20.0
            power_w = power_uw * 1e-6
            power_mw = power_uw / 1000.0

            pdp_j = power_w * (delay_ps * 1e-12)

            metrics = {
                "status": "SUCCESS",
                "is_oscillating": True,
                "freq_hz": freq_hz,
                "freq_ghz": freq_ghz,
                "period_s": period_s,
                "power_w": power_w,
                "power_mw": power_mw,
                "delay_s": delay_ps * 1e-12,
                "delay_ps": delay_ps,
                "pdp_j": pdp_j
            }

        score, is_feasible, breakdown = self.objective_evaluator.evaluate(metrics)

        return {
            "status": metrics["status"],
            "is_feasible": is_feasible,
            "objective_score": score,
            "metrics": metrics,
            "breakdown": breakdown,
            "sim_time_sec": 0.001,
            "is_synthetic": True
        }


class PhysicalCandidateEvaluator(BaseCandidateEvaluator):
    """Physical Candidate Evaluator for Live LTspice Execution."""

    @property
    def is_physical(self) -> bool:
        return True

    def __init__(
        self,
        template_netlist_path: Path,
        ltspice_executable: Path,
        work_dir: Path,
        objective_evaluator: ObjectiveEvaluator,
        timeout_seconds: float = 30.0,
        num_stages: int = 5
    ):
        self.parameterizer = NetlistParameterizer(template_netlist_path)
        self.runner = LTspiceRunner(executable_path=str(ltspice_executable), timeout_seconds=timeout_seconds)
        self.extractor = MetricExtractor(stages=num_stages)
        self.objective_evaluator = objective_evaluator
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.call_count = 0

    def evaluate(self, candidate: Dict[str, float], iteration_idx: int) -> Dict[str, Any]:
        self.call_count += 1
        iter_str = f"iter_{iteration_idx:04d}"
        netlist_path = self.work_dir / f"run_{iter_str}.net"

        # 1. Parameter injection
        params = {"Wn": candidate["wn"], "Wp": candidate["wp"]}
        self.parameterizer.generate_netlist(params, netlist_path)

        # 2. Simulation execution
        sim_res = self.runner.run(netlist_path)

        # 3. Measurement extraction
        metrics = self.extractor.extract(sim_res)

        # 4. Scalar objective calculation
        score, is_feasible, breakdown = self.objective_evaluator.evaluate(metrics)

        return {
            "status": metrics.get("status", "FAILED"),
            "is_feasible": is_feasible,
            "objective_score": score,
            "metrics": metrics,
            "breakdown": breakdown,
            "sim_time_sec": sim_res.elapsed_time,
            "is_synthetic": False
        }


def _safe_write_file(target_path: Path, content: str) -> None:
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_name(f"{target_path.name}.tmp_{os.getpid()}_{uuid.uuid4().hex[:8]}")

    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        max_retries = 5
        last_error = None
        for attempt in range(max_retries):
            try:
                os.replace(tmp_path, target_path)
                last_error = None
                break
            except OSError as e:
                last_error = e
                time.sleep(0.05 * (attempt + 1))

        if last_error is not None:
            raise last_error
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


# ==============================================================================
# Bayesian Optimization Campaign Runner (Scenario B)
# ==============================================================================

class BayesianOptimizationCampaignRunner:
    """Coordinates execution of Bayesian Optimization Campaign (Scenario B / Frequency Priority)."""

    def __init__(
        self,
        config_path: Union[str, Path] = "configs/bayesian_optimization_config.yaml",
        scenario_key: str = "scenario_b",
        dry_run: bool = True,
        output_dir: Optional[Union[str, Path]] = None,
        evaluator: Optional[BaseCandidateEvaluator] = None,
        overwrite: bool = False
    ):
        self.dry_run = dry_run
        self.scenario_key = scenario_key
        self.overwrite = overwrite

        # 1. Load and strictly validate configuration
        self.config = load_and_validate_bo_config(config_path, scenario_key=scenario_key)
        self.search_space = self.config["search_space"]
        self.opt_cfg = self.config["optimization"]
        self.scenario_cfg = self.opt_cfg["scenarios"][self.scenario_key]

        self.seed = int(self.opt_cfg["seeds"][self.scenario_key])
        self.total_evaluations = int(self.opt_cfg["total_evaluations"])
        self.n_initial_samples = int(self.opt_cfg["n_initial_samples"])
        self.n_adaptive_iterations = int(self.opt_cfg["n_adaptive_iterations"])
        self.w_f = float(self.scenario_cfg["w_f"])
        self.w_p = float(self.scenario_cfg["w_p"])
        self.penalty_value = float(self.opt_cfg["penalty_value"])

        # 2. Configure Objective Evaluator (Scenario B: w_f=0.7, w_p=0.3)
        norm_cfg = self.config["normalization"]
        self.objective_evaluator = ObjectiveEvaluator(
            baseline_freq_hz=float(norm_cfg["baseline_frequency_hz"]),
            baseline_power_w=float(norm_cfg["baseline_power_w"]),
            w_f=self.w_f,
            w_p=self.w_p,
            objective_mode="weighted",
            penalty_value=self.penalty_value
        )

        # 3. Configure Bayesian Optimizer
        self.optimizer = BayesianOptimizer(
            search_space=self.search_space,
            seed=self.seed,
            n_initial_samples=self.n_initial_samples,
            xi=float(self.opt_cfg["xi"]),
            nugget=float(self.opt_cfg["nugget"]),
            enforce_frozen_bounds=True
        )

        # 4. Resolve Output Directory & Overwrite Protection
        if output_dir is not None:
            self.output_dir = Path(output_dir)
        else:
            base_dir = PROJECT_ROOT / self.config["logging"]["scenario_b_dir"]
            self.output_dir = base_dir / "dry_run" if self.dry_run else base_dir

        self._check_output_directory_safeguards()

        self.plots_dir = self.output_dir / "plots"
        self.raw_dir = self.output_dir / "raw_results"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.plots_dir.mkdir(parents=True, exist_ok=True)
        if not self.dry_run:
            self.raw_dir.mkdir(parents=True, exist_ok=True)

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        mode_tag = "dry_run" if self.dry_run else "physical"
        self.campaign_id = f"bo_scenario_b_{self.seed}_{mode_tag}_{timestamp_str}"

        # 5. Configure & Validate Candidate Evaluator Compatibility
        if not self.dry_run:
            self._validate_physical_environment()

        if evaluator is not None:
            is_phys = getattr(evaluator, "is_physical", False) or isinstance(evaluator, PhysicalCandidateEvaluator)
            if self.dry_run and is_phys:
                raise ValueError("Security violation: Physical evaluator injected into dry-run mode.")
            if not self.dry_run and not is_phys:
                raise ValueError("Configuration error: Mock/synthetic evaluator injected into physical campaign mode.")
            self.evaluator = evaluator
        elif self.dry_run:
            self.evaluator = MockCandidateEvaluator(
                objective_evaluator=self.objective_evaluator,
                seed=self.seed,
                fail_extreme_ratios=True
            )
        else:
            sim_cfg = self.config["simulation"]
            circ_cfg = self.config["circuit"]
            template_path = PROJECT_ROOT / circ_cfg["template_netlist"]
            ltspice_exe = Path(sim_cfg["ltspice_executable"])

            self.evaluator = PhysicalCandidateEvaluator(
                template_netlist_path=template_path,
                ltspice_executable=ltspice_exe,
                work_dir=self.raw_dir,
                objective_evaluator=self.objective_evaluator,
                timeout_seconds=float(sim_cfg.get("timeout_seconds", 30.0)),
                num_stages=int(circ_cfg.get("stages", 5))
            )

        self.results_records: List[Dict[str, Any]] = []
        self.evaluated_candidates: Set[Tuple[float, float]] = set()
        self.best_candidate: Optional[Dict[str, Any]] = None

    def _check_output_directory_safeguards(self) -> None:
        critical_artifacts = [
            self.output_dir / "results.csv",
            self.output_dir / "config.json",
            self.output_dir / "summary.md",
            self.output_dir / "checkpoint.json"
        ]
        if not self.overwrite and any(p.exists() for p in critical_artifacts):
            existing_files = [p.name for p in critical_artifacts if p.exists()]
            raise FileExistsError(
                f"Output directory '{self.output_dir}' already contains campaign artifacts: {existing_files}. "
                "Refusing to overwrite without explicit overwrite=True (or --overwrite flag)."
            )

    def _validate_physical_environment(self) -> None:
        sim_cfg = self.config.get("simulation", {})
        circ_cfg = self.config.get("circuit", {})

        template_path = PROJECT_ROOT / circ_cfg.get("template_netlist", "")
        if not template_path.exists():
            raise FileNotFoundError(f"Template netlist not found: {template_path}")

        ltspice_exe = Path(sim_cfg.get("ltspice_executable", ""))
        if not ltspice_exe.exists():
            raise FileNotFoundError(f"LTspice executable not found: {ltspice_exe}")

        models_dir = PROJECT_ROOT / circ_cfg.get("models_path", "")
        if not models_dir.exists():
            raise FileNotFoundError(f"Transistor models directory not found: {models_dir}")

    def _validate_and_sanitize_result(
        self,
        candidate: Dict[str, float],
        raw_result: Any
    ) -> Dict[str, Any]:
        if not isinstance(raw_result, dict):
            return {
                "status": "MALFORMED_OUTPUT",
                "is_feasible": False,
                "objective_score": self.penalty_value,
                "metrics": {},
                "sim_time_sec": 0.0,
                "is_synthetic": self.dry_run
            }

        status = str(raw_result.get("status", "FAILED"))
        is_feasible = bool(raw_result.get("is_feasible", False))
        score_val = raw_result.get("objective_score")

        try:
            score = float(score_val)
            if math.isnan(score) or math.isinf(score):
                score = self.penalty_value
                is_feasible = False
        except (TypeError, ValueError):
            score = self.penalty_value
            is_feasible = False

        metrics = raw_result.get("metrics", {})
        if not isinstance(metrics, dict):
            metrics = {}

        if is_feasible:
            if status != "SUCCESS":
                is_feasible = False
                score = self.penalty_value
            elif not metrics.get("is_oscillating", False):
                is_feasible = False
                score = self.penalty_value
            else:
                critical_keys = ["freq_hz", "freq_ghz", "period_s", "power_w", "power_mw", "delay_s", "delay_ps", "pdp_j"]
                for k in critical_keys:
                    val = metrics.get(k)
                    if val is None or isinstance(val, bool) or not isinstance(val, (int, float)):
                        is_feasible = False
                        score = self.penalty_value
                        status = "INVALID_METRICS_TYPE"
                        break
                    val_f = float(val)
                    if math.isnan(val_f) or math.isinf(val_f) or val_f <= 0.0:
                        is_feasible = False
                        score = self.penalty_value
                        status = "NON_POSITIVE_METRICS"
                        break

        # Consistency checks
        if is_feasible:
            try:
                f_hz = float(metrics["freq_hz"])
                t_per = float(metrics["period_s"])
                f_ghz = float(metrics["freq_ghz"])
                p_w = float(metrics["power_w"])
                p_mw = float(metrics["power_mw"])
                t_pd = float(metrics["delay_s"])
                t_pd_ps = float(metrics["delay_ps"])
                pdp = float(metrics["pdp_j"])

                if abs(f_hz * t_per - 1.0) > 1e-2:
                    is_feasible = False
                    score = self.penalty_value
                    status = "RECIPROCITY_VIOLATION"
                elif abs(f_ghz - f_hz * 1e-9) / f_ghz > 1e-2:
                    is_feasible = False
                    score = self.penalty_value
                    status = "FREQ_UNIT_MISMATCH"
                elif abs(p_mw - p_w * 1e3) / p_mw > 1e-2:
                    is_feasible = False
                    score = self.penalty_value
                    status = "POWER_UNIT_MISMATCH"
                elif abs(t_pd - t_per / 10.0) / t_pd > 1e-2:
                    is_feasible = False
                    score = self.penalty_value
                    status = "DELAY_PERIOD_INCONSISTENCY"
                elif abs(t_pd_ps - t_pd * 1e12) / t_pd_ps > 1e-2:
                    is_feasible = False
                    score = self.penalty_value
                    status = "DELAY_UNIT_MISMATCH"
                elif abs(pdp - p_w * t_pd) / pdp > 1e-2:
                    is_feasible = False
                    score = self.penalty_value
                    status = "PDP_INCONSISTENCY"
            except Exception:
                is_feasible = False
                score = self.penalty_value
                status = "CONSISTENCY_CHECK_FAILED"

        def _clean_float(v: Any) -> Optional[float]:
            if v is None:
                return None
            try:
                f = float(v)
                return f if math.isfinite(f) else None
            except (TypeError, ValueError):
                return None

        clean_metrics = {
            "status": status,
            "is_oscillating": bool(metrics.get("is_oscillating", False)),
            "freq_hz": _clean_float(metrics.get("freq_hz")),
            "freq_ghz": _clean_float(metrics.get("freq_ghz")),
            "period_s": _clean_float(metrics.get("period_s")),
            "power_w": _clean_float(metrics.get("power_w")),
            "power_mw": _clean_float(metrics.get("power_mw")),
            "delay_s": _clean_float(metrics.get("delay_s")),
            "delay_ps": _clean_float(metrics.get("delay_ps")),
            "pdp_j": _clean_float(metrics.get("pdp_j"))
        }

        return {
            "status": status,
            "is_feasible": is_feasible,
            "objective_score": score,
            "metrics": clean_metrics,
            "sim_time_sec": float(raw_result.get("sim_time_sec", 0.0)),
            "is_synthetic": bool(raw_result.get("is_synthetic", self.dry_run))
        }

    def _flush_results_ledger(self) -> None:
        csv_path = self.output_dir / "results.csv"
        headers = [
            "iteration", "phase", "seed", "Wn", "Wp", "ratio",
            "frequency", "average_power", "period", "delay", "PDP",
            "objective", "is_feasible", "simulation_status", "oscillation_status",
            "runtime", "Wn_um", "Wp_um", "Wp_Wn_ratio",
            "frequency_ghz", "average_power_uw", "period_ps", "delay_ps",
            "pdp_fj", "objective_score", "runtime_sec", "is_synthetic"
        ]

        csv_rows = []
        for r in self.results_records:
            m = r.get("metrics", {})
            f_ghz = m.get("freq_ghz")
            p_w = m.get("power_w")
            p_uw = (p_w * 1e6) if p_w is not None else None
            per_ps = (m["period_s"] * 1e12) if m.get("period_s") is not None else None
            del_ps = m.get("delay_ps")
            pdp_fj = (m["pdp_j"] * 1e15) if m.get("pdp_j") is not None else None

            csv_rows.append({
                "iteration": r["iteration"],
                "phase": r["phase"],
                "seed": self.seed,
                "Wn": round(r["Wn_um"], 4),
                "Wp": round(r["Wp_um"], 4),
                "ratio": round(r["ratio"], 4),
                "frequency": round(f_ghz, 6) if f_ghz is not None else "",
                "average_power": round(p_uw, 3) if p_uw is not None else "",
                "period": round(per_ps, 4) if per_ps is not None else "",
                "delay": round(del_ps, 4) if del_ps is not None else "",
                "PDP": round(pdp_fj, 6) if pdp_fj is not None else "",
                "objective": round(r["objective_score"], 6),
                "is_feasible": r["is_feasible"],
                "simulation_status": r["status"],
                "oscillation_status": "VALID" if m.get("is_oscillating", False) else "NO_OSCILLATION",
                "runtime": round(r["sim_time_sec"], 3),
                "Wn_um": round(r["Wn_um"], 4),
                "Wp_um": round(r["Wp_um"], 4),
                "Wp_Wn_ratio": round(r["ratio"], 4),
                "frequency_ghz": round(f_ghz, 6) if f_ghz is not None else "",
                "average_power_uw": round(p_uw, 3) if p_uw is not None else "",
                "period_ps": round(per_ps, 4) if per_ps is not None else "",
                "delay_ps": round(del_ps, 4) if del_ps is not None else "",
                "pdp_fj": round(pdp_fj, 6) if pdp_fj is not None else "",
                "objective_score": round(r["objective_score"], 6),
                "runtime_sec": round(r["sim_time_sec"], 3),
                "is_synthetic": r.get("is_synthetic", self.dry_run)
            })

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(csv_rows)
        _safe_write_file(csv_path, output.getvalue())

    def _flush_checkpoint(self, current_candidate: Dict[str, float]) -> None:
        ckpt_path = self.output_dir / "checkpoint.json"
        ckpt_data = {
            "campaign_id": self.campaign_id,
            "completed_evaluations": len(self.results_records),
            "total_budget": self.total_evaluations,
            "is_dry_run": self.dry_run,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "best_candidate": self.best_candidate,
            "last_candidate": current_candidate
        }
        _safe_write_file(ckpt_path, json.dumps(ckpt_data, indent=2))

    def run(self) -> Dict[str, Any]:
        """Execute the 50-evaluation Bayesian Optimization Campaign B."""
        mode_str = "DRY-RUN / SYNTHETIC" if self.dry_run else "PHYSICAL SIMULATION"
        print("=" * 80)
        print(f"STARTING BAYESIAN OPTIMIZATION CAMPAIGN – SCENARIO B ({mode_str})")
        print(f"  Campaign ID: {self.campaign_id}")
        print(f"  Objective: Frequency-Priority (w_f = {self.w_f}, w_p = {self.w_p})")
        print(f"  Frozen Search Space: Wn in [0.12, 1.20] µm | Wp in [0.24, 2.80] µm")
        print(f"  Grid Resolution: 10.0 nm (28,013 valid points)")
        print(f"  Deterministic Seed: {self.seed}")
        print(f"  Evaluation Budget: {self.total_evaluations} total ({self.n_initial_samples} LHS + {self.n_adaptive_iterations} adaptive)")
        print(f"  Output Directory: {self.output_dir}")
        print("=" * 80)

        t_campaign_start = time.time()
        consecutive_evaluator_crashes = 0
        max_consecutive_crashes = 3

        for eval_idx in range(self.total_evaluations):
            candidate = self.optimizer.suggest()
            wn = candidate["wn"]
            wp = candidate["wp"]
            wn_um = wn * 1e6
            wp_um = wp * 1e6
            ratio = wp / wn

            phase_label = "LHS" if eval_idx < self.n_initial_samples else "ADAPTIVE_BO"

            try:
                raw_eval = self.evaluator.evaluate(candidate, eval_idx)
                consecutive_evaluator_crashes = 0
            except Exception as e:
                consecutive_evaluator_crashes += 1
                raw_eval = {
                    "status": f"EVALUATOR_EXCEPTION: {type(e).__name__}",
                    "is_feasible": False,
                    "objective_score": self.penalty_value,
                    "metrics": {"status": "CRASH", "is_oscillating": False},
                    "sim_time_sec": 0.0,
                    "is_synthetic": self.dry_run
                }
                if consecutive_evaluator_crashes >= max_consecutive_crashes:
                    self._flush_results_ledger()
                    self._flush_checkpoint(candidate)
                    raise RuntimeError(
                        f"Campaign aborted after {consecutive_evaluator_crashes} consecutive evaluator crashes. "
                        f"State preserved in {self.output_dir}."
                    ) from e

            sanitized = self._validate_and_sanitize_result(candidate, raw_eval)

            try:
                self.optimizer.register(candidate, sanitized)
            except Exception as e:
                self._flush_results_ledger()
                self._flush_checkpoint(candidate)
                raise RuntimeError(
                    f"Optimizer registration failed at iteration {eval_idx + 1}. State preserved."
                ) from e

            record = {
                "iteration": eval_idx + 1,
                "phase": phase_label,
                "Wn_um": wn_um,
                "Wp_um": wp_um,
                "ratio": ratio,
                "objective_score": sanitized["objective_score"],
                "is_feasible": sanitized["is_feasible"],
                "status": sanitized["status"],
                "sim_time_sec": sanitized["sim_time_sec"],
                "is_synthetic": sanitized["is_synthetic"],
                "metrics": sanitized["metrics"]
            }
            self.results_records.append(record)
            self.evaluated_candidates.add((round(wn, 9), round(wp, 9)))

            if sanitized["is_feasible"]:
                if self.best_candidate is None or sanitized["objective_score"] > self.best_candidate["objective_score"]:
                    m = sanitized["metrics"]
                    self.best_candidate = {
                        "iteration": eval_idx + 1,
                        "phase": phase_label,
                        "seed": self.seed,
                        "Wn": round(wn_um, 4),
                        "Wp": round(wp_um, 4),
                        "ratio": round(ratio, 4),
                        "frequency": round(m["freq_ghz"], 6) if m.get("freq_ghz") else None,
                        "average_power": round(m["power_w"] * 1e6, 3) if m.get("power_w") else None,
                        "period": round(m["period_s"] * 1e12, 4) if m.get("period_s") else None,
                        "delay": round(m["delay_ps"], 4) if m.get("delay_ps") else None,
                        "PDP": round(m["pdp_j"] * 1e15, 6) if m.get("pdp_j") else None,
                        "objective": round(sanitized["objective_score"], 6),
                        "is_feasible": True,
                        "simulation_status": sanitized["status"],
                        "oscillation_status": "VALID" if m.get("is_oscillating") else "NO_OSCILLATION",
                        "runtime": round(sanitized["sim_time_sec"], 3),
                        "Wn_um": round(wn_um, 4),
                        "Wp_um": round(wp_um, 4),
                        "Wp_Wn_ratio": round(ratio, 4),
                        "frequency_ghz": round(m["freq_ghz"], 6) if m.get("freq_ghz") else None,
                        "average_power_uw": round(m["power_w"] * 1e6, 3) if m.get("power_w") else None,
                        "period_ps": round(m["period_s"] * 1e12, 4) if m.get("period_s") else None,
                        "delay_ps": round(m["delay_ps"], 4) if m.get("delay_ps") else None,
                        "pdp_fj": round(m["pdp_j"] * 1e15, 6) if m.get("pdp_j") else None,
                        "objective_score": round(sanitized["objective_score"], 6),
                        "runtime_sec": round(sanitized["sim_time_sec"], 3),
                        "is_synthetic": sanitized["is_synthetic"]
                    }

            self._flush_results_ledger()
            self._flush_checkpoint(candidate)

            m_log = sanitized["metrics"]
            f_str = f"{m_log['freq_ghz']:.3f} GHz" if m_log.get("freq_ghz") is not None else "N/A"
            p_str = f"{m_log['power_w']*1e6:.1f} µW" if m_log.get("power_w") is not None else "N/A"
            status_str = "VALID" if m_log.get("is_oscillating") else sanitized["status"]
            print(
                f"[{phase_label:<11}] Iter {eval_idx + 1:02d}/{self.total_evaluations} | "
                f"Wn={wn_um:.2f}µm, Wp={wp_um:.2f}µm (Ratio={ratio:.2f}) | "
                f"Status={status_str} | Freq={f_str} | Power={p_str} | "
                f"F={sanitized['objective_score']:.4f}"
            )

        duration = time.time() - t_campaign_start
        print(f"\nCampaign execution phase ended in {duration:.2f} seconds.")

        self._write_campaign_artifacts(duration)

        return {
            "campaign_id": self.campaign_id,
            "total_evaluations": len(self.results_records),
            "feasible_evaluations": sum(1 for r in self.results_records if r["is_feasible"]),
            "best_candidate": self.best_candidate,
            "duration_sec": duration,
            "output_dir": str(self.output_dir)
        }

    def _write_campaign_artifacts(self, duration: float) -> None:
        cfg_out = {
            "campaign_id": self.campaign_id,
            "campaign_name": "bayesian_optimization_scenario_b",
            "scenario": "scenario_b_frequency_priority_07_03",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_dry_run": self.dry_run,
            "is_synthetic_data": self.dry_run,
            "seed": self.seed,
            "total_evaluations": self.total_evaluations,
            "n_initial_samples_lhs": self.n_initial_samples,
            "n_adaptive_iterations_bo": self.n_adaptive_iterations,
            "search_space": {
                "wn_min_um": round(self.search_space["wn_min"] * 1e6, 4),
                "wn_max_um": round(self.search_space["wn_max"] * 1e6, 4),
                "wp_min_um": round(self.search_space["wp_min"] * 1e6, 4),
                "wp_max_um": round(self.search_space["wp_max"] * 1e6, 4),
                "step_size_nm": round(self.search_space["step_size"] * 1e9, 2),
                "discrete_candidates_total": 28013
            },
            "objective": {
                "mode": "weighted",
                "w_f": self.w_f,
                "w_p": self.w_p,
                "penalty_value": self.penalty_value
            },
            "surrogate": {
                "model": "GaussianProcessMatern52",
                "kernel": "matern52_ard",
                "nugget": float(self.opt_cfg["nugget"]),
                "acquisition": "expected_improvement",
                "xi_standardized_domain": float(self.opt_cfg["xi"])
            },
            "execution": {
                "duration_sec": round(duration, 3),
                "completed_iterations": len(self.results_records),
                "feasible_iterations": sum(1 for r in self.results_records if r["is_feasible"]),
                "oscillating_iterations": sum(1 for r in self.results_records if r.get("metrics", {}).get("is_oscillating", False))
            }
        }

        cfg_final = self.output_dir / "config.json"
        _safe_write_file(cfg_final, json.dumps(cfg_out, indent=2))

        # Markdown Summary
        best_cand = self.best_candidate
        mode_str = "SYNTHETIC DRY-RUN (MOCK EVALUATOR)" if self.dry_run else "PHYSICAL LTSPICE EXECUTION"
        summary_md = f"""# Bayesian Optimization Campaign B Summary (Scenario B: Frequency-Priority 0.7/0.3)

- **Campaign ID:** `{self.campaign_id}`
- **Campaign Mode:** {mode_str}
- **Total Evaluations:** {len(self.results_records)} / {self.total_evaluations}
- **Initial LHS Design:** {self.n_initial_samples} evaluations
- **Adaptive BO Iterations:** {self.n_adaptive_iterations} evaluations
- **Feasible Evaluations:** {sum(1 for r in self.results_records if r['is_feasible'])} / {self.total_evaluations} ({sum(1 for r in self.results_records if r['is_feasible'])/self.total_evaluations*100:.1f}%)
- **Deterministic Seed:** {self.seed}
- **Total Duration:** {duration:.2f} s
- **Acquisition Policy:** Expected Improvement (xi = 0.01 in standardized objective domain)
- **Search Space:** Wn in [0.12, 1.20] µm, Wp in [0.24, 2.80] µm (10 nm grid, 28,013 valid points)

## Best Feasible Candidate
"""
        if best_cand is not None:
            summary_md += f"""- **Iteration:** {best_cand['iteration']} ({best_cand['phase']})
- **Transistor Sizing:** Wn = {best_cand['Wn_um']:.4f} µm, Wp = {best_cand['Wp_um']:.4f} µm (Ratio = {best_cand['Wp_Wn_ratio']:.4f})
- **Objective Score F:** {best_cand['objective_score']:.6f}
- **Oscillation Frequency:** {best_cand['frequency_ghz']:.6f} GHz
- **Average Power:** {best_cand['average_power_uw']:.3f} µW
- **Stage Propagation Delay:** {best_cand['delay_ps']:.4f} ps
- **Power-Delay Product:** {best_cand['pdp_fj']:.6f} fJ
"""
        else:
            summary_md += "- No feasible candidates identified.\n"

        sum_final = self.output_dir / "summary.md"
        _safe_write_file(sum_final, summary_md)

        print(f"Artifacts successfully written to: {self.output_dir}")


# ==============================================================================
# CLI Entrypoint
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Run Bayesian Optimization Campaign B for CMOS Ring Oscillator."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Execute in safe dry-run mode using synthetic mock evaluator (default: True)."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/bayesian_optimization_config.yaml",
        help="Path to dedicated Bayesian Optimization configuration YAML."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Optional custom output directory."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Explicitly permit overwriting an existing campaign directory."
    )
    parser.add_argument(
        "--execute-physical-campaign",
        action="store_true",
        default=False,
        help="Explicit physical execution pathway flag. Locked until authorized."
    )

    args = parser.parse_args()

    if args.execute_physical_campaign:
        if os.environ.get("AUTHORIZE_PHYSICAL_CAMPAIGN_B") != "1":
            print("=" * 80)
            print("SAFETY INTERLOCK: PHYSICAL CAMPAIGN EXECUTION IS CURRENTLY LOCKED.")
            print("To unlock physical execution once approved by the user, set AUTHORIZE_PHYSICAL_CAMPAIGN_B=1.")
            print("=" * 80)
            sys.exit(1)

        runner = BayesianOptimizationCampaignRunner(
            config_path=args.config,
            scenario_key="scenario_b",
            dry_run=False,
            output_dir=args.output_dir,
            overwrite=args.overwrite
        )
    else:
        runner = BayesianOptimizationCampaignRunner(
            config_path=args.config,
            scenario_key="scenario_b",
            dry_run=True,
            output_dir=args.output_dir,
            overwrite=args.overwrite
        )

    summary = runner.run()
    print("\nCAMPAIGN RUN COMPLETE.")
    print(f"Campaign ID: {summary['campaign_id']}")
    print(f"Evaluations: {summary['total_evaluations']} | Feasible: {summary['feasible_evaluations']}")


if __name__ == "__main__":
    main()

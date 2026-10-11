"""
Scenario A Bayesian Optimization Campaign Runner (Step 6.2.1).

Executes or dry-runs the 50-evaluation Bayesian Optimization campaign for Scenario A:
  - Objective: Balanced (w_f = 0.5, w_p = 0.5)
  - Search Space: Frozen [0.12, 1.20] µm x [0.24, 2.80] µm on 10 nm grid (28,013 valid points)
  - Budget: 10 LHS space-filling initial evaluations + 40 adaptive BO evaluations = 50 total
  - Random Seed: 2026
  - Model: Gaussian Process Regression with Matérn 5/2 kernel and ARD lengthscales
  - Acquisition: Expected Improvement (xi = 0.01 in standardized objective domain)
  - Duplicate Mitigation: Strict discrete grid exclusion
  - Evaluator Isolation: Explicit mode compatibility check (AUD-01)
  - Atomic Checkpointing: Per-iteration flush, checkpoint state, exception recovery (AUD-02)
  - Output Protection: Overwrite prevention and unique campaign identification (AUD-03)
  - Result Validation: Strict sanity checks before optimizer registration (AUD-07)
  - Configuration Validation: Complete frozen specification verification (AUD-06)

Master Source of Truth: SRS.md (Section 12 & Section 13)
"""

import argparse
import csv
import json
import math
import os
import sys
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union

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
# Configuration Loading & Comprehensive Validation (AUD-06)
# ==============================================================================

def load_and_validate_bo_config(
    config_path: Union[str, Path] = "configs/bayesian_optimization_config.yaml",
    scenario_key: str = "scenario_a"
) -> Dict[str, Any]:
    """
    Load and strictly validate the dedicated Bayesian Optimization configuration.
    
    Verifies every campaign-critical and frozen parameter:
      - Search space bounds and DRC grid step
      - 5-stage ring oscillator circuit architecture and nominal parameters
      - Headless LTspice simulation tolerances and timeout
      - Normalization constants
      - Budget partitioning (10 LHS + 40 Adaptive BO = 50 evaluations)
      - Scenario A weights (w_f=0.5, w_p=0.5) and seed (2026)
      - Penalty value (-1.0e9) and GPR/EI settings
      
    Args:
        config_path: Path to configuration YAML file.
        scenario_key: Target scenario key ("scenario_a").
        
    Returns:
        Validated configuration dictionary.
        
    Raises:
        FileNotFoundError: If configuration file does not exist.
        ValueError: If any parameter violates frozen methodology requirements.
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

    # 2. Validate circuit specifications (AUD-06)
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

    # 3. Validate simulation specifications (AUD-06)
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

    # 6. Validate Scenario A specifics
    scenarios = opt_cfg.get("scenarios", {})
    if scenario_key not in scenarios:
        raise ValueError(f"Target scenario '{scenario_key}' not defined in configuration.")

    sc_cfg = scenarios[scenario_key]
    if scenario_key == "scenario_a":
        if sc_cfg.get("name") != "balanced":
            raise ValueError(f"Scenario A name must be 'balanced', got '{sc_cfg.get('name')}'")
        if abs(float(sc_cfg.get("w_f", 0.0)) - 0.5) > 1e-12 or abs(float(sc_cfg.get("w_p", 0.0)) - 0.5) > 1e-12:
            raise ValueError(f"Scenario A requires w_f=0.5 and w_p=0.5, got w_f={sc_cfg.get('w_f')}, w_p={sc_cfg.get('w_p')}")

        seeds = opt_cfg.get("seeds", {})
        seed_a = int(seeds.get("scenario_a", 0))
        if seed_a != 2026:
            raise ValueError(f"Scenario A deterministic seed must be 2026, got {seed_a}")

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
# Evaluator Interfaces (Dependency Injection & Strict Mode Lockdown - AUD-01)
# ==============================================================================

class BaseCandidateEvaluator(ABC):
    """Abstract interface for candidate sizing evaluation."""

    @property
    @abstractmethod
    def is_physical(self) -> bool:
        """Return True if this evaluator executes physical circuit simulation, False if synthetic/mock."""
        pass

    @abstractmethod
    def evaluate(self, candidate: Dict[str, float], iteration_idx: int) -> Dict[str, Any]:
        """
        Evaluate candidate transistor sizing [Wn, Wp].
        
        Args:
            candidate: Dictionary containing 'wn' and 'wp' in meters.
            iteration_idx: 0-indexed evaluation iteration counter.
            
        Returns:
            Dictionary containing electrical metrics, feasibility status, and objective score.
        """
        pass


class MockCandidateEvaluator(BaseCandidateEvaluator):
    """
    Mock Candidate Evaluator for Dry-Run and Automated Testing.
    
    Computes deterministic synthetic electrical measurements without invoking LTspice,
    launching subprocesses, writing netlist files, or consuming physical evaluations.
    """

    @property
    def is_physical(self) -> bool:
        return False

    def __init__(
        self,
        objective_evaluator: ObjectiveEvaluator,
        seed: int = 2026,
        fail_extreme_ratios: bool = True
    ):
        """
        Args:
            objective_evaluator: ObjectiveEvaluator instance configured with scenario weights.
            seed: Deterministic integer seed for synthetic reproducibility.
            fail_extreme_ratios: If True, candidate with extreme Wp/Wn ratio fails to oscillate,
                                 exercising the Step 6.1.1 conditioned penalty handling.
        """
        self.objective_evaluator = objective_evaluator
        self.seed = seed
        self.fail_extreme_ratios = fail_extreme_ratios
        self.call_count = 0

    def evaluate(self, candidate: Dict[str, float], iteration_idx: int) -> Dict[str, Any]:
        """Generate deterministic synthetic metrics and compute objective score."""
        self.call_count += 1
        wn = candidate["wn"]
        wp = candidate["wp"]
        ratio = wp / wn

        # Synthetic failure criteria: extreme PMOS dominance or severe NMOS starvation
        # Models physical Level-1 inverter switching breakdown
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
            # Deterministic analytical surrogate proxy for Level-1 5-stage ring oscillator:
            wn_um = wn * 1e6
            wp_um = wp * 1e6
            
            drive_eff = (wn_um * wp_um) / (wn_um + 0.5 * wp_um + 0.1)
            cap_eff = 0.5 + 0.8 * (wn_um + wp_um)
            freq_ghz = 25.0 + 35.0 * (drive_eff / cap_eff)
            freq_hz = freq_ghz * 1e9

            period_s = 1.0 / freq_hz
            delay_ps = (period_s / 10.0) * 1e12  # 5 stages -> 10 transitions per cycle

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

        # Evaluate scalar objective utility using ObjectiveEvaluator
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
    """
    Physical Candidate Evaluator for Live LTspice Execution.
    
    Coordinates NetlistParameterizer, LTspiceRunner, MetricExtractor, and ObjectiveEvaluator.
    NEVER invoked during dry-run validation.
    """

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
        """Execute physical LTspice simulation and parse measurement log."""
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
    """Safely write file with atomic replace and fallback handling for Windows locking (AUD-02, AUD-03)."""
    tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    try:
        if target_path.exists():
            try:
                target_path.unlink()
            except OSError:
                pass
        tmp_path.replace(target_path)
    except OSError:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


# ==============================================================================
# Bayesian Optimization Campaign Runner
# ==============================================================================

class BayesianOptimizationCampaignRunner:
    """
    Coordinates execution of Bayesian Optimization Campaign (Scenario A / Balanced).
    
    Enforces the frozen 50-evaluation budget (10 LHS + 40 adaptive BO), strict grid alignment,
    duplicate mitigation, conditioned penalty tracking, atomic checkpointing, and output protection.
    """

    def __init__(
        self,
        config_path: Union[str, Path] = "configs/bayesian_optimization_config.yaml",
        scenario_key: str = "scenario_a",
        dry_run: bool = True,
        output_dir: Optional[Union[str, Path]] = None,
        evaluator: Optional[BaseCandidateEvaluator] = None,
        overwrite: bool = False
    ):
        """
        Args:
            config_path: Path to bayesian_optimization_config.yaml.
            scenario_key: Scenario identifier ('scenario_a').
            dry_run: If True, uses isolated MockCandidateEvaluator and labels all outputs synthetic.
            output_dir: Custom output directory. Defaults to experiments/bayesian_optimization/scenario_05_05/
                        (or a /dry_run subdirectory if dry_run=True).
            evaluator: Optional custom evaluator instance (dependency injection).
            overwrite: If False, refuses to run if target output directory already contains artifacts (AUD-03).
        """
        self.dry_run = dry_run
        self.scenario_key = scenario_key
        self.overwrite = overwrite

        # 1. Load and strictly validate configuration (AUD-06)
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

        # 2. Configure Objective Evaluator
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

        # 4. Resolve Output Directory & Overwrite Protection (AUD-03)
        if output_dir is not None:
            self.output_dir = Path(output_dir)
        else:
            base_dir = PROJECT_ROOT / self.config["logging"]["scenario_a_dir"]
            self.output_dir = base_dir / "dry_run" if self.dry_run else base_dir

        self._check_output_directory_safeguards()

        self.plots_dir = self.output_dir / "plots"
        self.raw_dir = self.output_dir / "raw_results"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.plots_dir.mkdir(parents=True, exist_ok=True)
        if not self.dry_run:
            self.raw_dir.mkdir(parents=True, exist_ok=True)

        # Unique Campaign Identifier for Auditability (AUD-03)
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        mode_tag = "dry_run" if self.dry_run else "physical"
        self.campaign_id = f"bo_scenario_a_{self.seed}_{mode_tag}_{timestamp_str}"

        # 5. Configure & Validate Candidate Evaluator Compatibility (AUD-01)
        if evaluator is not None:
            # Enforce mode compatibility: reject physical evaluator in dry-run, reject mock in physical
            is_phys = getattr(evaluator, "is_physical", False) or isinstance(evaluator, PhysicalCandidateEvaluator)
            if self.dry_run and is_phys:
                raise ValueError(
                    "Security violation: Physical evaluator injected into dry-run mode. "
                    "Dry-run mode requires an isolated synthetic evaluator (is_physical=False)."
                )
            if not self.dry_run and not is_phys:
                raise ValueError(
                    "Configuration error: Mock/synthetic evaluator injected into physical campaign mode. "
                    "Physical campaign execution requires an explicit physical evaluator (is_physical=True)."
                )
            self.evaluator = evaluator
        elif self.dry_run:
            self.evaluator = MockCandidateEvaluator(
                objective_evaluator=self.objective_evaluator,
                seed=self.seed,
                fail_extreme_ratios=True
            )
        else:
            # Physical mode requested: validate physical environment (AUD-04)
            self._validate_physical_environment()
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

        # Evaluation telemetry tracking
        self.results_records: List[Dict[str, Any]] = []
        self.evaluated_candidates: Set[Tuple[float, float]] = set()
        self.best_candidate: Optional[Dict[str, Any]] = None

    def _check_output_directory_safeguards(self) -> None:
        """Prevent accidental overwriting of completed/partial campaigns (AUD-03)."""
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
                "Refusing to overwrite without explicit overwrite=True (or --overwrite flag). "
                "Specify an empty directory or explicitly authorize replacement."
            )

    def _validate_physical_environment(self) -> None:
        """Validate prerequisites before executing physical simulation campaign (AUD-04)."""
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
        """
        Validate and sanitize candidate evaluation output before registration (AUD-07).
        
        Enforces:
        - Result is a dictionary with required keys: 'status', 'is_feasible', 'objective_score', 'metrics'.
        - 'objective_score' is a finite float. If NaN or infinite, coerces to penalty_value.
        - Feasibility consistency: If is_feasible is True, status MUST be 'SUCCESS' and metrics['is_oscillating'] MUST be True.
        - Metrics dictionary completeness: Safely populates missing electrical keys with None.
        """
        if not isinstance(raw_result, dict):
            return {
                "status": "MALFORMED_NON_DICT_RESULT",
                "is_feasible": False,
                "objective_score": self.penalty_value,
                "metrics": {
                    "status": "FAILED",
                    "is_oscillating": False,
                    "freq_hz": None, "freq_ghz": None, "period_s": None,
                    "power_w": None, "power_mw": None, "delay_s": None,
                    "delay_ps": None, "pdp_j": None
                },
                "breakdown": {"error": f"Evaluator returned non-dict type: {type(raw_result)}"},
                "sim_time_sec": 0.0,
                "is_synthetic": self.dry_run
            }

        status = str(raw_result.get("status", "FAILED"))
        is_feasible = bool(raw_result.get("is_feasible", False))

        try:
            score = float(raw_result.get("objective_score", self.penalty_value))
            if math.isnan(score) or math.isinf(score):
                score = self.penalty_value
                is_feasible = False
                status = "MALFORMED_NON_FINITE_SCORE"
        except (ValueError, TypeError):
            score = self.penalty_value
            is_feasible = False
            status = "MALFORMED_UNPARSEABLE_SCORE"

        metrics = raw_result.get("metrics")
        if not isinstance(metrics, dict):
            metrics = {
                "status": "FAILED",
                "is_oscillating": False,
                "freq_hz": None, "freq_ghz": None, "period_s": None,
                "power_w": None, "power_mw": None, "delay_s": None,
                "delay_ps": None, "pdp_j": None
            }
            is_feasible = False
            score = self.penalty_value

        is_oscillating = bool(metrics.get("is_oscillating", False))

        # Enforce consistency between feasibility and oscillation status
        if is_feasible and (status != "SUCCESS" or not is_oscillating):
            is_feasible = False
            score = self.penalty_value
            status = "INCONSISTENT_FEASIBILITY"

        # Ensure canonical electrical keys exist
        for key in ["freq_ghz", "power_mw", "period_s", "delay_ps", "pdp_j"]:
            if key not in metrics:
                metrics[key] = None

        return {
            "status": status,
            "is_feasible": is_feasible,
            "objective_score": score,
            "metrics": metrics,
            "breakdown": raw_result.get("breakdown", {}),
            "sim_time_sec": float(raw_result.get("sim_time_sec", 0.0)),
            "is_synthetic": bool(raw_result.get("is_synthetic", self.dry_run))
        }

    def _write_checkpoint(self, iter_idx: int, last_candidate: Dict[str, float]) -> None:
        """Atomically persist campaign state checkpoint after every iteration (AUD-02)."""
        checkpoint_payload = {
            "campaign_id": self.campaign_id,
            "completed_evaluations": iter_idx + 1,
            "total_budget": self.total_evaluations,
            "is_dry_run": self.dry_run,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "best_candidate": self.best_candidate,
            "last_candidate": last_candidate
        }
        final_path = self.output_dir / "checkpoint.json"
        _safe_write_file(final_path, json.dumps(checkpoint_payload, indent=2))

    def _append_record_to_csv(self, record: Dict[str, Any], is_first: bool = False) -> None:
        """Atomically append a completed evaluation record to results.csv (AUD-02)."""
        csv_path = self.output_dir / "results.csv"
        csv_fields = [
            "iteration", "phase", "seed", "Wn", "Wp", "ratio", "frequency", "average_power",
            "period", "delay", "PDP", "objective", "simulation_status", "oscillation_status",
            "runtime", "Wn_um", "Wp_um", "Wp_Wn_ratio", "frequency_ghz", "average_power_uw",
            "period_ps", "delay_ps", "pdp_fj", "objective_score", "runtime_sec", "is_synthetic"
        ]
        mode = "w" if is_first else "a"
        with open(csv_path, mode, newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields)
            if is_first:
                writer.writeheader()
            writer.writerow(record)
            f.flush()
            os.fsync(f.fileno())

    def run(self) -> Dict[str, Any]:
        """
        Execute the Bayesian Optimization campaign.
        
        Guarantees:
        - Per-iteration atomic checkpointing to results.csv and checkpoint.json (AUD-02).
        - Exception handling preventing campaign data loss on simulator crash (AUD-02).
        - Sanitized result registration and best-candidate tracking (AUD-07).
        - Strict budget capping at exactly 50 physical evaluations without retries.
        
        Returns:
            Dictionary containing campaign summary statistics and artifacts metadata.
        """
        mode_str = "DRY-RUN (SYNTHETIC)" if self.dry_run else "PHYSICAL SIMULATION"
        print("=" * 80)
        print(f"STARTING BAYESIAN OPTIMIZATION CAMPAIGN — SCENARIO A ({mode_str})")
        print(f"  Campaign ID: {self.campaign_id}")
        print(f"  Objective: Balanced (w_f = {self.w_f}, w_p = {self.w_p})")
        print(f"  Frozen Search Space: Wn in [{self.search_space['wn_min']*1e6:.2f}, {self.search_space['wn_max']*1e6:.2f}] µm | "
              f"Wp in [{self.search_space['wp_min']*1e6:.2f}, {self.search_space['wp_max']*1e6:.2f}] µm")
        print(f"  Grid Resolution: {self.search_space['step_size']*1e9:.1f} nm (28,013 valid points)")
        print(f"  Deterministic Seed: {self.seed}")
        print(f"  Evaluation Budget: {self.total_evaluations} total ({self.n_initial_samples} LHS + {self.n_adaptive_iterations} adaptive)")
        print(f"  Output Directory: {self.output_dir}")
        print("=" * 80)

        start_time_all = time.time()
        csv_initialized = False

        try:
            for iter_idx in range(self.total_evaluations):
                # Budget safeguard
                if len(self.optimizer.history) >= self.total_evaluations:
                    print(f"Evaluation budget limit ({self.total_evaluations}) reached. Stopping.")
                    break

                # 1. Propose candidate
                candidate = self.optimizer.suggest()
                wn = float(candidate["wn"])
                wp = float(candidate["wp"])
                coord = (round(wn, 12), round(wp, 12))

                # 2. Strict candidate validation (grid, bounds, uniqueness)
                step_nm = self.search_space["step_size"] * 1e9
                wn_nm = round(wn * 1e9, 4)
                wp_nm = round(wp * 1e9, 4)
                if abs(wn_nm % step_nm) > 1e-4 or abs(wp_nm % step_nm) > 1e-4:
                    raise ValueError(f"Candidate {coord} is not snapped to {step_nm} nm grid.")

                if wn < self.search_space["wn_min"] - 1e-12 or wn > self.search_space["wn_max"] + 1e-12:
                    raise ValueError(f"Candidate Wn={wn} exceeds bounds [{self.search_space['wn_min']}, {self.search_space['wn_max']}].")
                if wp < self.search_space["wp_min"] - 1e-12 or wp > self.search_space["wp_max"] + 1e-12:
                    raise ValueError(f"Candidate Wp={wp} exceeds bounds [{self.search_space['wp_min']}, {self.search_space['wp_max']}].")

                if coord in self.evaluated_candidates:
                    raise RuntimeError(f"Duplicate candidate proposed: {coord}. Duplicate mitigation failed.")

                self.evaluated_candidates.add(coord)

                # 3. Evaluate candidate with exception recovery (AUD-02)
                try:
                    raw_result = self.evaluator.evaluate(candidate, iteration_idx=iter_idx)
                    eval_result = self._validate_and_sanitize_result(candidate, raw_result)
                except Exception as exc:
                    # Capture evaluation failure without aborting campaign or losing prior records
                    eval_result = {
                        "status": f"EVALUATOR_EXCEPTION: {type(exc).__name__}",
                        "is_feasible": False,
                        "objective_score": self.penalty_value,
                        "metrics": {
                            "status": "FAILED",
                            "is_oscillating": False,
                            "error": str(exc),
                            "freq_hz": None, "freq_ghz": None, "period_s": None,
                            "power_w": None, "power_mw": None, "delay_s": None,
                            "delay_ps": None, "pdp_j": None
                        },
                        "breakdown": {"error": str(exc)},
                        "sim_time_sec": 0.0,
                        "is_synthetic": self.dry_run
                    }

                # 4. Register result with Bayesian Optimizer (refits GP during adaptive phase)
                self.optimizer.register(candidate, eval_result)

                # 5. Extract metrics and record telemetry
                metrics = eval_result["metrics"]
                score = float(eval_result["objective_score"])
                status = eval_result["status"]
                is_oscillating = bool(metrics.get("is_oscillating", False))
                is_feasible = bool(eval_result["is_feasible"])
                phase = "LHS" if iter_idx < self.n_initial_samples else "ADAPTIVE_BO"
                ratio = wp / wn

                record = {
                    "iteration": iter_idx + 1,  # 1-indexed (1..50)
                    "phase": phase,
                    "seed": self.seed,
                    "Wn": round(wn * 1e6, 4),
                    "Wp": round(wp * 1e6, 4),
                    "ratio": round(ratio, 4),
                    "frequency": round(metrics["freq_ghz"], 6) if metrics.get("freq_ghz") is not None else None,
                    "average_power": round(metrics["power_mw"] * 1000, 3) if metrics.get("power_mw") is not None else None,
                    "period": round(metrics["period_s"] * 1e12, 4) if metrics.get("period_s") is not None else None,
                    "delay": round(metrics["delay_ps"], 4) if metrics.get("delay_ps") is not None else None,
                    "PDP": round(metrics["pdp_j"] * 1e15, 6) if metrics.get("pdp_j") is not None else None,
                    "objective": round(score, 6),
                    "simulation_status": status,
                    "oscillation_status": "VALID" if is_oscillating else "NO_OSCILLATION",
                    "runtime": round(eval_result.get("sim_time_sec", 0.0), 3),
                    # Canonical detailed fields
                    "Wn_um": round(wn * 1e6, 4),
                    "Wp_um": round(wp * 1e6, 4),
                    "Wp_Wn_ratio": round(ratio, 4),
                    "frequency_ghz": round(metrics["freq_ghz"], 6) if metrics.get("freq_ghz") is not None else None,
                    "average_power_uw": round(metrics["power_mw"] * 1000, 3) if metrics.get("power_mw") is not None else None,
                    "period_ps": round(metrics["period_s"] * 1e12, 4) if metrics.get("period_s") is not None else None,
                    "delay_ps": round(metrics["delay_ps"], 4) if metrics.get("delay_ps") is not None else None,
                    "pdp_fj": round(metrics["pdp_j"] * 1e15, 6) if metrics.get("pdp_j") is not None else None,
                    "objective_score": round(score, 6),
                    "runtime_sec": round(eval_result.get("sim_time_sec", 0.0), 3),
                    "is_synthetic": self.dry_run
                }

                self.results_records.append(record)

                # Update best feasible candidate
                if is_feasible and (self.best_candidate is None or score > self.best_candidate["objective_score"]):
                    self.best_candidate = record

                # 6. Immediate per-iteration persistence (AUD-02)
                self._append_record_to_csv(record, is_first=(not csv_initialized))
                csv_initialized = True
                self._write_checkpoint(iter_idx, candidate)

                freq_str = f"{record['frequency_ghz']:.3f} GHz" if record['frequency_ghz'] is not None else "N/A"
                pow_str = f"{record['average_power_uw']:.1f} µW" if record['average_power_uw'] is not None else "N/A"

                print(
                    f"[{phase:11s}] Iter {iter_idx+1:02d}/50 | "
                    f"Wn={record['Wn_um']:.2f}µm, Wp={record['Wp_um']:.2f}µm (Ratio={record['Wp_Wn_ratio']:.2f}) | "
                    f"Status={record['oscillation_status']} | Freq={freq_str} | Power={pow_str} | "
                    f"F={record['objective_score']:.4f}"
                )

        finally:
            total_duration = time.time() - start_time_all
            print(f"\nCampaign execution phase ended in {total_duration:.2f} seconds.")
            # Ensure final summary and config are saved even on premature loop exit (AUD-02)
            self._save_final_artifacts(total_duration)

        valid_records = [r for r in self.results_records if r["oscillation_status"] == "VALID"]
        best_cand = max(valid_records, key=lambda x: x["objective_score"]) if valid_records else None

        return {
            "campaign_id": self.campaign_id,
            "total_evaluations": len(self.results_records),
            "feasible_evaluations": len(valid_records),
            "best_candidate": best_cand,
            "duration_sec": total_duration,
            "is_dry_run": self.dry_run,
            "output_dir": str(self.output_dir)
        }

    def _save_final_artifacts(self, total_duration: float) -> None:
        """Write config.json and summary.md artifacts atomically (AUD-02, AUD-03)."""
        valid_records = [r for r in self.results_records if r["oscillation_status"] == "VALID"]
        best_cand = max(valid_records, key=lambda x: x["objective_score"]) if valid_records else None

        # 1. config.json
        config_payload = {
            "campaign_id": self.campaign_id,
            "campaign_name": "bayesian_optimization_scenario_a",
            "scenario": "scenario_a_balanced_05_05",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_dry_run": self.dry_run,
            "is_synthetic_data": self.dry_run,
            "seed": self.seed,
            "total_evaluations": self.total_evaluations,
            "n_initial_samples_lhs": self.n_initial_samples,
            "n_adaptive_iterations_bo": self.n_adaptive_iterations,
            "search_space": {
                "wn_min_um": self.search_space["wn_min"] * 1e6,
                "wn_max_um": self.search_space["wn_max"] * 1e6,
                "wp_min_um": self.search_space["wp_min"] * 1e6,
                "wp_max_um": self.search_space["wp_max"] * 1e6,
                "step_size_nm": self.search_space["step_size"] * 1e9,
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
                "nugget": self.opt_cfg["nugget"],
                "acquisition": "expected_improvement",
                "xi_standardized_domain": self.opt_cfg["xi"]
            },
            "execution": {
                "duration_sec": round(total_duration, 3),
                "completed_iterations": len(self.results_records),
                "feasible_iterations": len(valid_records)
            }
        }
        cfg_final = self.output_dir / "config.json"
        _safe_write_file(cfg_final, json.dumps(config_payload, indent=2))

        # 2. summary.md
        dry_run_notice = "> [!NOTE]\n> **THIS IS A DRY-RUN VALIDATION DATASET GENERATED USING A DETERMINISTIC SYNTHETIC EVALUATOR.**\n> Zero LTspice simulations were executed. Physical simulation execution remains pending separate authorization.\n" if self.dry_run else ""

        summary_md = f"""# Bayesian Optimization Campaign A Summary (Scenario A: Balanced 0.5/0.5)

{dry_run_notice}
- **Campaign ID:** `{self.campaign_id}`
- **Campaign Mode:** {"DRY-RUN (SYNTHETIC EVALUATOR)" if self.dry_run else "PHYSICAL LTSPICE EXECUTION"}
- **Total Evaluations:** {len(self.results_records)} / {self.total_evaluations}
- **Initial LHS Design:** {min(len(self.results_records), self.n_initial_samples)} evaluations
- **Adaptive BO Iterations:** {max(0, len(self.results_records) - self.n_initial_samples)} evaluations
- **Feasible / Valid Simulations:** {len(valid_records)} / {max(len(self.results_records), 1)} ({len(valid_records)/max(len(self.results_records),1)*100:.1f}%)
- **Deterministic Seed:** {self.seed}
- **Total Duration:** {total_duration:.2f} s
- **Acquisition Policy:** Expected Improvement (xi = 0.01 in standardized objective domain)
- **Search Space:** Wn in [0.12, 1.20] µm, Wp in [0.24, 2.80] µm (10 nm grid, 28,013 valid points)

## Best Feasible Candidate
"""
        if best_cand:
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
# CLI Entrypoint (AUD-04)
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Run Bayesian Optimization Campaign A for CMOS Ring Oscillator."
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
        help="Explicitly permit overwriting an existing campaign directory (AUD-03)."
    )
    parser.add_argument(
        "--execute-physical-campaign",
        action="store_true",
        default=False,
        help="Explicit physical execution pathway flag. Locked until authorized (AUD-04)."
    )

    args = parser.parse_args()

    if args.execute_physical_campaign:
        # Safety gate: Physical campaign execution requires explicit approval environment variable (AUD-04)
        if os.environ.get("AUTHORIZE_PHYSICAL_CAMPAIGN_A") != "1":
            print("=" * 80)
            print("SAFETY INTERLOCK: PHYSICAL CAMPAIGN EXECUTION IS CURRENTLY LOCKED.")
            print("The physical execution pathway has been validated, but Step 6.2.1 approval")
            print("is restricted to software tests and dry-run validation.")
            print("To unlock physical execution once approved by the user, set AUTHORIZE_PHYSICAL_CAMPAIGN_A=1.")
            print("=" * 80)
            sys.exit(1)

        runner = BayesianOptimizationCampaignRunner(
            config_path=args.config,
            scenario_key="scenario_a",
            dry_run=False,
            output_dir=args.output_dir,
            overwrite=args.overwrite
        )
    else:
        runner = BayesianOptimizationCampaignRunner(
            config_path=args.config,
            scenario_key="scenario_a",
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

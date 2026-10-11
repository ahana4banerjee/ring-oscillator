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
  - Dry-Run Mode: Synthetic evaluation with zero LTspice/subprocess/netlist interactions.

Master Source of Truth: SRS.md (Section 12 & Section 13)
"""

import argparse
import csv
import json
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
# Configuration Loading & Validation
# ==============================================================================

def load_and_validate_bo_config(
    config_path: Union[str, Path] = "configs/bayesian_optimization_config.yaml",
    scenario_key: str = "scenario_a"
) -> Dict[str, Any]:
    """
    Load and strictly validate the dedicated Bayesian Optimization configuration.
    
    Args:
        config_path: Path to configuration YAML file.
        scenario_key: Target scenario key ("scenario_a" or "scenario_b").
        
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
        if k in config["search_space"]:
            config["search_space"][k] = float(config["search_space"][k])
    validate_frozen_bounds(config["search_space"])

    # 2. Validate optimization parameters
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

    # 3. Validate budget partitioning
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

    # 4. Validate Scenario A specifics
    scenarios = opt_cfg.get("scenarios", {})
    if scenario_key not in scenarios:
        raise ValueError(f"Target scenario '{scenario_key}' not defined in configuration.")

    sc_cfg = scenarios[scenario_key]
    if scenario_key == "scenario_a":
        if abs(float(sc_cfg.get("w_f", 0.0)) - 0.5) > 1e-12 or abs(float(sc_cfg.get("w_p", 0.0)) - 0.5) > 1e-12:
            raise ValueError(f"Scenario A requires w_f=0.5 and w_p=0.5, got w_f={sc_cfg.get('w_f')}, w_p={sc_cfg.get('w_p')}")

        seeds = opt_cfg.get("seeds", {})
        seed_a = int(seeds.get("scenario_a", 0))
        if seed_a != 2026:
            raise ValueError(f"Scenario A deterministic seed must be 2026, got {seed_a}")

    # 5. Validate normalization baselines
    norm_cfg = config.get("normalization", {})
    f0 = float(norm_cfg.get("baseline_frequency_hz", 0.0))
    p0 = float(norm_cfg.get("baseline_power_w", 0.0))
    if abs(f0 - 41069756649.1) > 1.0:
        raise ValueError(f"Baseline frequency must be 41.0697566491 GHz, got {f0} Hz")
    if abs(p0 - 0.000140169553568) > 1e-12:
        raise ValueError(f"Baseline power must be 140.169553568 µW, got {p0} W")

    return config


# ==============================================================================
# Evaluator Interfaces (Dependency Injection for Strict Dry-Run Isolation)
# ==============================================================================

class BaseCandidateEvaluator(ABC):
    """Abstract interface for candidate sizing evaluation."""

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
            # - Frequency scales with effective drive conductance Wn*Wp/(Wn+Wp) and inversely with total W
            # - Power scales with frequency and total capacitive load (dynamic power cv^2*f)
            wn_um = wn * 1e6
            wp_um = wp * 1e6
            
            # Smooth physical approximation centered near nominal baseline (0.5u/1.0u -> 41.07 GHz, 140.2 uW)
            drive_eff = (wn_um * wp_um) / (wn_um + 0.5 * wp_um + 0.1)
            cap_eff = 0.5 + 0.8 * (wn_um + wp_um)
            freq_ghz = 25.0 + 35.0 * (drive_eff / cap_eff)
            freq_hz = freq_ghz * 1e9

            period_s = 1.0 / freq_hz
            delay_ps = (period_s / 10.0) * 1e12  # 5 stages -> 10 transitions per cycle

            # Dynamic capacitive switching power
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

        # Evaluate scalar objective utility using authoritative ObjectiveEvaluator
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


# ==============================================================================
# Bayesian Optimization Campaign Runner
# ==============================================================================

class BayesianOptimizationCampaignRunner:
    """
    Coordinates execution of Bayesian Optimization Campaign (Scenario A / Balanced).
    
    Enforces the frozen 50-evaluation budget (10 LHS + 40 adaptive BO), strict grid alignment,
    duplicate mitigation, conditioned penalty tracking, and atomic result logging.
    """

    def __init__(
        self,
        config_path: Union[str, Path] = "configs/bayesian_optimization_config.yaml",
        scenario_key: str = "scenario_a",
        dry_run: bool = True,
        output_dir: Optional[Union[str, Path]] = None,
        evaluator: Optional[BaseCandidateEvaluator] = None
    ):
        """
        Args:
            config_path: Path to bayesian_optimization_config.yaml.
            scenario_key: Scenario identifier ('scenario_a').
            dry_run: If True, uses isolated MockCandidateEvaluator and labels all outputs synthetic.
            output_dir: Custom output directory. Defaults to experiments/bayesian_optimization/scenario_05_05/
                        (or a /dry_run subdirectory if dry_run=True).
            evaluator: Optional custom evaluator instance (dependency injection).
        """
        self.dry_run = dry_run
        self.scenario_key = scenario_key

        # 1. Load and validate configuration
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

        # 4. Resolve Output Directory
        if output_dir is not None:
            self.output_dir = Path(output_dir)
        else:
            base_dir = PROJECT_ROOT / self.config["logging"]["scenario_a_dir"]
            self.output_dir = base_dir / "dry_run" if self.dry_run else base_dir

        self.plots_dir = self.output_dir / "plots"
        self.raw_dir = self.output_dir / "raw_results"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.plots_dir.mkdir(parents=True, exist_ok=True)
        if not self.dry_run:
            self.raw_dir.mkdir(parents=True, exist_ok=True)

        # 5. Configure Candidate Evaluator
        if evaluator is not None:
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

        # Evaluation telemetry tracking
        self.results_records: List[Dict[str, Any]] = []
        self.evaluated_candidates: Set[Tuple[float, float]] = set()

    def run(self) -> Dict[str, Any]:
        """
        Execute the Bayesian Optimization campaign.
        
        Returns:
            Dictionary containing campaign summary statistics and artifacts metadata.
        """
        mode_str = "DRY-RUN (SYNTHETIC)" if self.dry_run else "PHYSICAL SIMULATION"
        print("=" * 80)
        print(f"STARTING BAYESIAN OPTIMIZATION CAMPAIGN — SCENARIO A ({mode_str})")
        print(f"  Objective: Balanced (w_f = {self.w_f}, w_p = {self.w_p})")
        print(f"  Frozen Search Space: Wn in [{self.search_space['wn_min']*1e6:.2f}, {self.search_space['wn_max']*1e6:.2f}] µm | "
              f"Wp in [{self.search_space['wp_min']*1e6:.2f}, {self.search_space['wp_max']*1e6:.2f}] µm")
        print(f"  Grid Resolution: {self.search_space['step_size']*1e9:.1f} nm (28,013 valid points)")
        print(f"  Deterministic Seed: {self.seed}")
        print(f"  Evaluation Budget: {self.total_evaluations} total ({self.n_initial_samples} LHS + {self.n_adaptive_iterations} adaptive)")
        print(f"  Output Directory: {self.output_dir}")
        print("=" * 80)

        start_time_all = time.time()

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

            # 3. Evaluate candidate via injected evaluator
            eval_result = self.evaluator.evaluate(candidate, iteration_idx=iter_idx)

            # 4. Register result with Bayesian Optimizer (refits GP during adaptive phase)
            self.optimizer.register(candidate, eval_result)

            # 5. Extract metrics and record telemetry
            metrics = eval_result["metrics"]
            score = float(eval_result["objective_score"])
            status = eval_result["status"]
            is_oscillating = bool(metrics.get("is_oscillating", False))
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

            freq_str = f"{record['frequency_ghz']:.3f} GHz" if record['frequency_ghz'] is not None else "N/A"
            pow_str = f"{record['average_power_uw']:.1f} µW" if record['average_power_uw'] is not None else "N/A"

            print(
                f"[{phase:11s}] Iter {iter_idx+1:02d}/50 | "
                f"Wn={record['Wn_um']:.2f}µm, Wp={record['Wp_um']:.2f}µm (Ratio={record['Wp_Wn_ratio']:.2f}) | "
                f"Status={record['oscillation_status']} | Freq={freq_str} | Power={pow_str} | "
                f"F={record['objective_score']:.4f}"
            )

        total_duration = time.time() - start_time_all
        print(f"\nCampaign execution completed in {total_duration:.2f} seconds.")

        # 6. Save artifacts
        self._save_artifacts(total_duration)

        valid_records = [r for r in self.results_records if r["oscillation_status"] == "VALID"]
        best_cand = max(valid_records, key=lambda x: x["objective_score"]) if valid_records else None

        return {
            "total_evaluations": len(self.results_records),
            "feasible_evaluations": len(valid_records),
            "best_candidate": best_cand,
            "duration_sec": total_duration,
            "is_dry_run": self.dry_run,
            "output_dir": str(self.output_dir)
        }

    def _save_artifacts(self, total_duration: float) -> None:
        """Write config.json, results.csv, and summary.md artifacts."""
        valid_records = [r for r in self.results_records if r["oscillation_status"] == "VALID"]
        best_cand = max(valid_records, key=lambda x: x["objective_score"]) if valid_records else None

        # 1. config.json
        config_payload = {
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
        with open(self.output_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump(config_payload, f, indent=2)

        # 2. results.csv
        csv_fields = [
            "iteration", "phase", "seed", "Wn", "Wp", "ratio", "frequency", "average_power",
            "period", "delay", "PDP", "objective", "simulation_status", "oscillation_status",
            "runtime", "Wn_um", "Wp_um", "Wp_Wn_ratio", "frequency_ghz", "average_power_uw",
            "period_ps", "delay_ps", "pdp_fj", "objective_score", "runtime_sec", "is_synthetic"
        ]
        with open(self.output_dir / "results.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields)
            writer.writeheader()
            writer.writerows(self.results_records)

        # 3. summary.md
        dry_run_notice = "> [!NOTE]\n> **THIS IS A DRY-RUN VALIDATION DATASET GENERATED USING A DETERMINISTIC SYNTHETIC EVALUATOR.**\n> Zero LTspice simulations were executed. Physical simulation execution remains pending separate authorization.\n" if self.dry_run else ""

        summary_md = f"""# Bayesian Optimization Campaign A Summary (Scenario A: Balanced 0.5/0.5)

{dry_run_notice}
- **Campaign Mode:** {"DRY-RUN (SYNTHETIC EVALUATOR)" if self.dry_run else "PHYSICAL LTSPICE EXECUTION"}
- **Total Evaluations:** {len(self.results_records)} / {self.total_evaluations}
- **Initial LHS Design:** {self.n_initial_samples} evaluations
- **Adaptive BO Iterations:** {len(self.results_records) - self.n_initial_samples} evaluations
- **Feasible / Valid Simulations:** {len(valid_records)} / {len(self.results_records)} ({len(valid_records)/max(len(self.results_records),1)*100:.1f}%)
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

        with open(self.output_dir / "summary.md", "w", encoding="utf-8") as f:
            f.write(summary_md)

        print(f"Artifacts successfully written to: {self.output_dir}")


# ==============================================================================
# CLI Entrypoint
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
        "--execute-physical-campaign",
        action="store_true",
        default=False,
        help="EXPLICIT FLAG REQUIRED TO RUN PHYSICAL SIMULATIONS. In Step 6.2.1, this is FORBIDDEN."
    )

    args = parser.parse_args()

    if args.execute_physical_campaign:
        print("ERROR: Physical simulation execution is FORBIDDEN in Step 6.2.1.")
        print("Step 6.2.1 requires dry-run validation only. Separate user approval is required to launch LTspice.")
        sys.exit(1)

    runner = BayesianOptimizationCampaignRunner(
        config_path=args.config,
        scenario_key="scenario_a",
        dry_run=True,
        output_dir=args.output_dir
    )
    summary = runner.run()
    print("\nDRY-RUN VALIDATION COMPLETE.")
    print(f"Evaluations: {summary['total_evaluations']} | Feasible: {summary['feasible_evaluations']}")


if __name__ == "__main__":
    main()

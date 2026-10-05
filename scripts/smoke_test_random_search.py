"""
Phase 5.2: Random Search Smoke Test Script.

Executes a 5-iteration end-to-end Random Search pipeline validation test
using LTspice batch simulations, metric extraction, objective evaluation,
and structured CSV logging.
"""

import sys
import yaml
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ltspice.parameterizer import NetlistParameterizer
from src.simulation.runner import LTspiceRunner
from src.evaluation.extractor import MetricExtractor
from src.evaluation.objective import ObjectiveEvaluator
from src.optimization.random_search import RandomSearchOptimizer
from src.utils.logger import ExperimentLogger


def run_smoke_test(config_path: Path, n_iterations: int = 5, seed: int = 42):
    """Run a 5-iteration Random Search smoke test.

    Args:
        config_path: Path to optimization_config.yaml
        n_iterations: Number of iterations (default: 5)
        seed: Random seed for reproducibility (default: 42)
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 1. Initialize Pipeline Components
    template_path = PROJECT_ROOT / config["circuit"]["template_netlist"]
    ltspice_exe = Path(config["simulation"]["ltspice_executable"])
    timeout_sec = float(config["simulation"]["timeout_seconds"])

    parameterizer = NetlistParameterizer(template_path)
    runner = LTspiceRunner(ltspice_exe, timeout_seconds=timeout_sec)
    extractor = MetricExtractor(stages=config["circuit"]["stages"])

    # Objective Evaluator (Phase 1-3 baseline normalization, Config B 0.5/0.5)
    norm_cfg = config["normalization"]
    opt_cfg = config["optimization"]
    profile_name = opt_cfg.get("profile", "balanced")
    weights = opt_cfg["profiles"][profile_name]

    evaluator = ObjectiveEvaluator(
        baseline_freq_hz=float(norm_cfg["baseline_frequency_hz"]),
        baseline_power_w=float(norm_cfg["baseline_power_w"]),
        w_f=float(weights["w_f"]),
        w_p=float(weights["w_p"]),
        objective_mode=opt_cfg.get("objective_mode", "weighted"),
        penalty_value=float(opt_cfg.get("penalty_value", -1.0e9))
    )

    # Search Space & Optimizer
    search_space = config["search_space"]
    optimizer = RandomSearchOptimizer(search_space=search_space, seed=seed)

    # Logger
    csv_log_path = PROJECT_ROOT / "results" / "processed" / "smoke_test_log.csv"
    summary_json_path = PROJECT_ROOT / "results" / "processed" / "smoke_test_summary.json"
    logger = ExperimentLogger(
        csv_path=csv_log_path,
        summary_path=summary_json_path,
        experiment_id="exp_phase5_2_smoke",
        method="RANDOM_SEARCH"
    )

    work_dir = PROJECT_ROOT / "results" / "raw" / "smoke_test"
    work_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"STARTING PHASE 5.2 RANDOM SEARCH SMOKE TEST ({n_iterations} ITERATIONS)")
    print(f"Search Bounds: Wn=[{search_space['wn_min']*1e6:.2f}u, {search_space['wn_max']*1e6:.2f}u], "
          f"Wp=[{search_space['wp_min']*1e6:.2f}u, {search_space['wp_max']*1e6:.2f}u]")
    print(f"Random Seed: {seed}")
    print("=" * 70)

    for i in range(n_iterations):
        candidate = optimizer.suggest()
        print(f"\n[Iteration {i+1}/{n_iterations}] Candidate Proposed: "
              f"Wn = {candidate['wn']*1e6:.4f} um, Wp = {candidate['wp']*1e6:.4f} um")

        # Execute simulation pipeline via optimizer helper
        result_payload = optimizer.evaluate_candidate(
            candidate=candidate,
            parameterizer=parameterizer,
            runner=runner,
            extractor=extractor,
            objective_evaluator=evaluator,
            work_dir=work_dir,
            iteration_idx=i
        )

        # Log iteration to CSV
        log_rec = logger.log_iteration(iteration=i, candidate=candidate, result=result_payload)

        status = result_payload["status"]
        score = result_payload["objective_score"]
        metrics = result_payload["metrics"]

        if status == "SUCCESS":
            freq_ghz = metrics.get('freq_ghz', 0.0)
            power_mw = metrics.get('power_mw', 0.0)
            delay_ps = metrics.get('delay_ps', 0.0)
            print(f"  Status: {status} | Score: {score:+.6f} | "
                  f"Freq: {freq_ghz:.3f} GHz | Power: {power_mw:.3f} mW | Delay: {delay_ps:.2f} ps")
        else:
            print(f"  Status: {status} | Score: {score:+.6f} (PENALTY APPLIED)")

    best_rec = optimizer.get_best_candidate()
    logger.write_summary(
        total_evaluations=n_iterations,
        best_candidate_record=best_rec,
        config_snapshot=config
    )

    print("\n" + "=" * 70)
    print("PHASE 5.2 SMOKE TEST COMPLETED SUCCESSFULLY!")
    print(f"Total Iterations: {n_iterations}")
    print(f"CSV Log Location: {csv_log_path}")
    print(f"Summary JSON Location: {summary_json_path}")
    if best_rec:
        best_cand = best_rec["candidate"]
        print(f"Best Candidate: Wn={best_cand['wn']*1e6:.4f} um, Wp={best_cand['wp']*1e6:.4f} um "
              f"with Objective Score: {best_rec['objective_score']:+.6f}")
    else:
        print("Best Candidate: None (all candidates failed/non-oscillating)")
    print("=" * 70)

    return optimizer, logger


if __name__ == "__main__":
    cfg_file = PROJECT_ROOT / "configs" / "optimization_config.yaml"
    run_smoke_test(cfg_file, n_iterations=5, seed=42)

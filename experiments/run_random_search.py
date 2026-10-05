"""
Phase 5.3: Development Random Search Campaign Runner.

Executes a reproducible 20-iteration Random Search campaign over the temporary development search bounds
(Wn in [0.18um, 0.80um], Wp in [0.36um, 1.60um]) using LTspice batch execution, metric extraction,
objective utility evaluation, and structured CSV logging.
"""

import sys
import yaml
import time
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ltspice.parameterizer import NetlistParameterizer
from src.simulation.runner import LTspiceRunner
from src.evaluation.extractor import MetricExtractor
from src.evaluation.objective import ObjectiveEvaluator
from src.optimization.random_search import RandomSearchOptimizer
from src.utils.logger import ExperimentLogger


def run_random_search_campaign(config_path: Path, n_iterations: int = 20, seed: int = 42):
    """Run Phase 5.3 reproducible 20-iteration Random Search campaign.

    Args:
        config_path: Path to optimization_config.yaml
        n_iterations: Total evaluations (default: 20)
        seed: Random seed for reproducibility (default: 42)
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 1. Pipeline Component Initialization
    template_path = PROJECT_ROOT / config["circuit"]["template_netlist"]
    ltspice_exe = Path(config["simulation"]["ltspice_executable"])
    timeout_sec = float(config["simulation"]["timeout_seconds"])

    parameterizer = NetlistParameterizer(template_path)
    runner = LTspiceRunner(ltspice_exe, timeout_seconds=timeout_sec)
    extractor = MetricExtractor(stages=config["circuit"]["stages"])

    # 2. Objective Evaluator Configuration
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

    # 3. Search Space & Optimizer Setup
    search_space = config["search_space"]
    optimizer = RandomSearchOptimizer(search_space=search_space, seed=seed)

    # 4. Logger Setup (writing to primary experiment_log.csv and run_summary.json)
    csv_log_path = PROJECT_ROOT / config["logging"]["results_csv"]
    summary_json_path = PROJECT_ROOT / config["logging"]["summary_json"]

    logger = ExperimentLogger(
        csv_path=csv_log_path,
        summary_path=summary_json_path,
        experiment_id="exp_phase5_3_random_search",
        method="RANDOM_SEARCH"
    )

    work_dir = PROJECT_ROOT / "results" / "raw" / "random_search_20iter"
    work_dir.mkdir(parents=True, exist_ok=True)

    start_wall_time = time.time()

    print("=" * 80)
    print(f"STARTING PHASE 5.3: DEVELOPMENT RANDOM SEARCH CAMPAIGN ({n_iterations} ITERATIONS)")
    print(f"Search Bounds: Wn=[{search_space['wn_min']*1e6:.2f}u, {search_space['wn_max']*1e6:.2f}u], "
          f"Wp=[{search_space['wp_min']*1e6:.2f}u, {search_space['wp_max']*1e6:.2f}u]")
    print(f"Weight Profile: '{profile_name}' (wf={weights['w_f']}, wp={weights['w_p']})")
    print(f"Random Seed: {seed}")
    print(f"Output CSV Log: {csv_log_path}")
    print("=" * 80)

    success_count = 0
    failure_count = 0

    for i in range(n_iterations):
        candidate = optimizer.suggest()

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

        # Log to structured CSV
        logger.log_iteration(iteration=i, candidate=candidate, result=result_payload)

        status = result_payload["status"]
        score = result_payload["objective_score"]
        metrics = result_payload["metrics"]
        sim_time = result_payload["sim_time_sec"]

        wn_um = candidate["wn"] * 1e6
        wp_um = candidate["wp"] * 1e6

        if status == "SUCCESS":
            success_count += 1
            freq_ghz = metrics.get('freq_ghz', 0.0)
            power_mw = metrics.get('power_mw', 0.0)
            delay_ps = metrics.get('delay_ps', 0.0)
            print(f"[{i+1:02d}/{n_iterations:02d}] Candidate (Wn={wn_um:0.2f}u, Wp={wp_um:0.2f}u) -> "
                  f"SUCCESS | Score: {score:+.6f} | Freq: {freq_ghz:6.3f} GHz | "
                  f"Power: {power_mw:7.3f} mW | Delay: {delay_ps:5.2f} ps | ({sim_time:.2f}s)")
        else:
            failure_count += 1
            print(f"[{i+1:02d}/{n_iterations:02d}] Candidate (Wn={wn_um:0.2f}u, Wp={wp_um:0.2f}u) -> "
                  f"{status:14s} | Score: {score:+.1e} (Penalty) | ({sim_time:.2f}s)")

    total_wall_time = time.time() - start_wall_time
    best_rec = optimizer.get_best_candidate()

    # Export JSON summary artifact
    logger.write_summary(
        total_evaluations=n_iterations,
        best_candidate_record=best_rec,
        config_snapshot=config
    )

    print("\n" + "=" * 80)
    print("PHASE 5.3 DEVELOPMENT RANDOM SEARCH CAMPAIGN COMPLETE")
    print(f"Total Iterations Executed : {n_iterations}")
    print(f"Successful (Valid Osc)   : {success_count} ({success_count/n_iterations*100:.1f}%)")
    print(f"Failed / Non-Oscillating : {failure_count} ({failure_count/n_iterations*100:.1f}%)")
    print(f"Total Execution Time     : {total_wall_time:.2f} seconds")
    print(f"Experiment Log CSV       : {csv_log_path}")
    print(f"Summary Artifact JSON    : {summary_json_path}")
    print("-" * 80)
    if best_rec:
        best_cand = best_rec["candidate"]
        best_res = best_rec["result"]
        best_metrics = best_res["metrics"]
        print(f"Best Candidate in Sample : Wn={best_cand['wn']*1e6:.4f} um, Wp={best_cand['wp']*1e6:.4f} um")
        print(f"  Objective Utility Score: {best_rec['objective_score']:+.6f}")
        print(f"  Oscillation Frequency  : {best_metrics.get('freq_ghz', 0.0):.3f} GHz")
        print(f"  Average Power          : {best_metrics.get('power_mw', 0.0):.3f} mW")
        print(f"  Stage Propagation Delay: {best_metrics.get('delay_ps', 0.0):.2f} ps")
    else:
        print("Best Candidate in Sample : None (all evaluated candidates failed)")
    print("=" * 80)

    return optimizer, logger


if __name__ == "__main__":
    cfg_file = PROJECT_ROOT / "configs" / "optimization_config.yaml"
    run_random_search_campaign(cfg_file, n_iterations=20, seed=42)

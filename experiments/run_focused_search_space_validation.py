"""
Phase 5.4A: Focused Search-Space Validation Campaign Runner (100 Iterations).

Executes a 100-iteration Random Search campaign over the focused bounds
(Wn in [0.18um, 0.50um], Wp in [0.36um, 1.20um]) with 10nm grid snapping
to validate the spatial continuity and density of the feasible oscillation region.
"""

import sys
import csv
import json
import yaml
import time
import datetime
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


def run_focused_validation_campaign(config_path: Path, n_iterations: int = 100, seed: int = 2026):
    """Run Phase 5.4A 100-iteration focused search-space validation.

    Args:
        config_path: Path to optimization_config.yaml
        n_iterations: Total evaluations (default: 100)
        seed: Random seed for reproducibility (default: 2026)
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Focused Search Space Bounds (Phase 5.4A)
    focused_search_space = {
        "wn_min": 0.18e-6,
        "wn_max": 0.50e-6,
        "wp_min": 0.36e-6,
        "wp_max": 1.20e-6,
        "step_size": 10e-9  # 10nm grid snapping preserved
    }

    # 1. Pipeline Initialization
    template_path = PROJECT_ROOT / config["circuit"]["template_netlist"]
    ltspice_exe = Path(config["simulation"]["ltspice_executable"])
    timeout_sec = float(config["simulation"]["timeout_seconds"])

    parameterizer = NetlistParameterizer(template_path)
    runner = LTspiceRunner(ltspice_exe, timeout_seconds=timeout_sec)
    extractor = MetricExtractor(stages=config["circuit"]["stages"])

    # Dual Evaluators: Config B (0.5/0.5) and Config S (0.7/0.3)
    norm_cfg = config["normalization"]
    f0 = float(norm_cfg["baseline_frequency_hz"])
    p0 = float(norm_cfg["baseline_power_w"])
    penalty = float(config["optimization"].get("penalty_value", -1.0e9))

    evaluator_b = ObjectiveEvaluator(
        baseline_freq_hz=f0, baseline_power_w=p0, w_f=0.5, w_p=0.5, objective_mode="weighted", penalty_value=penalty
    )
    evaluator_s = ObjectiveEvaluator(
        baseline_freq_hz=f0, baseline_power_w=p0, w_f=0.7, w_p=0.3, objective_mode="weighted", penalty_value=penalty
    )

    # 2. Optimizer & Working Directory
    optimizer = RandomSearchOptimizer(search_space=focused_search_space, seed=seed)

    csv_log_path = PROJECT_ROOT / "results" / "processed" / "experiment_log_focused_100iter.csv"
    summary_json_path = PROJECT_ROOT / "results" / "processed" / "run_summary_focused_100iter.json"
    csv_log_path.parent.mkdir(parents=True, exist_ok=True)

    work_dir = PROJECT_ROOT / "results" / "raw" / "focused_100iter"
    work_dir.mkdir(parents=True, exist_ok=True)

    # CSV Headers
    headers = [
        "experiment_id",
        "iteration",
        "method",
        "timestamp",
        "wn_um",
        "wp_um",
        "ratio_wp_wn",
        "status",
        "freq_ghz",
        "power_mw",
        "delay_ps",
        "score_config_b",
        "score_config_s",
        "sim_time_sec",
        "failure_reason"
    ]

    with open(csv_log_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

    print("=" * 85)
    print(f"STARTING PHASE 5.4A: FOCUSED SEARCH-SPACE VALIDATION ({n_iterations} ITERATIONS)")
    print(f"Focused Bounds: Wn=[0.18u, 0.50u], Wp=[0.36u, 1.20u] | Grid Snapping: 10nm")
    print(f"Random Seed: {seed}")
    print(f"Output CSV: {csv_log_path}")
    print("=" * 85)

    success_count = 0
    failure_count = 0
    records = []
    best_b_record = None
    best_b_score = -float('inf')
    best_s_record = None
    best_s_score = -float('inf')

    start_wall_time = time.time()

    for i in range(n_iterations):
        candidate = optimizer.suggest()
        wn_um = candidate["wn"] * 1e6
        wp_um = candidate["wp"] * 1e6
        ratio = wp_um / wn_um

        # Execute candidate simulation
        iter_str = f"iter_{i:04d}"
        netlist_path = work_dir / f"run_{iter_str}.net"

        parameterizer.generate_netlist({"Wn": candidate["wn"], "Wp": candidate["wp"]}, netlist_path)
        sim_res = runner.run(netlist_path)
        metrics = extractor.extract(sim_res)

        # Dual Objective Scoring
        score_b, feasible_b, breakdown_b = evaluator_b.evaluate(metrics)
        score_s, feasible_s, breakdown_s = evaluator_s.evaluate(metrics)

        status = metrics.get("status", "FAILED")
        failure_reason = metrics.get("error_message") or ("No 0.9V crossings" if status == "NO_OSCILLATION" else "")
        sim_time = sim_res.elapsed_time

        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        freq_ghz = metrics.get("freq_ghz") if feasible_b else None
        power_mw = metrics.get("power_mw") if feasible_b else None
        delay_ps = metrics.get("delay_ps") if feasible_b else None

        row = [
            "exp_phase5_4a_focused",
            i,
            "RANDOM_SEARCH",
            timestamp,
            f"{wn_um:.4f}",
            f"{wp_um:.4f}",
            f"{ratio:.4f}",
            status,
            f"{freq_ghz:.4f}" if freq_ghz is not None else "NaN",
            f"{power_mw:.4f}" if power_mw is not None else "NaN",
            f"{delay_ps:.4f}" if delay_ps is not None else "NaN",
            f"{score_b:.6f}",
            f"{score_s:.6f}",
            f"{sim_time:.3f}",
            failure_reason
        ]

        with open(csv_log_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(row)

        record = {
            "iteration": i,
            "wn_um": wn_um,
            "wp_um": wp_um,
            "ratio_wp_wn": ratio,
            "status": status,
            "freq_ghz": freq_ghz,
            "power_mw": power_mw,
            "delay_ps": delay_ps,
            "score_config_b": score_b,
            "score_config_s": score_s,
            "sim_time_sec": sim_time,
            "failure_reason": failure_reason
        }
        records.append(record)

        if feasible_b:
            success_count += 1
            if score_b > best_b_score:
                best_b_score = score_b
                best_b_record = record
            if score_s > best_s_score:
                best_s_score = score_s
                best_s_record = record

            print(f"[{i+1:03d}/{n_iterations:03d}] (Wn={wn_um:0.2f}u, Wp={wp_um:0.2f}u, Ratio={ratio:0.2f}) -> "
                  f"SUCCESS | Freq: {freq_ghz:6.3f}GHz | Pwr: {power_mw:6.2f}mW | "
                  f"ScoreB: {score_b:+.4f} | ScoreS: {score_s:+.4f}")
        else:
            failure_count += 1
            print(f"[{i+1:03d}/{n_iterations:03d}] (Wn={wn_um:0.2f}u, Wp={wp_um:0.2f}u, Ratio={ratio:0.2f}) -> "
                  f"{status:14s} | Score: {score_b:+.1e}")

    total_wall_time = time.time() - start_wall_time

    summary = {
        "experiment_id": "exp_phase5_4a_focused",
        "method": "RANDOM_SEARCH",
        "seed": seed,
        "focused_bounds": {
            "wn_um_min": 0.18,
            "wn_um_max": 0.50,
            "wp_um_min": 0.36,
            "wp_um_max": 1.20,
            "step_size_nm": 10
        },
        "total_evaluations": n_iterations,
        "successful_evaluations": success_count,
        "failed_evaluations": failure_count,
        "success_rate_pct": (success_count / n_iterations) * 100.0,
        "total_wall_time_sec": total_wall_time,
        "best_candidate_config_b": best_b_record,
        "best_candidate_config_s": best_s_record
    }

    with open(summary_json_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 85)
    print("PHASE 5.4A FOCUSED VALIDATION CAMPAIGN COMPLETE")
    print(f"Total Iterations Executed : {n_iterations}")
    print(f"Successful (Valid Osc)   : {success_count} ({success_count/n_iterations*100:.1f}%)")
    print(f"Failed / Non-Oscillating : {failure_count} ({failure_count/n_iterations*100:.1f}%)")
    print(f"Total Wall Time          : {total_wall_time:.2f}s (~{total_wall_time/n_iterations:.2f}s/sim)")
    print(f"CSV Output Location      : {csv_log_path}")
    print(f"JSON Summary Location    : {summary_json_path}")
    print("-" * 85)
    if best_b_record:
        print(f"Best Config B Candidate  : Wn={best_b_record['wn_um']:.4f}u, Wp={best_b_record['wp_um']:.4f}u (Ratio={best_b_record['ratio_wp_wn']:.2f})")
        print(f"  Config B Score         : {best_b_record['score_config_b']:+.6f}")
        print(f"  Frequency              : {best_b_record['freq_ghz']:.3f} GHz")
        print(f"  Power                  : {best_b_record['power_mw']:.3f} mW")
        print(f"  Propagation Delay      : {best_b_record['delay_ps']:.2f} ps")
    if best_s_record:
        print(f"Best Config S Candidate  : Wn={best_s_record['wn_um']:.4f}u, Wp={best_s_record['wp_um']:.4f}u (Ratio={best_s_record['ratio_wp_wn']:.2f})")
        print(f"  Config S Score         : {best_s_record['score_config_s']:+.6f}")
        print(f"  Frequency              : {best_s_record['freq_ghz']:.3f} GHz")
        print(f"  Power                  : {best_s_record['power_mw']:.3f} mW")
        print(f"  Propagation Delay      : {best_s_record['delay_ps']:.2f} ps")
    print("=" * 85)

    return summary


if __name__ == "__main__":
    cfg_file = PROJECT_ROOT / "configs" / "optimization_config.yaml"
    run_focused_validation_campaign(cfg_file, n_iterations=100, seed=2026)

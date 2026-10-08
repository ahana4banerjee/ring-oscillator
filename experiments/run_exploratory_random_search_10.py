"""
Initial Exploratory Random Search Campaign (10 Evaluations).

Executes a 10-iteration exploratory Random Search across broad independent Wn/Wp candidate ranges
to characterize oscillation feasibility, frequency-power trade-offs, and search-space structure
around and beyond the 40 nm baseline ring oscillator.
"""

import json
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import matplotlib.pyplot as plt

from src.ltspice.parameterizer import NetlistParameterizer
from src.simulation.runner import LTspiceRunner
from src.evaluation.extractor import MetricExtractor
from src.evaluation.objective import ObjectiveEvaluator
from src.optimization.random_search import RandomSearchOptimizer

TEMPLATE_PATH = PROJECT_ROOT / "circuits" / "templates" / "ring_oscillator.net"
LTSPICE_EXE = r"C:\Users\Ahana Banerjee\AppData\Local\Programs\ADI\LTspice\LTspice.exe"

# Output directory structure
EXP_DIR = PROJECT_ROOT / "experiments" / "random_search" / "exploratory_10"
PLOTS_DIR = EXP_DIR / "plots"
RAW_DIR = EXP_DIR / "raw_results"

EXP_DIR.mkdir(parents=True, exist_ok=True)
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Exploratory Bounds Definition (Broad initial candidate range around baseline Wn=0.5u, Wp=1.0u)
SEARCH_SPACE = {
    "wn_min": 0.15e-6,
    "wn_max": 1.20e-6,
    "wp_min": 0.30e-6,
    "wp_max": 2.40e-6,
    "step_size": 10e-9  # 10 nm grid snapping
}
RANDOM_SEED = 42

# 40 nm Verified Baseline Normalization Constants
BASELINE_FREQ_HZ = 41069756649.1       # 41.0697566491 GHz
BASELINE_POWER_W = 0.000140169553568   # 140.169553568 uW


def main():
    print("=" * 80)
    print("STARTING INITIAL EXPLORATORY RANDOM SEARCH (EXACTLY 10 EVALUATIONS)")
    print(f"Seed: {RANDOM_SEED}")
    print(f"Broad Wn range: [{SEARCH_SPACE['wn_min']*1e6:.2f}, {SEARCH_SPACE['wn_max']*1e6:.2f}] um")
    print(f"Broad Wp range: [{SEARCH_SPACE['wp_min']*1e6:.2f}, {SEARCH_SPACE['wp_max']*1e6:.2f}] um")
    print("=" * 80)

    # Write config.json
    config_payload = {
        "experiment_name": "exploratory_10_random_search",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "seed": RANDOM_SEED,
        "search_space": {
            "wn_min_um": SEARCH_SPACE["wn_min"] * 1e6,
            "wn_max_um": SEARCH_SPACE["wn_max"] * 1e6,
            "wp_min_um": SEARCH_SPACE["wp_min"] * 1e6,
            "wp_max_um": SEARCH_SPACE["wp_max"] * 1e6,
            "step_size_nm": SEARCH_SPACE["step_size"] * 1e9
        },
        "baseline": {
            "technology": "40nm",
            "vdd_v": 1.1,
            "wn_base_um": 0.5,
            "wp_base_um": 1.0,
            "f0_ghz": BASELINE_FREQ_HZ / 1e9,
            "p0_uw": BASELINE_POWER_W * 1e6
        },
        "objective": {
            "mode": "weighted",
            "w_f": 0.5,
            "w_p": 0.5,
            "penalty_value": -1.0e9
        }
    }
    with open(EXP_DIR / "config.json", "w", encoding="utf-8") as f:
        json.dump(config_payload, f, indent=2)

    parameterizer = NetlistParameterizer(TEMPLATE_PATH)
    runner = LTspiceRunner(executable_path=LTSPICE_EXE, timeout_seconds=30.0)
    extractor = MetricExtractor(stages=5)
    objective_evaluator = ObjectiveEvaluator(
        baseline_freq_hz=BASELINE_FREQ_HZ,
        baseline_power_w=BASELINE_POWER_W,
        w_f=0.5,
        w_p=0.5,
        objective_mode="weighted",
        penalty_value=-1.0e9
    )
    optimizer = RandomSearchOptimizer(search_space=SEARCH_SPACE, seed=RANDOM_SEED)

    results_records = []

    for i in range(10):
        candidate = optimizer.suggest()
        wn = candidate["wn"]
        wp = candidate["wp"]
        ratio = wp / wn

        eval_result = optimizer.evaluate_candidate(
            candidate=candidate,
            parameterizer=parameterizer,
            runner=runner,
            extractor=extractor,
            objective_evaluator=objective_evaluator,
            work_dir=RAW_DIR,
            iteration_idx=i
        )

        metrics = eval_result["metrics"]
        score = eval_result["objective_score"]
        status = eval_result["status"]
        is_oscillating = metrics.get("is_oscillating", False)

        record = {
            "iteration": i,
            "seed": RANDOM_SEED,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "Wn_um": round(wn * 1e6, 4),
            "Wp_um": round(wp * 1e6, 4),
            "Wp_Wn_ratio": round(ratio, 4),
            "frequency_ghz": round(metrics["freq_ghz"], 6) if metrics.get("freq_ghz") is not None else None,
            "average_power_mw": round(metrics["power_mw"], 6) if metrics.get("power_mw") is not None else None,
            "average_power_uw": round(metrics["power_mw"] * 1000, 3) if metrics.get("power_mw") is not None else None,
            "period_ps": round(metrics["period_s"] * 1e12, 4) if metrics.get("period_s") is not None else None,
            "delay_ps": round(metrics["delay_ps"], 4) if metrics.get("delay_ps") is not None else None,
            "pdp_fj": round(metrics["pdp_j"] * 1e15, 6) if metrics.get("pdp_j") is not None else None,
            "objective_score": round(score, 6),
            "simulation_status": status,
            "oscillation_status": "VALID" if is_oscillating else "NO_OSCILLATION",
            "runtime_sec": round(eval_result["sim_time_sec"], 3)
        }

        results_records.append(record)

        print(f"Iter {i:02d} | Wn={record['Wn_um']:.2f}u, Wp={record['Wp_um']:.2f}u (Ratio={record['Wp_Wn_ratio']:.2f}) | "
              f"Status={record['oscillation_status']} | Freq={record['frequency_ghz']} GHz | Power={record['average_power_uw']} uW | "
              f"Score={record['objective_score']:.4f}")

    # Save results.csv
    csv_fields = list(results_records[0].keys())
    with open(EXP_DIR / "results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows(results_records)

    # Plotting Exploratory Results
    valid_records = [r for r in results_records if r["oscillation_status"] == "VALID"]
    invalid_records = [r for r in results_records if r["oscillation_status"] != "VALID"]

    plt.figure(figsize=(10, 7))
    if valid_records:
        plt.scatter([r["Wn_um"] for r in valid_records],
                    [r["Wp_um"] for r in valid_records],
                    c=[r["objective_score"] for r in valid_records],
                    cmap="viridis", s=120, edgecolors="black", label="VALID Oscillation", zorder=3)
        plt.colorbar(label="Objective Score F")
    if invalid_records:
        plt.scatter([r["Wn_um"] for r in invalid_records],
                    [r["Wp_um"] for r in invalid_records],
                    color="red", marker="x", s=120, linewidths=2, label="NO_OSCILLATION / Failed", zorder=3)

    plt.plot(0.5, 1.0, "r*", markersize=16, label="Baseline (0.5u / 1.0u)")
    plt.xlim(0.10, 1.30)
    plt.ylim(0.20, 2.50)
    plt.xlabel("NMOS Width Wn (um)")
    plt.ylabel("PMOS Width Wp (um)")
    plt.title("Exploratory Random Search (10 Points) — Feasibility & Score Map")
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(loc="upper left")
    plt.savefig(PLOTS_DIR / "exploratory_10_feasibility_map.png", dpi=300, bbox_inches="tight")
    plt.close()

    print("\n" + "=" * 80)
    print("EXPLORATORY RANDOM SEARCH COMPLETE")
    print(f"Results saved to: {EXP_DIR}")
    print("=" * 80)


if __name__ == "__main__":
    main()

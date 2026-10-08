"""
Formal Random Search Campaign (100 Iterations).

Executes the formal 100-evaluation Random Search campaign across the frozen search space:
  Wn in [0.12 um, 1.20 um]
  Wp in [0.24 um, 2.80 um]
  Grid resolution: 10 nm (0.01 um)
  Deterministic seed: 2026

Establishes the formal stochastic baseline for the 40 nm Ring Oscillator sizing problem.
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

# Output directory structure for formal 100-iteration campaign
EXP_DIR = PROJECT_ROOT / "experiments" / "random_search" / "formal_100"
PLOTS_DIR = EXP_DIR / "plots"
RAW_DIR = EXP_DIR / "raw_results"

EXP_DIR.mkdir(parents=True, exist_ok=True)
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Formal Frozen Search Space Definition
SEARCH_SPACE = {
    "wn_min": 0.12e-6,
    "wn_max": 1.20e-6,
    "wp_min": 0.24e-6,
    "wp_max": 2.80e-6,
    "step_size": 10e-9  # 10 nm grid step
}
RANDOM_SEED = 2026
NUM_EVALUATIONS = 100

# 40 nm Verified Baseline Normalization Constants
BASELINE_FREQ_HZ = 41069756649.1       # 41.0697566491 GHz
BASELINE_POWER_W = 0.000140169553568   # 140.169553568 uW
BASELINE_DELAY_PS = 2.43488172707       # 2.43488172707 ps
BASELINE_PDP_FJ = 0.341300000000       # ~0.3413 fJ


def generate_plots(results_records):
    """Generate all required plots for formal Random Search analysis."""
    valid_records = [r for r in results_records if r["oscillation_status"] == "VALID"]
    invalid_records = [r for r in results_records if r["oscillation_status"] != "VALID"]

    # 1. Wn vs Wp scatter colored by objective
    plt.figure(figsize=(10, 7))
    if valid_records:
        sc = plt.scatter(
            [r["Wn_um"] for r in valid_records],
            [r["Wp_um"] for r in valid_records],
            c=[r["objective_score"] for r in valid_records],
            cmap="viridis", s=80, edgecolors="black", linewidths=0.5, label="Oscillating (VALID)", zorder=3
        )
        cbar = plt.colorbar(sc)
        cbar.set_label("Objective Score F", fontsize=11)
    if invalid_records:
        plt.scatter(
            [r["Wn_um"] for r in invalid_records],
            [r["Wp_um"] for r in invalid_records],
            color="red", marker="x", s=100, linewidths=2, label="Non-oscillating", zorder=3
        )

    plt.axvline(0.50, color="gray", linestyle=":", alpha=0.7, label="Baseline (Wn=0.50, Wp=1.00)")
    plt.axhline(1.00, color="gray", linestyle=":", alpha=0.7)
    plt.xlim(0.10, 1.25)
    plt.ylim(0.20, 2.90)
    plt.xlabel("NMOS Width Wn (µm)", fontsize=12)
    plt.ylabel("PMOS Width Wp (µm)", fontsize=12)
    plt.title("Formal Random Search Space Sampling (N=100, Seed 2026)", fontsize=13, fontweight="bold")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="upper left")
    plt.savefig(PLOTS_DIR / "wn_vs_wp_scatter.png", dpi=300, bbox_inches="tight")
    plt.close()

    # 2. Objective vs Wn
    plt.figure(figsize=(9, 6))
    if valid_records:
        plt.scatter([r["Wn_um"] for r in valid_records], [r["objective_score"] for r in valid_records],
                    color="#1f77b4", s=60, alpha=0.8, edgecolors="none")
    plt.xlabel("NMOS Width Wn (µm)", fontsize=12)
    plt.ylabel("Objective Score F", fontsize=12)
    plt.title("Objective Score vs. NMOS Width Wn", fontsize=13, fontweight="bold")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.savefig(PLOTS_DIR / "objective_vs_wn.png", dpi=300, bbox_inches="tight")
    plt.close()

    # 3. Objective vs Wp
    plt.figure(figsize=(9, 6))
    if valid_records:
        plt.scatter([r["Wp_um"] for r in valid_records], [r["objective_score"] for r in valid_records],
                    color="#2ca02c", s=60, alpha=0.8, edgecolors="none")
    plt.xlabel("PMOS Width Wp (µm)", fontsize=12)
    plt.ylabel("Objective Score F", fontsize=12)
    plt.title("Objective Score vs. PMOS Width Wp", fontsize=13, fontweight="bold")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.savefig(PLOTS_DIR / "objective_vs_wp.png", dpi=300, bbox_inches="tight")
    plt.close()

    # 4. Best-so-far objective vs evaluations
    best_so_far = []
    current_best = -float("inf")
    eval_indices = list(range(1, len(results_records) + 1))
    for r in results_records:
        if r["oscillation_status"] == "VALID" and r["objective_score"] > current_best:
            current_best = r["objective_score"]
        best_so_far.append(current_best)

    plt.figure(figsize=(9, 6))
    plt.plot(eval_indices, best_so_far, color="#d62728", linewidth=2.5, marker="o", markersize=4, label="Best-so-Far F")
    plt.axhline(0.0, color="black", linestyle="--", alpha=0.6, label="Baseline F0 = 0.0")
    plt.xlabel("Evaluation Index", fontsize=12)
    plt.ylabel("Best Observed Objective Score F", fontsize=12)
    plt.title("Formal Random Search Empirical Convergence Curve (N=100)", fontsize=13, fontweight="bold")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="lower right")
    plt.savefig(PLOTS_DIR / "convergence_best_so_far.png", dpi=300, bbox_inches="tight")
    plt.close()

    # 5. Frequency vs Power
    plt.figure(figsize=(9, 6))
    if valid_records:
        plt.scatter([r["average_power_uw"] for r in valid_records],
                    [r["frequency_ghz"] for r in valid_records],
                    c=[r["objective_score"] for r in valid_records], cmap="plasma", s=70, zorder=3)
        cbar = plt.colorbar()
        cbar.set_label("Objective Score F")
    plt.scatter([BASELINE_POWER_W * 1e6], [BASELINE_FREQ_HZ / 1e9], color="black", marker="*", s=200, label="Baseline (Wn=0.5, Wp=1.0)", zorder=4)
    plt.xlabel("Average Power Pavg (µW)", fontsize=12)
    plt.ylabel("Oscillation Frequency fosc (GHz)", fontsize=12)
    plt.title("Frequency vs. Power Trade-off Landscape", fontsize=13, fontweight="bold")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="upper left")
    plt.savefig(PLOTS_DIR / "frequency_vs_power.png", dpi=300, bbox_inches="tight")
    plt.close()

    # 6. PDP vs Wp/Wn ratio
    plt.figure(figsize=(9, 6))
    if valid_records:
        plt.scatter([r["Wp_Wn_ratio"] for r in valid_records],
                    [r["pdp_fj"] for r in valid_records],
                    c=[r["Wn_um"] for r in valid_records], cmap="viridis", s=70, zorder=3)
        cbar = plt.colorbar()
        cbar.set_label("NMOS Width Wn (µm)")
    plt.axhline(BASELINE_PDP_FJ, color="gray", linestyle="--", label=f"Baseline PDP ({BASELINE_PDP_FJ:.4f} fJ)")
    plt.xlabel("Sizing Ratio (Wp / Wn)", fontsize=12)
    plt.ylabel("Power-Delay Product PDP (fJ)", fontsize=12)
    plt.title("Power-Delay Product (PDP) vs. Transistor Sizing Ratio", fontsize=13, fontweight="bold")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="upper right")
    plt.savefig(PLOTS_DIR / "pdp_vs_sizing.png", dpi=300, bbox_inches="tight")
    plt.close()


def main():
    print("=" * 80)
    print("STARTING FORMAL RANDOM SEARCH CAMPAIGN (100 EVALUATIONS, SEED 2026)")
    print(f"Frozen Wn Range: [{SEARCH_SPACE['wn_min']*1e6:.2f}, {SEARCH_SPACE['wn_max']*1e6:.2f}] µm")
    print(f"Frozen Wp Range: [{SEARCH_SPACE['wp_min']*1e6:.2f}, {SEARCH_SPACE['wp_max']*1e6:.2f}] µm")
    print(f"Grid Step: {SEARCH_SPACE['step_size']*1e9:.1f} nm")
    print("=" * 80)

    # Save config.json
    config_payload = {
        "experiment_name": "formal_100_random_search",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "seed": RANDOM_SEED,
        "evaluations": NUM_EVALUATIONS,
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
            "temp_c": 25,
            "stages": 5,
            "load_cap_ff": 0.5,
            "wn_base_um": 0.5,
            "wp_base_um": 1.0,
            "f0_ghz": BASELINE_FREQ_HZ / 1e9,
            "p0_uw": BASELINE_POWER_W * 1e6,
            "tpd0_ps": BASELINE_DELAY_PS,
            "pdp0_fj": BASELINE_PDP_FJ,
            "objective_baseline": 0.0
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

    template_path = PROJECT_ROOT / "circuits" / "templates" / "ring_oscillator.net"
    ltspice_exe = r"C:\Users\Ahana Banerjee\AppData\Local\Programs\ADI\LTspice\LTspice.exe"

    parameterizer = NetlistParameterizer(template_path)
    runner = LTspiceRunner(executable_path=ltspice_exe, timeout_seconds=30.0)
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

    start_time_all = time.time()
    for i in range(NUM_EVALUATIONS):
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
            "iteration": i + 1,  # 1-indexed for clear human reporting (1..100)
            "seed": RANDOM_SEED,
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
            "runtime": round(eval_result["sim_time_sec"], 3),
            # Additional detailed unit headers for downstream tools
            "Wn_um": round(wn * 1e6, 4),
            "Wp_um": round(wp * 1e6, 4),
            "Wp_Wn_ratio": round(ratio, 4),
            "frequency_ghz": round(metrics["freq_ghz"], 6) if metrics.get("freq_ghz") is not None else None,
            "average_power_uw": round(metrics["power_mw"] * 1000, 3) if metrics.get("power_mw") is not None else None,
            "period_ps": round(metrics["period_s"] * 1e12, 4) if metrics.get("period_s") is not None else None,
            "delay_ps": round(metrics["delay_ps"], 4) if metrics.get("delay_ps") is not None else None,
            "pdp_fj": round(metrics["pdp_j"] * 1e15, 6) if metrics.get("pdp_j") is not None else None,
            "objective_score": round(score, 6),
            "runtime_sec": round(eval_result["sim_time_sec"], 3)
        }

        results_records.append(record)

        freq_str = f"{record['frequency_ghz']:.3f} GHz" if record['frequency_ghz'] is not None else "N/A"
        pow_str = f"{record['average_power_uw']:.1f} uW" if record['average_power_uw'] is not None else "N/A"

        print(f"Iter {i+1:03d}/100 | Wn={record['Wn_um']:.2f}µm, Wp={record['Wp_um']:.2f}µm (Ratio={record['Wp_Wn_ratio']:.2f}) | "
              f"Status={record['oscillation_status']} | Freq={freq_str} | Power={pow_str} | "
              f"F={record['objective_score']:.4f}")

    total_duration = time.time() - start_time_all
    print(f"\nAll 100 simulations finished in {total_duration:.2f} seconds.")

    # Save results.csv
    csv_fields = [
        "iteration", "seed", "Wn", "Wp", "ratio", "frequency", "average_power", "period",
        "delay", "PDP", "objective", "simulation_status", "oscillation_status", "runtime",
        "Wn_um", "Wp_um", "Wp_Wn_ratio", "frequency_ghz", "average_power_uw", "period_ps",
        "delay_ps", "pdp_fj", "objective_score", "runtime_sec"
    ]
    with open(EXP_DIR / "results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows(results_records)

    # Generate Plots
    print("Generating plots...")
    generate_plots(results_records)

    # Generate summary.md
    valid_records = [r for r in results_records if r["oscillation_status"] == "VALID"]
    best_obj_cand = max(valid_records, key=lambda x: x["objective_score"])
    max_freq_cand = max(valid_records, key=lambda x: x["frequency_ghz"])
    min_pow_cand = min(valid_records, key=lambda x: x["average_power_uw"])
    min_pdp_cand = min(valid_records, key=lambda x: x["pdp_fj"])

    summary_md = f"""# Formal Random Search 100 Summary

- **Total Simulations:** {NUM_EVALUATIONS}
- **Feasible/Valid:** {len(valid_records)} / {NUM_EVALUATIONS} ({len(valid_records)/NUM_EVALUATIONS*100:.1f}%)
- **Seed:** {RANDOM_SEED}
- **Execution Time:** {total_duration:.2f} s

## Key Results
- **Best Objective Candidate:** Iteration {best_obj_cand['iteration']} (Wn={best_obj_cand['Wn_um']} µm, Wp={best_obj_cand['Wp_um']} µm, F={best_obj_cand['objective_score']:.6f}, Freq={best_obj_cand['frequency_ghz']:.6f} GHz, Power={best_obj_cand['average_power_uw']:.3f} µW, PDP={best_obj_cand['pdp_fj']:.6f} fJ)
- **Highest Frequency Candidate:** Iteration {max_freq_cand['iteration']} (Wn={max_freq_cand['Wn_um']} µm, Wp={max_freq_cand['Wp_um']} µm, Freq={max_freq_cand['frequency_ghz']:.6f} GHz, Power={max_freq_cand['average_power_uw']:.3f} µW, F={max_freq_cand['objective_score']:.6f})
- **Lowest Power Candidate:** Iteration {min_pow_cand['iteration']} (Wn={min_pow_cand['Wn_um']} µm, Wp={min_pow_cand['Wp_um']} µm, Power={min_pow_cand['average_power_uw']:.3f} µW, Freq={min_pow_cand['frequency_ghz']:.6f} GHz, F={min_pow_cand['objective_score']:.6f})
- **Lowest PDP Candidate:** Iteration {min_pdp_cand['iteration']} (Wn={min_pdp_cand['Wn_um']} µm, Wp={min_pdp_cand['Wp_um']} µm, PDP={min_pdp_cand['pdp_fj']:.6f} fJ, Freq={min_pdp_cand['frequency_ghz']:.6f} GHz, Power={min_pdp_cand['average_power_uw']:.3f} µW)
"""
    with open(EXP_DIR / "summary.md", "w", encoding="utf-8") as f:
        f.write(summary_md)

    print("FORMAL RANDOM SEARCH EXECUTION COMPLETE.")


if __name__ == "__main__":
    main()

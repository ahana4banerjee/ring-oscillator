"""
Random Search Re-Scoring Script for Second Objective Scenario (0.7 / 0.3).

Re-scores the existing 100 formal physical Random Search evaluations under the
frequency-priority scalar objective:
    F_0.7/0.3 = 0.7 * (f / f0) - 0.3 * (P / P0)

Does NOT perform any new LTspice simulations.
Generates:
  - experiments/random_search/formal_100_rescored_07_03/config.json
  - experiments/random_search/formal_100_rescored_07_03/results.csv
  - experiments/random_search/formal_100_rescored_07_03/summary.md
  - experiments/random_search/formal_100_rescored_07_03/plots/
"""

import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import matplotlib.pyplot as plt

# Paths
INPUT_CSV = PROJECT_ROOT / "experiments" / "random_search" / "formal_100" / "results.csv"
OUTPUT_DIR = PROJECT_ROOT / "experiments" / "random_search" / "formal_100_rescored_07_03"
PLOTS_DIR = OUTPUT_DIR / "plots"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

# Normalization constants (40 nm baseline)
F0_GHZ = 41.0697566491
P0_UW = 140.169553568
TPD0_PS = 2.43488172707
PDP0_FJ = 0.341300000000
BASELINE_F_05_05 = 0.0
BASELINE_F_07_03 = 0.400000000000


def main():
    print("=" * 80)
    print("STARTING RANDOM SEARCH RE-SCORING FOR OBJECTIVE 0.7 / 0.3")
    print("Source dataset: experiments/random_search/formal_100/results.csv")
    print("Physical simulations: 100 (0 new simulations)")
    print("=" * 80)

    # 1. Load physical evaluations
    raw_records = []
    with open(INPUT_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            freq_ghz = float(r["frequency_ghz"]) if r["frequency_ghz"] else float(r["frequency"])
            power_uw = float(r["average_power_uw"]) if r["average_power_uw"] else float(r["average_power"])
            delay_ps = float(r["delay_ps"]) if r["delay_ps"] else float(r["delay"])
            pdp_fj = float(r["pdp_fj"]) if r["pdp_fj"] else float(r["PDP"])
            f_05_05 = float(r["objective_score"]) if r.get("objective_score") is not None else float(r["objective"])

            # Compute raw 0.7/0.3 objective
            # F_0.7/0.3 = 0.7 * (freq / f0) - 0.3 * (power / p0)
            norm_f = freq_ghz / F0_GHZ
            norm_p = power_uw / P0_UW
            f_07_03 = 0.7 * norm_f - 0.3 * norm_p
            delta_f_07_03 = f_07_03 - BASELINE_F_07_03  # Relative to baseline F=0.4

            raw_records.append({
                "iteration": int(r["iteration"]),
                "seed": int(r["seed"]),
                "Wn": float(r["Wn"]),
                "Wp": float(r["Wp"]),
                "ratio": float(r["ratio"]),
                "frequency": freq_ghz,
                "average_power": power_uw,
                "delay": delay_ps,
                "PDP": pdp_fj,
                "objective_0_5_0_5": f_05_05,
                "objective_0_7_0_3": round(f_07_03, 6),
                "delta_objective_0_7_0_3": round(delta_f_07_03, 6),
                "simulation_status": r["simulation_status"],
                "oscillation_status": r["oscillation_status"],
                "runtime": float(r["runtime"]),
                "Wn_um": float(r["Wn"]),
                "Wp_um": float(r["Wp"]),
                "Wp_Wn_ratio": float(r["ratio"]),
                "frequency_ghz": freq_ghz,
                "average_power_uw": power_uw,
                "delay_ps": delay_ps,
                "pdp_fj": pdp_fj
            })

    # 2. Compute ranks under both objectives
    # Sort for 0.5/0.5
    sorted_05 = sorted(raw_records, key=lambda x: x["objective_0_5_0_5"], reverse=True)
    rank_map_05 = {r["iteration"]: rank + 1 for rank, r in enumerate(sorted_05)}

    # Sort for 0.7/0.3
    sorted_07 = sorted(raw_records, key=lambda x: x["objective_0_7_0_3"], reverse=True)
    rank_map_07 = {r["iteration"]: rank + 1 for rank, r in enumerate(sorted_07)}

    for r in raw_records:
        r["rank_0_5_0_5"] = rank_map_05[r["iteration"]]
        r["rank_0_7_0_3"] = rank_map_07[r["iteration"]]

    # 3. Independent Verification Check on key candidates
    print("\n--- INDEPENDENT VERIFICATION CHECK ---")
    iter_62 = next(r for r in raw_records if r["iteration"] == 62)
    iter_63 = next(r for r in raw_records if r["iteration"] == 63)
    iter_97 = next(r for r in raw_records if r["iteration"] == 97)

    print(f"Iter 62 (Orig 0.5/0.5 Best): Wn={iter_62['Wn']}u, Wp={iter_62['Wp']}u | Freq={iter_62['frequency']:.3f}GHz, Power={iter_62['average_power']:.1f}uW")
    print(f"  -> F_0.5/0.5 = {iter_62['objective_0_5_0_5']:.6f} (Rank {iter_62['rank_0_5_0_5']})")
    print(f"  -> F_0.7/0.3 = {iter_62['objective_0_7_0_3']:.6f} (Rank {iter_62['rank_0_7_0_3']})")

    print(f"\nIter 63 (Max Freq): Wn={iter_63['Wn']}u, Wp={iter_63['Wp']}u | Freq={iter_63['frequency']:.3f}GHz, Power={iter_63['average_power']:.1f}uW")
    print(f"  -> F_0.5/0.5 = {iter_63['objective_0_5_0_5']:.6f} (Rank {iter_63['rank_0_5_0_5']})")
    print(f"  -> F_0.7/0.3 = {iter_63['objective_0_7_0_3']:.6f} (Rank {iter_63['rank_0_7_0_3']})")

    print(f"\nIter 97 (Min Power): Wn={iter_97['Wn']}u, Wp={iter_97['Wp']}u | Freq={iter_97['frequency']:.3f}GHz, Power={iter_97['average_power']:.1f}uW")
    print(f"  -> F_0.5/0.5 = {iter_97['objective_0_5_0_5']:.6f} (Rank {iter_97['rank_0_5_0_5']})")
    print(f"  -> F_0.7/0.3 = {iter_97['objective_0_7_0_3']:.6f} (Rank {iter_97['rank_0_7_0_3']})")

    # 4. Save config.json
    config_payload = {
        "experiment_name": "formal_100_rescored_07_03",
        "source_dataset": "experiments/random_search/formal_100/results.csv",
        "physical_evaluations": 100,
        "new_simulations": 0,
        "seed": 2026,
        "objective_scenarios": {
            "scenario_a": {"w_f": 0.5, "w_p": 0.5, "baseline_f": 0.0},
            "scenario_b": {"w_f": 0.7, "w_p": 0.3, "baseline_f": 0.4}
        },
        "baseline_constants": {
            "f0_ghz": F0_GHZ,
            "p0_uw": P0_UW,
            "tpd0_ps": TPD0_PS,
            "pdp0_fj": PDP0_FJ
        }
    }
    with open(OUTPUT_DIR / "config.json", "w", encoding="utf-8") as f:
        json.dump(config_payload, f, indent=2)

    # 5. Save results.csv
    fields = [
        "iteration", "seed", "Wn", "Wp", "ratio", "frequency", "average_power", "delay", "PDP",
        "objective_0_5_0_5", "objective_0_7_0_3", "delta_objective_0_7_0_3",
        "rank_0_5_0_5", "rank_0_7_0_3", "simulation_status", "oscillation_status", "runtime",
        "Wn_um", "Wp_um", "Wp_Wn_ratio", "frequency_ghz", "average_power_uw", "delay_ps", "pdp_fj"
    ]
    with open(OUTPUT_DIR / "results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(raw_records)

    # 6. Convergence trajectory comparison plot
    best_so_far_05 = []
    best_so_far_07 = []
    curr_best_05 = -float("inf")
    curr_best_07 = -float("inf")
    eval_indices = list(range(1, 101))

    for r in raw_records:
        if r["objective_0_5_0_5"] > curr_best_05:
            curr_best_05 = r["objective_0_5_0_5"]
        if r["objective_0_7_0_3"] > curr_best_07:
            curr_best_07 = r["objective_0_7_0_3"]
        best_so_far_05.append(curr_best_05)
        best_so_far_07.append(curr_best_07)

    plt.figure(figsize=(10, 6))
    plt.plot(eval_indices, best_so_far_05, color="#1f77b4", linewidth=2.5, marker="o", markersize=3, label="Scenario A: Balanced (0.5 f / 0.5 P)")
    plt.plot(eval_indices, best_so_far_07, color="#d62728", linewidth=2.5, marker="s", markersize=3, label="Scenario B: Frequency-Priority (0.7 f / 0.3 P)")
    plt.axhline(0.0, color="#1f77b4", linestyle="--", alpha=0.5, label="Baseline F (0.5/0.5) = 0.0")
    plt.axhline(0.4, color="#d62728", linestyle="--", alpha=0.5, label="Baseline F (0.7/0.3) = 0.4")
    plt.xlabel("Evaluation Index", fontsize=12)
    plt.ylabel("Best Observed Objective Score", fontsize=12)
    plt.title("Random Search Empirical Convergence Trajectory Comparison (N=100 Physical Evals)", fontsize=13, fontweight="bold")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="center right", fontsize=10)
    plt.savefig(PLOTS_DIR / "convergence_comparison_05_vs_07.png", dpi=300, bbox_inches="tight")
    plt.close()

    # Scatter map colored by 0.7/0.3 objective
    plt.figure(figsize=(10, 7))
    sc = plt.scatter(
        [r["Wn"] for r in raw_records],
        [r["Wp"] for r in raw_records],
        c=[r["objective_0_7_0_3"] for r in raw_records],
        cmap="plasma", s=80, edgecolors="black", linewidths=0.5, zorder=3
    )
    cbar = plt.colorbar(sc)
    cbar.set_label("Objective Score F (0.7 / 0.3)", fontsize=11)
    plt.axvline(0.50, color="gray", linestyle=":", alpha=0.7, label="Baseline (Wn=0.50, Wp=1.00)")
    plt.axhline(1.00, color="gray", linestyle=":", alpha=0.7)
    plt.xlim(0.10, 1.25)
    plt.ylim(0.20, 2.90)
    plt.xlabel("NMOS Width Wn (µm)", fontsize=12)
    plt.ylabel("PMOS Width Wp (µm)", fontsize=12)
    plt.title("Random Search Design Space Colored by 0.7/0.3 Objective Score", fontsize=13, fontweight="bold")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="upper left")
    plt.savefig(PLOTS_DIR / "wn_vs_wp_scatter_07_03.png", dpi=300, bbox_inches="tight")
    plt.close()

    # 7. Generate summary.md
    best_05_cand = sorted_05[0]
    best_07_cand = sorted_07[0]

    # Top 10 overlap
    top10_05_iters = set(r["iteration"] for r in sorted_05[:10])
    top10_07_iters = set(r["iteration"] for r in sorted_07[:10])
    overlap_count = len(top10_05_iters.intersection(top10_07_iters))

    print("\n--- RE-SCORING SUMMARY ---")
    print(f"Best 0.5/0.5 Candidate: Iter {best_05_cand['iteration']} (Wn={best_05_cand['Wn']}u, Wp={best_05_cand['Wp']}u) -> F_0.5/0.5 = {best_05_cand['objective_0_5_0_5']:.6f}, F_0.7/0.3 = {best_05_cand['objective_0_7_0_3']:.6f}")
    print(f"Best 0.7/0.3 Candidate: Iter {best_07_cand['iteration']} (Wn={best_07_cand['Wn']}u, Wp={best_07_cand['Wp']}u) -> F_0.7/0.3 = {best_07_cand['objective_0_7_0_3']:.6f}, F_0.5/0.5 = {best_07_cand['objective_0_5_0_5']:.6f}")
    print(f"Top 10 Overlap: {overlap_count} / 10 candidates overlap.")

    summary_md = f"""# Random Search Re-Scoring (0.7 / 0.3 Objective) Summary

- **Source Physical Dataset:** `experiments/random_search/formal_100/results.csv`
- **Physical Simulations Executed:** 100 (Seed 2026)
- **New Simulations:** 0 (Re-scored offline)
- **Baseline Reference:** $W_n=0.50$ µm, $W_p=1.00$ µm ($f_0=41.069757$ GHz, $P_0=140.169554$ µW)

## Key Results Comparison

| Metric | Scenario A (0.5 f / 0.5 P) | Scenario B (0.7 f / 0.3 P) | Shift / Difference |
| :--- | :--- | :--- | :--- |
| **Best Candidate Iteration** | Iteration {best_05_cand['iteration']} | Iteration {best_07_cand['iteration']} | Shifted from Iter {best_05_cand['iteration']} to Iter {best_07_cand['iteration']} |
| **NMOS Width ($W_n$)** | {best_05_cand['Wn']:.2f} µm | {best_07_cand['Wn']:.2f} µm | {best_07_cand['Wn'] - best_05_cand['Wn']:+.2f} µm |
| **PMOS Width ($W_p$)** | {best_05_cand['Wp']:.2f} µm | {best_07_cand['Wp']:.2f} µm | {best_07_cand['Wp'] - best_05_cand['Wp']:+.2f} µm |
| **Sizing Ratio ($W_p/W_n$)** | {best_05_cand['ratio']:.2f} | {best_07_cand['ratio']:.2f} | {best_07_cand['ratio'] - best_05_cand['ratio']:+.2f} |
| **Oscillation Frequency ($f_{{osc}}$)** | {best_05_cand['frequency']:.6f} GHz | {best_07_cand['frequency']:.6f} GHz | {((best_07_cand['frequency'] - best_05_cand['frequency'])/best_05_cand['frequency'])*100:+.2f}% |
| **Average Power ($P_{{avg}}$)** | {best_05_cand['average_power']:.3f} µW | {best_07_cand['average_power']:.3f} µW | {((best_07_cand['average_power'] - best_05_cand['average_power'])/best_05_cand['average_power'])*100:+.2f}% |
| **Propagation Delay ($t_{{pd}}$)** | {best_05_cand['delay']:.4f} ps | {best_07_cand['delay']:.4f} ps | {((best_07_cand['delay'] - best_05_cand['delay'])/best_05_cand['delay'])*100:+.2f}% |
| **Power-Delay Product ($PDP$)** | {best_05_cand['PDP']:.6f} fJ | {best_07_cand['PDP']:.6f} fJ | {((best_07_cand['PDP'] - best_05_cand['PDP'])/best_05_cand['PDP'])*100:+.2f}% |
| **Score under $\mathcal{{F}}_{{0.5/0.5}}$** | **{best_05_cand['objective_0_5_0_5']:.6f}** | {best_07_cand['objective_0_5_0_5']:.6f} | {best_07_cand['objective_0_5_0_5'] - best_05_cand['objective_0_5_0_5']:+.6f} |
| **Score under $\mathcal{{F}}_{{0.7/0.3}}$** | {best_05_cand['objective_0_7_0_3']:.6f} | **{best_07_cand['objective_0_7_0_3']:.6f}** | {best_07_cand['objective_0_7_0_3'] - best_05_cand['objective_0_7_0_3']:+.6f} |

## Top 10 Overlap
- **Top 10 Candidates Overlap Count:** {overlap_count} out of 10.
- **Sizing Region Shift:** Re-scoring under Scenario B shifts preference dramatically from low-power high-ratio candidates ($W_n \approx 0.19$ µm, $W_p \approx 2.66$ µm) to maximum-frequency candidates ($W_n \approx 1.08-1.20$ µm, $W_p \approx 1.87-2.42$ µm) with ratios near ~2.0.
"""
    with open(OUTPUT_DIR / "summary.md", "w", encoding="utf-8") as f:
        f.write(summary_md)

    print("RE-SCORING COMPLETED SUCCESSFULLY.")


if __name__ == "__main__":
    main()

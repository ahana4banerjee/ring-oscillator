"""
Analyze Formal Random Search 100 Dataset.
Computes comprehensive statistics, Pareto frontier, convergence thresholds, top 10 candidates,
PDP metrics, baseline comparisons, and quality control checks.
"""

import csv
import json
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXP_DIR = PROJECT_ROOT / "experiments" / "random_search" / "formal_100"
CSV_PATH = EXP_DIR / "results.csv"

# Baseline reference constants
F0_GHZ = 41.0697566491
P0_UW = 140.169553568
TPD0_PS = 2.43488172707
PDP0_FJ = 0.341300000000
F0_OBJ = 0.0

def main():
    rows = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                "iteration": int(r["iteration"]),
                "seed": int(r["seed"]),
                "Wn": float(r["Wn"]),
                "Wp": float(r["Wp"]),
                "ratio": float(r["ratio"]),
                "frequency": float(r["frequency"]) if r["frequency"] else None,
                "average_power": float(r["average_power"]) if r["average_power"] else None,
                "period": float(r["period"]) if r["period"] else None,
                "delay": float(r["delay"]) if r["delay"] else None,
                "PDP": float(r["PDP"]) if r["PDP"] else None,
                "objective": float(r["objective"]),
                "simulation_status": r["simulation_status"],
                "oscillation_status": r["oscillation_status"],
                "runtime": float(r["runtime"])
            })

    total_sims = len(rows)
    valid_rows = [r for r in rows if r["oscillation_status"] == "VALID"]
    failed_sims = [r for r in rows if r["simulation_status"] != "SUCCESS"]
    non_osc_sims = [r for r in rows if r["oscillation_status"] != "VALID"]

    print("=== A. FEASIBILITY ===")
    print(f"Total: {total_sims}")
    print(f"Successful & Valid: {len(valid_rows)}")
    print(f"Failed: {len(failed_sims)}")
    print(f"Non-oscillating: {len(non_osc_sims)}")
    print(f"Feasibility: {len(valid_rows)/total_sims*100:.2f}%")

    # Quality Control Bounds Check
    wn_valid = all(0.12 <= r["Wn"] <= 1.20 for r in rows)
    wp_valid = all(0.24 <= r["Wp"] <= 2.80 for r in rows)
    grid_wn = all(abs(round(r["Wn"]*100) - r["Wn"]*100) < 1e-5 for r in rows)
    grid_wp = all(abs(round(r["Wp"]*100) - r["Wp"]*100) < 1e-5 for r in rows)
    print(f"\nQC Bounds Check: Wn inside [0.12, 1.20]: {wn_valid}, Wp inside [0.24, 2.80]: {wp_valid}")
    print(f"QC Grid Check (10nm): Wn grid: {grid_wn}, Wp grid: {grid_wp}")

    # Key Candidates
    best_obj = max(valid_rows, key=lambda x: x["objective"])
    max_freq = max(valid_rows, key=lambda x: x["frequency"])
    min_pow = min(valid_rows, key=lambda x: x["average_power"])
    min_pdp = min(valid_rows, key=lambda x: x["PDP"])

    print("\n=== B. BEST OBJECTIVE CANDIDATE ===")
    print(f"Iteration: {best_obj['iteration']}")
    print(f"Wn: {best_obj['Wn']} µm, Wp: {best_obj['Wp']} µm, Ratio: {best_obj['ratio']:.4f}")
    print(f"Objective F: {best_obj['objective']:.6f}")
    print(f"Frequency: {best_obj['frequency']:.6f} GHz")
    print(f"Power: {best_obj['average_power']:.3f} µW")
    print(f"Delay: {best_obj['delay']:.4f} ps")
    print(f"PDP: {best_obj['PDP']:.6f} fJ")

    print("\n=== C. HIGHEST FREQUENCY ===")
    print(f"Iteration: {max_freq['iteration']}")
    print(f"Wn: {max_freq['Wn']} µm, Wp: {max_freq['Wp']} µm, Freq: {max_freq['frequency']:.6f} GHz")
    print(f"Power: {max_freq['average_power']:.3f} µW, Objective F: {max_freq['objective']:.6f}")

    print("\n=== D. LOWEST POWER ===")
    print(f"Iteration: {min_pow['iteration']}")
    print(f"Wn: {min_pow['Wn']} µm, Wp: {min_pow['Wp']} µm, Power: {min_pow['average_power']:.3f} µW")
    print(f"Freq: {min_pow['frequency']:.6f} GHz, Objective F: {min_pow['objective']:.6f}")

    print("\n=== E. LOWEST PDP ===")
    print(f"Iteration: {min_pdp['iteration']}")
    print(f"Wn: {min_pdp['Wn']} µm, Wp: {min_pdp['Wp']} µm, PDP: {min_pdp['PDP']:.6f} fJ")
    print(f"Freq: {min_pdp['frequency']:.6f} GHz, Power: {min_pdp['average_power']:.3f} µW, Objective F: {min_pdp['objective']:.6f}")

    print("\n=== F. BASELINE COMPARISON (Best Obj Candidate vs Baseline) ===")
    freq_change_pct = ((best_obj["frequency"] - F0_GHZ) / F0_GHZ) * 100
    pow_change_pct = ((best_obj["average_power"] - P0_UW) / P0_UW) * 100
    delay_change_pct = ((best_obj["delay"] - TPD0_PS) / TPD0_PS) * 100
    pdp_change_pct = ((best_obj["PDP"] - PDP0_FJ) / PDP0_FJ) * 100
    print(f"Frequency change: {freq_change_pct:+.2f}%")
    print(f"Power change: {pow_change_pct:+.2f}%")
    print(f"Delay change: {delay_change_pct:+.2f}%")
    print(f"PDP change: {pdp_change_pct:+.2f}%")
    print(f"Objective score F: {best_obj['objective']:.6f} (vs baseline 0.000000)")

    # Convergence Analysis
    best_so_far = []
    curr_best = -float("inf")
    for r in rows:
        if r["oscillation_status"] == "VALID" and r["objective"] > curr_best:
            curr_best = r["objective"]
        best_so_far.append(curr_best)

    final_best_score = best_so_far[-1]
    print(f"\n=== CONVERGENCE ANALYSIS ===")
    print(f"Final Best Objective Score: {final_best_score:.6f}")

    # Thresholds: 25%, 50%, 75%, 90%, 100% of final best score
    # Note: baseline is F=0, so fraction relative to 0 -> final_best_score
    thresholds = [0.25, 0.50, 0.75, 0.90, 1.00]
    for t in thresholds:
        target_score = t * final_best_score
        first_eval = next((i + 1 for i, score in enumerate(best_so_far) if score >= target_score), None)
        print(f"Evaluation reaching {int(t*100)}% of final best score ({target_score:.6f}): Iteration {first_eval}")

    # Top 10 Candidates
    top10 = sorted(valid_rows, key=lambda x: x["objective"], reverse=True)[:10]
    print("\n=== TOP 10 CANDIDATES ===")
    print("Rank | Iter | Wn (µm) | Wp (µm) | Ratio | Freq (GHz) | Power (µW) | Delay (ps) | PDP (fJ) | Objective F")
    print("-" * 110)
    for rank, cand in enumerate(top10, 1):
        print(f"{rank:4d} | {cand['iteration']:4d} | {cand['Wn']:7.2f} | {cand['Wp']:7.2f} | {cand['ratio']:5.2f} | "
              f"{cand['frequency']:10.6f} | {cand['average_power']:10.3f} | {cand['delay']:10.4f} | {cand['PDP']:8.6f} | {cand['objective']:11.6f}")

    # PDP Analysis
    pdps = [r["PDP"] for r in valid_rows]
    min_pdp_val = np.min(pdps)
    max_pdp_val = np.max(pdps)
    mean_pdp_val = np.mean(pdps)
    std_pdp_val = np.std(pdps)
    pdp_range_pct = ((max_pdp_val - min_pdp_val) / min_pdp_val) * 100

    print("\n=== PDP ANALYSIS ===")
    print(f"Min PDP: {min_pdp_val:.6f} fJ")
    print(f"Max PDP: {max_pdp_val:.6f} fJ")
    print(f"Mean PDP: {mean_pdp_val:.6f} fJ")
    print(f"Std PDP: {std_pdp_val:.6f} fJ")
    print(f"PDP Percentage Range: {pdp_range_pct:.2f}%")
    print(f"Baseline PDP: {PDP0_FJ:.6f} fJ")

    # Pareto non-dominated set (maximize frequency, minimize power)
    pareto_set = []
    for cand in valid_rows:
        dominated = False
        for other in valid_rows:
            if other["iteration"] == cand["iteration"]:
                continue
            # other dominates cand if other has freq >= cand freq AND other power <= cand power, with at least one strict inequality
            if (other["frequency"] >= cand["frequency"] and other["average_power"] <= cand["average_power"]) and \
               (other["frequency"] > cand["frequency"] or other["average_power"] < cand["average_power"]):
                dominated = True
                break
        if not dominated:
            pareto_set.append(cand)

    pareto_sorted = sorted(pareto_set, key=lambda x: x["frequency"])
    print("\n=== PARETO EFFICIENT FRONTIER (Maximize Freq, Minimize Power) ===")
    print(f"Total Pareto points: {len(pareto_sorted)}")
    print("Iter | Wn (µm) | Wp (µm) | Ratio | Freq (GHz) | Power (µW) | PDP (fJ) | Obj F")
    print("-" * 85)
    for p in pareto_sorted:
        print(f"{p['iteration']:4d} | {p['Wn']:7.2f} | {p['Wp']:7.2f} | {p['ratio']:5.2f} | {p['frequency']:10.6f} | {p['average_power']:10.3f} | {p['PDP']:8.6f} | {p['objective']:11.6f}")

if __name__ == "__main__":
    main()

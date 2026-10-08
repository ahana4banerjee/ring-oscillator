"""
Detailed Analysis of Re-scored 0.7/0.3 Random Search Dataset.
Computes complete comparative tables, top 10 rankings, convergence milestones,
and frequency-power trade-off interpretations.
"""

import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "experiments" / "random_search" / "formal_100_rescored_07_03" / "results.csv"

F0_GHZ = 41.0697566491
P0_UW = 140.169553568
TPD0_PS = 2.43488172707
PDP0_FJ = 0.341300000000

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
                "frequency": float(r["frequency"]),
                "average_power": float(r["average_power"]),
                "delay": float(r["delay"]),
                "PDP": float(r["PDP"]),
                "objective_0_5_0_5": float(r["objective_0_5_0_5"]),
                "objective_0_7_0_3": float(r["objective_0_7_0_3"]),
                "delta_objective_0_7_0_3": float(r["delta_objective_0_7_0_3"]),
                "rank_0_5_0_5": int(r["rank_0_5_0_5"]),
                "rank_0_7_0_3": int(r["rank_0_7_0_3"])
            })

    # Sorts
    sorted_05 = sorted(rows, key=lambda x: x["objective_0_5_0_5"], reverse=True)
    sorted_07 = sorted(rows, key=lambda x: x["objective_0_7_0_3"], reverse=True)

    print("=== TOP 10 UNDER SCENARIO A (0.5 / 0.5) ===")
    for rank, r in enumerate(sorted_05[:10], 1):
        print(f"Rank {rank:2d} | Iter {r['iteration']:3d} | Wn={r['Wn']:4.2f}u, Wp={r['Wp']:4.2f}u | Ratio={r['ratio']:5.2f} | "
              f"Freq={r['frequency']:7.3f}GHz | Pow={r['average_power']:5.1f}uW | F_05={r['objective_0_5_0_5']:+.6f} | "
              f"F_07={r['objective_0_7_0_3']:.6f} (Rank {r['rank_0_7_0_3']:3d})")

    print("\n=== TOP 10 UNDER SCENARIO B (0.7 / 0.3) ===")
    for rank, r in enumerate(sorted_07[:10], 1):
        print(f"Rank {rank:2d} | Iter {r['iteration']:3d} | Wn={r['Wn']:4.2f}u, Wp={r['Wp']:4.2f}u | Ratio={r['ratio']:5.2f} | "
              f"Freq={r['frequency']:7.3f}GHz | Pow={r['average_power']:5.1f}uW | F_07={r['objective_0_7_0_3']:.6f} (d={r['delta_objective_0_7_0_3']:+.6f}) | "
              f"F_05={r['objective_0_5_0_5']:+.6f} (Rank {r['rank_0_5_0_5']:3d})")

    # Milestones for Scenario B (0.7/0.3)
    # Baseline score F=0.4000, Max score F=0.909112, Max delta = 0.509112
    best_so_far_07 = []
    curr_best = -float("inf")
    for r in rows:
        if r["objective_0_7_0_3"] > curr_best:
            curr_best = r["objective_0_7_0_3"]
        best_so_far_07.append(curr_best)

    final_best_07 = best_so_far_07[-1]
    final_delta_07 = final_best_07 - 0.400000

    print(f"\nFinal Best Score 0.7/0.3: {final_best_07:.6f} (Delta over baseline = {final_delta_07:+.6f})")

    thresholds = [0.25, 0.50, 0.75, 0.90, 1.00]
    for t in thresholds:
        target_delta = t * final_delta_07
        target_score = 0.400000 + target_delta
        first_eval = next((i + 1 for i, s in enumerate(best_so_far_07) if s >= target_score), None)
        print(f"Milestone {int(t*100)}% of max delta (score >= {target_score:.6f}): Iteration {first_eval}")

if __name__ == "__main__":
    main()

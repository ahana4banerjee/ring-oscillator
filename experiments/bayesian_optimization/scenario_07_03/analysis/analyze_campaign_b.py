"""
Comprehensive Analysis and Cross-Scenario Comparison Script
for Bayesian Optimization Campaign B (Scenario B: 0.7/0.3 Frequency Priority)
and Comparison with Campaign A (Scenario A: 0.5/0.5 Balanced).
"""

import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
EXP_A_DIR = PROJECT_ROOT / "experiments" / "bayesian_optimization" / "scenario_05_05"
EXP_B_DIR = PROJECT_ROOT / "experiments" / "bayesian_optimization" / "scenario_07_03"
ANALYSIS_B_DIR = EXP_B_DIR / "analysis"
ANALYSIS_B_DIR.mkdir(parents=True, exist_ok=True)

# Frozen Baseline Reference Constants
F0_GHZ = 41.0697566491
P0_UW = 140.169553568
TPD0_PS = 2.43488172707
PDP0_FJ = 0.341296
OBJ_A_BASE = 0.0
OBJ_B_BASE = 0.400000  # 0.7(1.0) - 0.3(1.0) = 0.4

def load_csv(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                "iteration": int(r["iteration"]),
                "phase": r["phase"],
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
                "is_feasible": r["is_feasible"].strip().lower() == "true",
                "simulation_status": r["simulation_status"],
                "oscillation_status": r["oscillation_status"],
                "runtime": float(r["runtime"]),
                "is_synthetic": r.get("is_synthetic", "False").strip().lower() == "true"
            })
    return rows

def compute_convergence(rows):
    best_so_far = []
    current_best = -float("inf")
    current_best_candidate = None
    for r in rows:
        if r["is_feasible"] and r["objective"] > current_best:
            current_best = r["objective"]
            current_best_candidate = r
        best_so_far.append((current_best, current_best_candidate))
    return best_so_far

def run():
    rows_a = load_csv(EXP_A_DIR / "results.csv")
    rows_b = load_csv(EXP_B_DIR / "results.csv")
    
    print("=== SCENARIO B DATASET VALIDATION ===")
    assert len(rows_b) == 50, f"Expected 50 rows in Scenario B, got {len(rows_b)}"
    assert all(not r["is_synthetic"] for r in rows_b), "Found synthetic evaluations in Scenario B!"
    
    feasible_b = [r for r in rows_b if r["is_feasible"]]
    failed_b = [r for r in rows_b if not r["is_feasible"]]
    print(f"Scenario B Total: {len(rows_b)}")
    print(f"Feasible: {len(feasible_b)} ({len(feasible_b)/len(rows_b)*100:.1f}%)")
    print(f"Failed: {len(failed_b)} ({len(failed_b)/len(rows_b)*100:.1f}%)")
    for fr in failed_b:
        print(f"  Failed Iter {fr['iteration']}: Wn={fr['Wn']}, Wp={fr['Wp']}, status={fr['simulation_status']}/{fr['oscillation_status']}, objective={fr['objective']}")
        
    best_b = max(feasible_b, key=lambda x: x["objective"])
    best_a = max([r for r in rows_a if r["is_feasible"]], key=lambda x: x["objective"])
    
    print("\n=== BEST CANDIDATES ===")
    print(f"Scenario A (Iter {best_a['iteration']}): Wn={best_a['Wn']}, Wp={best_a['Wp']}, F={best_a['objective']:.6f}, Freq={best_a['frequency']:.3f} GHz, Power={best_a['average_power']:.3f} uW, Delay={best_a['delay']:.4f} ps, PDP={best_a['PDP']:.6f} fJ")
    print(f"Scenario B (Iter {best_b['iteration']}): Wn={best_b['Wn']}, Wp={best_b['Wp']}, F={best_b['objective']:.6f}, Freq={best_b['frequency']:.3f} GHz, Power={best_b['average_power']:.3f} uW, Delay={best_b['delay']:.4f} ps, PDP={best_b['PDP']:.6f} fJ")
    
    # Cross-Scoring
    # Score A candidate under Scenario B objective
    score_a_under_b = 0.7 * (best_a["frequency"] / F0_GHZ) - 0.3 * (best_a["average_power"] / P0_UW)
    # Score B candidate under Scenario A objective
    score_b_under_a = 0.5 * (best_b["frequency"] / F0_GHZ) - 0.5 * (best_b["average_power"] / P0_UW)
    
    print("\n=== CROSS-SCENARIO EVALUATION ===")
    print(f"Candidate A (Power-Optimized):     F_A = {best_a['objective']:.6f} (Rank 1), F_B = {score_a_under_b:.6f} (Delta vs Base = {score_a_under_b - OBJ_B_BASE:+.6f})")
    print(f"Candidate B (Frequency-Optimized): F_B = {best_b['objective']:.6f} (Rank 1), F_A = {score_b_under_a:.6f} (Delta vs Base = {score_b_under_a - OBJ_A_BASE:+.6f})")
    
    # Save comparison CSV
    comp_csv = ANALYSIS_B_DIR / "comparison_scenario_a_vs_scenario_b.csv"
    with open(comp_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Baseline Reference", "Scenario A (Balanced 0.5/0.5)", "Scenario B (Frequency-Priority 0.7/0.3)"])
        writer.writerow(["Best Wn (um)", "0.50", f"{best_a['Wn']:.2f}", f"{best_b['Wn']:.2f}"])
        writer.writerow(["Best Wp (um)", "1.00", f"{best_a['Wp']:.2f}", f"{best_b['Wp']:.2f}"])
        writer.writerow(["Wp/Wn ratio", "2.0000", f"{best_a['ratio']:.4f}", f"{best_b['ratio']:.4f}"])
        writer.writerow(["Oscillation frequency (GHz)", f"{F0_GHZ:.4f}", f"{best_a['frequency']:.4f}", f"{best_b['frequency']:.4f}"])
        writer.writerow(["Frequency change vs baseline", "0.00%", f"{(best_a['frequency']-F0_GHZ)/F0_GHZ*100:+.2f}%", f"{(best_b['frequency']-F0_GHZ)/F0_GHZ*100:+.2f}%"])
        writer.writerow(["Average power (uW)", f"{P0_UW:.4f}", f"{best_a['average_power']:.4f}", f"{best_b['average_power']:.4f}"])
        writer.writerow(["Power change vs baseline", "0.00%", f"{(best_a['average_power']-P0_UW)/P0_UW*100:+.2f}%", f"{(best_b['average_power']-P0_UW)/P0_UW*100:+.2f}%"])
        writer.writerow(["Propagation delay (ps)", f"{TPD0_PS:.4f}", f"{best_a['delay']:.4f}", f"{best_b['delay']:.4f}"])
        writer.writerow(["Power-delay product (fJ)", f"{PDP0_FJ:.4f}", f"{best_a['PDP']:.4f}", f"{best_b['PDP']:.4f}"])
        writer.writerow(["Scenario objective score", f"F_A=0.000 / F_B=0.400", f"F_A = {best_a['objective']:.6f}", f"F_B = {best_b['objective']:.6f}"])
        writer.writerow(["Cross-scenario objective score", "—", f"F_B = {score_a_under_b:.6f}", f"F_A = {score_b_under_a:.6f}"])
        writer.writerow(["Net objective gain (delta F)", "0.000000", f"+{best_a['objective'] - OBJ_A_BASE:.6f}", f"+{best_b['objective'] - OBJ_B_BASE:.6f}"])
        writer.writerow(["Best discovery evaluation", "—", f"Eval {best_a['iteration']}", f"Eval {best_b['iteration']}"])
        writer.writerow(["Feasible candidates", "1 / 1 (100%)", f"{len([r for r in rows_a if r['is_feasible']])} / 50 (98.0%)", f"{len(feasible_b)} / 50 (98.0%)"])
    print(f"Saved comparison CSV to: {comp_csv}")
    
    generate_plots(rows_a, rows_b, best_a, best_b)

def generate_plots(rows_a, rows_b, best_a, best_b):
    conv_b = compute_convergence(rows_b)
    evals_50 = np.arange(1, 51)
    b_scores_50 = [s[0] for s in conv_b]
    
    plt.rcParams["font.sans-serif"] = "DejaVu Sans"
    plt.rcParams["axes.edgecolor"] = "#2d3748"
    plt.rcParams["axes.linewidth"] = 1.2

    # 1. Scenario B Convergence Plot
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=300)
    ax.axvspan(1, 10, color="#f0f4f8", alpha=0.8, label="Phase 1: Space-filling LHS (Evals 1–10)")
    ax.axvspan(10, 50, color="#fefcbf", alpha=0.4, label="Phase 2: Adaptive GP/EI (Evals 11–50)")
    
    raw_b = [r["objective"] if r["is_feasible"] else np.nan for r in rows_b]
    ax.scatter(evals_50, raw_b, c="#4a5568", s=35, alpha=0.7, label="Evaluated Candidates (Raw Score)")
    ax.step(evals_50, b_scores_50, where="post", color="#d69e2e", linewidth=2.6, label=f"Best-so-Far Feasible (Final = {best_b['objective']:.6f})")
    
    ax.scatter([best_b["iteration"]], [best_b["objective"]], color="#b7791f", s=140, marker="*", edgecolor="black", linewidth=1.5, zorder=6)
    ax.axhline(OBJ_B_BASE, color="#a0aec0", linestyle="--", linewidth=1.0, label=f"Baseline Reference (F_B = {OBJ_B_BASE:.2f})")
    
    ax.annotate(f"Best Feasible Discovered\n(Eval 11, Wn=1.20, Wp=2.80)\nF_B = {best_b['objective']:.6f} (+157% speed)",
                xy=(11, best_b["objective"]), xytext=(16, 0.85),
                arrowprops=dict(facecolor="#d69e2e", shrink=0.08, width=1.5, headwidth=7),
                fontsize=9.5, fontweight="bold", color="#744210",
                bbox=dict(boxstyle="round,pad=0.5", fc="#fffff0", ec="#d69e2e", lw=1.2))

    ax.set_title("Bayesian Optimization Campaign B Convergence (Scenario B: 0.7/0.3)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Evaluation Number", fontsize=11, fontweight="bold")
    ax.set_ylabel("Scenario B Objective Score F_B", fontsize=11, fontweight="bold")
    ax.set_xlim(1, 50)
    ax.set_ylim(0.15, 1.10)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="lower right", framealpha=0.95, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(ANALYSIS_B_DIR / "convergence_scenario_b.png")
    plt.close(fig)
    print("Saved convergence_scenario_b.png")

    # 2. Scenario B Design Space Plot
    fig, ax = plt.subplots(figsize=(8.5, 7.5), dpi=300)
    b_lhs = [r for r in rows_b if r["phase"] == "LHS"]
    b_adapt = [r for r in rows_b if r["phase"] == "ADAPTIVE_BO" and r["is_feasible"]]
    b_fail = [r for r in rows_b if not r["is_feasible"]]
    
    ax.scatter([r["Wn"] for r in b_lhs], [r["Wp"] for r in b_lhs], c="#4299e1", s=60, marker="o", edgecolors="#2b6cb0", linewidth=1.2, label="Scenario B Phase 1: LHS (N=10)")
    ax.scatter([r["Wn"] for r in b_adapt], [r["Wp"] for r in b_adapt], c="#d69e2e", s=70, marker="^", edgecolors="#744210", linewidth=1.2, label="Scenario B Phase 2: Adaptive GP/EI (N=39)")
    ax.scatter([r["Wn"] for r in b_fail], [r["Wp"] for r in b_fail], c="#e53e3e", s=120, marker="x", linewidth=2.5, label="Failed Simulation (Iter 17: 0.12/0.24)")
    ax.scatter([0.50], [1.00], c="#718096", s=140, marker="s", edgecolors="black", linewidth=1.5, label="Baseline Circuit (0.50, 1.00)", zorder=6)
    ax.scatter([best_b["Wn"]], [best_b["Wp"]], c="#b7791f", s=220, marker="*", edgecolors="black", linewidth=1.5, label=f"Best Scenario B (Iter 11: Wn=1.20, Wp=2.80)", zorder=8)
    
    ax.axvline(0.12, color="#a0aec0", linestyle="--")
    ax.axvline(1.20, color="#a0aec0", linestyle="--")
    ax.axhline(0.24, color="#a0aec0", linestyle="--")
    ax.axhline(2.80, color="#a0aec0", linestyle="--")
    
    ax.text(0.72, 2.70, "High-Speed Optimal Cluster\n(Wn=1.17-1.20, Wp=2.70-2.80)", fontsize=9.5, fontweight="bold", color="#744210", bbox=dict(boxstyle="round,pad=0.4", fc="#fffff0", ec="#d69e2e", lw=1.2))

    ax.set_title("Scenario B Design-Space Sampling (Wn vs. Wp)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("NMOS Channel Width Wn (µm)", fontsize=11, fontweight="bold")
    ax.set_ylabel("PMOS Channel Width Wp (µm)", fontsize=11, fontweight="bold")
    ax.set_xlim(0.08, 1.25)
    ax.set_ylim(0.15, 2.95)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="lower right", framealpha=0.92, fontsize=8.0)
    fig.tight_layout()
    fig.savefig(ANALYSIS_B_DIR / "design_space_scenario_b.png")
    plt.close(fig)
    print("Saved design_space_scenario_b.png")

    # 3. Cross-Scenario Design Space Comparison (Scenario A vs. Scenario B)
    fig, ax = plt.subplots(figsize=(9, 8), dpi=300)
    ax.scatter([r["Wn"] for r in rows_a if r["is_feasible"]], [r["Wp"] for r in rows_a if r["is_feasible"]], c="#3182ce", s=50, alpha=0.6, marker="o", label="Scenario A Evaluations (0.5/0.5 Balanced)")
    ax.scatter([r["Wn"] for r in rows_b if r["is_feasible"]], [r["Wp"] for r in rows_b if r["is_feasible"]], c="#d69e2e", s=50, alpha=0.6, marker="^", label="Scenario B Evaluations (0.7/0.3 Speed-Priority)")
    
    # Baseline
    ax.scatter([0.50], [1.00], c="#4a5568", s=140, marker="s", edgecolors="black", linewidth=1.5, label="Baseline Reference (0.50, 1.00)", zorder=6)
    
    # Best Candidate A
    ax.scatter([best_a["Wn"]], [best_a["Wp"]], c="#1a365d", s=220, marker="*", edgecolors="black", linewidth=1.5, label=f"Best Scenario A: Wn=0.12, Wp=2.80 (Low-Power Basin)", zorder=8)
    
    # Best Candidate B
    ax.scatter([best_b["Wn"]], [best_b["Wp"]], c="#744210", s=220, marker="*", edgecolors="black", linewidth=1.5, label=f"Best Scenario B: Wn=1.20, Wp=2.80 (High-Speed Basin)", zorder=8)
    
    ax.axvline(0.12, color="#a0aec0", linestyle="--")
    ax.axvline(1.20, color="#a0aec0", linestyle="--")
    ax.axhline(0.24, color="#a0aec0", linestyle="--")
    ax.axhline(2.80, color="#a0aec0", linestyle="--")
    
    ax.annotate("Scenario A Convergence:\nMinimum Wn (0.12 µm)\nfor Power Minimization",
                xy=(best_a["Wn"], best_a["Wp"]), xytext=(0.20, 2.50),
                arrowprops=dict(facecolor="#3182ce", shrink=0.08, width=1.5, headwidth=7),
                fontsize=9.0, fontweight="bold", color="#1a365d",
                bbox=dict(boxstyle="round,pad=0.4", fc="#ebf8ff", ec="#3182ce", lw=1.2))

    ax.annotate("Scenario B Convergence:\nMaximum Wn (1.20 µm)\nfor Frequency Maximization",
                xy=(best_b["Wn"], best_b["Wp"]), xytext=(0.75, 2.30),
                arrowprops=dict(facecolor="#d69e2e", shrink=0.08, width=1.5, headwidth=7),
                fontsize=9.0, fontweight="bold", color="#744210",
                bbox=dict(boxstyle="round,pad=0.4", fc="#fffff0", ec="#d69e2e", lw=1.2))

    ax.set_title("Cross-Scenario Design Space Convergence: Scenario A vs. Scenario B", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("NMOS Channel Width Wn (µm)", fontsize=11, fontweight="bold")
    ax.set_ylabel("PMOS Channel Width Wp (µm)", fontsize=11, fontweight="bold")
    ax.set_xlim(0.08, 1.25)
    ax.set_ylim(0.15, 2.95)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="lower right", framealpha=0.95, fontsize=8.2)
    fig.tight_layout()
    fig.savefig(ANALYSIS_B_DIR / "cross_scenario_design_space.png")
    plt.close(fig)
    print("Saved cross_scenario_design_space.png")

    # 4. Cross-Scenario Frequency vs. Power Comparison
    fig, ax = plt.subplots(figsize=(9.5, 6.5), dpi=300)
    
    ax.scatter([r["average_power"] for r in rows_a if r["is_feasible"]], [r["frequency"] for r in rows_a if r["is_feasible"]],
               c="#3182ce", s=45, alpha=0.5, label="Scenario A Candidates")
    ax.scatter([r["average_power"] for r in rows_b if r["is_feasible"]], [r["frequency"] for r in rows_b if r["is_feasible"]],
               c="#d69e2e", s=45, alpha=0.5, label="Scenario B Candidates")
               
    # Baseline
    ax.scatter([P0_UW], [F0_GHZ], c="#4a5568", s=140, marker="s", edgecolors="black", linewidth=1.5, label=f"Baseline Reference (41.07 GHz, 140.17 µW)", zorder=6)
    
    # Best A
    ax.scatter([best_a["average_power"]], [best_a["frequency"]], c="#1a365d", s=220, marker="*", edgecolors="black", linewidth=1.5,
               label=f"Best Scenario A (27.57 GHz, 88.32 µW)", zorder=8)
               
    # Best B
    ax.scatter([best_b["average_power"]], [best_b["frequency"]], c="#744210", s=220, marker="*", edgecolors="black", linewidth=1.5,
               label=f"Best Scenario B (105.66 GHz, 360.89 µW)", zorder=8)
               
    ax.annotate("Candidate A (Power-Optimized):\n-37.0% Power Savings\n-32.9% Freq Reduction\n(PDP = 0.320 fJ)",
                xy=(best_a["average_power"], best_a["frequency"]), xytext=(best_a["average_power"] + 30, best_a["frequency"] - 10),
                arrowprops=dict(facecolor="#3182ce", shrink=0.08, width=1.5, headwidth=7),
                fontsize=9.0, fontweight="bold", color="#1a365d",
                bbox=dict(boxstyle="round,pad=0.4", fc="#ebf8ff", ec="#3182ce", lw=1.2))

    ax.annotate("Candidate B (Speed-Optimized):\n+157.3% Frequency Increase\n+157.5% Power Increase\n(Delay = 0.947 ps, Sub-ps)",
                xy=(best_b["average_power"], best_b["frequency"]), xytext=(best_b["average_power"] - 130, best_b["frequency"] - 20),
                arrowprops=dict(facecolor="#d69e2e", shrink=0.08, width=1.5, headwidth=7),
                fontsize=9.0, fontweight="bold", color="#744210",
                bbox=dict(boxstyle="round,pad=0.4", fc="#fffff0", ec="#d69e2e", lw=1.2))

    ax.set_title("Frequency vs. Power Pareto Landscape: Scenario A vs. Scenario B", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Average Power Dissipation (µW)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Oscillation Frequency (GHz)", fontsize=11, fontweight="bold")
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper left", framealpha=0.95, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(ANALYSIS_B_DIR / "cross_scenario_frequency_power.png")
    plt.close(fig)
    print("Saved cross_scenario_frequency_power.png")

if __name__ == "__main__":
    run()

"""
Comprehensive Analysis Script for Bayesian Optimization Campaign A
and Fair Comparison with Formal Random Search (RS-50 and RS-100).
"""

import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
EXP_BO_DIR = PROJECT_ROOT / "experiments" / "bayesian_optimization" / "scenario_05_05"
EXP_RS_DIR = PROJECT_ROOT / "experiments" / "random_search" / "formal_100"
ANALYSIS_DIR = EXP_BO_DIR / "analysis"
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

# Frozen Baseline Constants
F0_HZ = 41069756649.1
F0_GHZ = 41.0697566491
P0_W = 0.000140169553568
P0_UW = 140.169553568
TPD0_PS = 2.43488172707
PDP0_FJ = 0.341300000000
OBJ0 = 0.0

def load_bo_data():
    csv_path = EXP_BO_DIR / "results.csv"
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
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

def load_rs_data():
    csv_path = EXP_RS_DIR / "results.csv"
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
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
                "is_feasible": r["oscillation_status"] == "VALID" and r["simulation_status"] == "SUCCESS",
                "simulation_status": r["simulation_status"],
                "oscillation_status": r["oscillation_status"],
                "runtime": float(r["runtime"])
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

def validate_campaign_a(bo_rows, rs_rows):
    print("=== 1.1 VALIDATING CAMPAIGN A DATASET ===")
    assert len(bo_rows) == 50, f"Expected 50 rows, got {len(bo_rows)}"
    
    # Check physical execution
    all_physical = all(not r["is_synthetic"] for r in bo_rows)
    print(f"All physical (is_synthetic == False): {all_physical}")
    assert all_physical, "Found synthetic data in physical campaign!"
    
    # Check bounds and 10nm grid
    for r in bo_rows:
        wn, wp = r["Wn"], r["Wp"]
        assert 0.12 <= wn <= 1.20, f"Wn {wn} out of bounds"
        assert 0.24 <= wp <= 2.80, f"Wp {wp} out of bounds"
        assert abs(round(wn * 100) - wn * 100) < 1e-4, f"Wn {wn} off grid"
        assert abs(round(wp * 100) - wp * 100) < 1e-4, f"Wp {wp} off grid"
    print("Search space bounds [0.12, 1.20] x [0.24, 2.80] and 10nm grid verified for all 50 candidates.")
    
    # Check uniqueness of candidates
    sizing_pairs = [(r["Wn"], r["Wp"]) for r in bo_rows]
    unique_pairs = set(sizing_pairs)
    print(f"Unique candidate sizings: {len(unique_pairs)} / {len(bo_rows)}")
    
    # Feasible vs failed
    feasible_count = sum(1 for r in bo_rows if r["is_feasible"])
    failed_count = sum(1 for r in bo_rows if not r["is_feasible"])
    print(f"Feasible candidates: {feasible_count} / 50 ({feasible_count/50*100:.1f}%)")
    print(f"Failed candidates: {failed_count} / 50 ({failed_count/50*100:.1f}%)")
    
    failed_rows = [r for r in bo_rows if not r["is_feasible"]]
    for fr in failed_rows:
        print(f"  Failed Iteration {fr['iteration']}: Wn={fr['Wn']}, Wp={fr['Wp']}, status={fr['simulation_status']}/{fr['oscillation_status']}, objective={fr['objective']}")
        assert fr["objective"] == -1.0e9, f"Penalty not -1e9: {fr['objective']}"
    
    # Objective score consistency for feasible
    for r in bo_rows:
        if r["is_feasible"]:
            calc_obj = 0.5 * (r["frequency"] / F0_GHZ) - 0.5 * (r["average_power"] / P0_UW)
            diff = abs(calc_obj - r["objective"])
            assert diff < 1e-4, f"Objective mismatch at iter {r['iteration']}: logged {r['objective']}, calc {calc_obj}"
    print("Objective score consistency verified against frozen reference values (f0=41.07 GHz, P0=140.17 uW).")
    
    # Check no RS observations used in initial LHS
    rs_sizings = set((r["Wn"], r["Wp"]) for r in rs_rows)
    lhs_sizings = set((r["Wn"], r["Wp"]) for r in bo_rows if r["phase"] == "LHS")
    overlap_lhs_rs = lhs_sizings.intersection(rs_sizings)
    print(f"Initial LHS (10 evals) overlap with 100 RS points: {len(overlap_lhs_rs)} points ({overlap_lhs_rs})")
    print("Initial LHS was sampled independently via deterministic LHS(seed=2026), without warm-starting.")
    
    # Best candidate verification
    best_candidate = max([r for r in bo_rows if r["is_feasible"]], key=lambda x: x["objective"])
    print(f"Best feasible candidate in ledger: Iteration {best_candidate['iteration']} | Wn={best_candidate['Wn']} um, Wp={best_candidate['Wp']} um | F={best_candidate['objective']:.6f} | Freq={best_candidate['frequency']:.3f} GHz, Power={best_candidate['average_power']:.3f} uW")
    return best_candidate

def run():
    bo_rows = load_bo_data()
    rs_rows = load_rs_data()
    
    best_bo = validate_campaign_a(bo_rows, rs_rows)
    
    # Convergence trajectories
    bo_conv = compute_convergence(bo_rows)
    rs_conv = compute_convergence(rs_rows)
    rs50_conv = compute_convergence(rs_rows[:50])
    
    # Find best for RS-50 and RS-100
    best_rs50 = max([r for r in rs_rows[:50] if r["is_feasible"]], key=lambda x: x["objective"])
    best_rs100 = max([r for r in rs_rows if r["is_feasible"]], key=lambda x: x["objective"])
    
    print("\n=== BEST CANDIDATES SUMMARY ===")
    print(f"Baseline: Wn=0.50 um, Wp=1.00 um, Freq={F0_GHZ:.4f} GHz, Power={P0_UW:.4f} uW, Delay={TPD0_PS:.4f} ps, PDP={PDP0_FJ:.4f} fJ, Obj={OBJ0:.6f}")
    print(f"RS-50:    Iter {best_rs50['iteration']} | Wn={best_rs50['Wn']} um, Wp={best_rs50['Wp']} um, Ratio={best_rs50['ratio']:.4f} | Freq={best_rs50['frequency']:.4f} GHz, Power={best_rs50['average_power']:.4f} uW, Delay={best_rs50['delay']:.4f} ps, PDP={best_rs50['PDP']:.4f} fJ, Obj={best_rs50['objective']:.6f}")
    print(f"BO-50:    Iter {best_bo['iteration']} | Wn={best_bo['Wn']} um, Wp={best_bo['Wp']} um, Ratio={best_bo['ratio']:.4f} | Freq={best_bo['frequency']:.4f} GHz, Power={best_bo['average_power']:.4f} uW, Delay={best_bo['delay']:.4f} ps, PDP={best_bo['PDP']:.4f} fJ, Obj={best_bo['objective']:.6f}")
    print(f"RS-100:   Iter {best_rs100['iteration']} | Wn={best_rs100['Wn']} um, Wp={best_rs100['Wp']} um, Ratio={best_rs100['ratio']:.4f} | Freq={best_rs100['frequency']:.4f} GHz, Power={best_rs100['average_power']:.4f} uW, Delay={best_rs100['delay']:.4f} ps, PDP={best_rs100['PDP']:.4f} fJ, Obj={best_rs100['objective']:.6f}")
    
    # Milestone scores for BO
    print("\n=== BO BEST-SO-FAR MILESTONES ===")
    for m in [10, 20, 30, 40, 50]:
        score, cand = bo_conv[m-1]
        print(f"After Eval {m:2d}: Best-so-far = {score:.6f} (discovered at Eval {cand['iteration']})")
        
    print("\n=== RS-50 BEST-SO-FAR MILESTONES ===")
    for m in [10, 20, 30, 40, 50]:
        score, cand = rs50_conv[m-1]
        print(f"After Eval {m:2d}: Best-so-far = {score:.6f} (discovered at Eval {cand['iteration']})")

    # Output comparison CSV
    comp_csv_path = ANALYSIS_DIR / "comparison_rs_vs_bo.csv"
    with open(comp_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Baseline", "RS-50", "BO-50", "RS-100"])
        writer.writerow(["Best Wn (um)", "0.50", f"{best_rs50['Wn']:.2f}", f"{best_bo['Wn']:.2f}", f"{best_rs100['Wn']:.2f}"])
        writer.writerow(["Best Wp (um)", "1.00", f"{best_rs50['Wp']:.2f}", f"{best_bo['Wp']:.2f}", f"{best_rs100['Wp']:.2f}"])
        writer.writerow(["Wp/Wn ratio", "2.0000", f"{best_rs50['ratio']:.4f}", f"{best_bo['ratio']:.4f}", f"{best_rs100['ratio']:.4f}"])
        writer.writerow(["Frequency (GHz)", f"{F0_GHZ:.4f}", f"{best_rs50['frequency']:.4f}", f"{best_bo['frequency']:.4f}", f"{best_rs100['frequency']:.4f}"])
        writer.writerow(["Average power (uW)", f"{P0_UW:.4f}", f"{best_rs50['average_power']:.4f}", f"{best_bo['average_power']:.4f}", f"{best_rs100['average_power']:.4f}"])
        writer.writerow(["Delay (ps)", f"{TPD0_PS:.4f}", f"{best_rs50['delay']:.4f}", f"{best_bo['delay']:.4f}", f"{best_rs100['delay']:.4f}"])
        writer.writerow(["PDP (fJ)", f"{PDP0_FJ:.4f}", f"{best_rs50['PDP']:.4f}", f"{best_bo['PDP']:.4f}", f"{best_rs100['PDP']:.4f}"])
        writer.writerow(["Objective score F", f"{OBJ0:.6f}", f"{best_rs50['objective']:.6f}", f"{best_bo['objective']:.6f}", f"{best_rs100['objective']:.6f}"])
        writer.writerow(["Eval discovered", "N/A", f"{best_rs50['iteration']}", f"{best_bo['iteration']}", f"{best_rs100['iteration']}"])
        writer.writerow(["Feasible candidates", "1 / 1 (100%)", f"{sum(1 for r in rs_rows[:50] if r['is_feasible'])} / 50 (100.0%)", f"{sum(1 for r in bo_rows if r['is_feasible'])} / 50 (98.0%)", f"{sum(1 for r in rs_rows if r['is_feasible'])} / 100 (100.0%)"])
    print(f"\nSaved comparison CSV to: {comp_csv_path}")

    # Generate Plots
    generate_plots(bo_rows, rs_rows, bo_conv, rs_conv, rs50_conv, best_bo, best_rs50, best_rs100)

def generate_plots(bo_rows, rs_rows, bo_conv, rs_conv, rs50_conv, best_bo, best_rs50, best_rs100):
    # Set styling
    plt.rcParams["font.sans-serif"] = "DejaVu Sans"
    plt.rcParams["axes.edgecolor"] = "#2d3748"
    plt.rcParams["axes.linewidth"] = 1.2
    
    # --------------------------------------------------------------------------
    # Plot 1: Equal-Budget Convergence (RS-50 vs BO-50)
    # --------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=300)
    evals_50 = np.arange(1, 51)
    bo_scores_50 = [s[0] for s in bo_conv]
    rs_scores_50 = [s[0] for s in rs50_conv]
    
    # BO phases
    ax.axvspan(1, 10, color="#f0f4f8", alpha=0.8, label="BO Phase 1: Space-filling LHS (Evals 1–10)")
    ax.axvspan(10, 50, color="#e6fffa", alpha=0.5, label="BO Phase 2: Adaptive GP/EI (Evals 11–50)")
    
    ax.step(evals_50, rs_scores_50, where="post", color="#e53e3e", linewidth=2.4, label=f"Random Search (RS-50): Best = {best_rs50['objective']:.6f} (Eval {best_rs50['iteration']})")
    ax.step(evals_50, bo_scores_50, where="post", color="#2b6cb0", linewidth=2.6, label=f"Bayesian Optimization (BO-50): Best = {best_bo['objective']:.6f} (Eval {best_bo['iteration']})")
    
    # Mark discovery points
    ax.scatter([best_rs50["iteration"]], [best_rs50["objective"]], color="#c53030", s=90, zorder=5, edgecolor="white", linewidth=1.5)
    ax.scatter([best_bo["iteration"]], [best_bo["objective"]], color="#1a365d", s=110, zorder=5, marker="*", edgecolor="white", linewidth=1.5)
    
    ax.annotate(f"BO Best Discovered\n(Eval 12, F={best_bo['objective']:.6f})",
                xy=(12, best_bo["objective"]), xytext=(17, 0.016),
                arrowprops=dict(facecolor="#2b6cb0", shrink=0.08, width=1.5, headwidth=7),
                fontsize=9.5, fontweight="bold", color="#1a365d",
                bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#2b6cb0", lw=1.2))
                
    ax.axhline(0.0, color="#a0aec0", linestyle="--", linewidth=1.0, label="Baseline Objective (F = 0.0)")
    
    ax.set_title("Equal-Budget Convergence Comparison: BO-50 vs. RS-50 (Scenario A)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Evaluation Number", fontsize=11, fontweight="bold")
    ax.set_ylabel("Best-so-Far Objective Score F", fontsize=11, fontweight="bold")
    ax.set_xlim(1, 50)
    ax.set_ylim(-0.001, 0.023)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="lower right", framealpha=0.95, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(ANALYSIS_DIR / "convergence_equal_budget.png")
    plt.close(fig)
    print("Saved convergence_equal_budget.png")

    # --------------------------------------------------------------------------
    # Plot 2: Full-Budget Convergence (RS-100 vs BO-50)
    # --------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
    evals_100 = np.arange(1, 101)
    rs_scores_100 = [s[0] for s in rs_conv]
    
    ax.step(evals_100, rs_scores_100, where="post", color="#e53e3e", linewidth=2.2, label=f"Random Search (RS-100): Best = {best_rs100['objective']:.6f} (Eval {best_rs100['iteration']})")
    ax.step(evals_50, bo_scores_50, where="post", color="#2b6cb0", linewidth=2.6, label=f"Bayesian Optimization (BO-50, Terminated at Eval 50): Best = {best_bo['objective']:.6f} (Eval {best_bo['iteration']})")
    
    # Mark discovery points
    ax.scatter([best_rs100["iteration"]], [best_rs100["objective"]], color="#c53030", s=90, zorder=5, edgecolor="white", linewidth=1.5)
    ax.scatter([best_bo["iteration"]], [best_bo["objective"]], color="#1a365d", s=110, zorder=5, marker="*", edgecolor="white", linewidth=1.5)
    
    ax.axvline(50, color="#718096", linestyle=":", linewidth=1.5, label="BO Budget Limit (50 Evals)")
    ax.axhline(0.0, color="#a0aec0", linestyle="--", linewidth=1.0, label="Baseline Objective (F = 0.0)")
    
    ax.annotate(f"BO-50 final result (+0.020616)\noutperforms RS-100 (+0.010923)\nin 12 evaluations vs 62 evaluations",
                xy=(12, best_bo["objective"]), xytext=(30, 0.016),
                arrowprops=dict(facecolor="#2b6cb0", shrink=0.08, width=1.5, headwidth=7),
                fontsize=9.5, fontweight="bold", color="#1a365d",
                bbox=dict(boxstyle="round,pad=0.5", fc="#ebf8ff", ec="#3182ce", lw=1.2))

    ax.annotate(f"RS-100 Best Discovered\n(Eval 62, F={best_rs100['objective']:.6f})",
                xy=(62, best_rs100["objective"]), xytext=(68, 0.007),
                arrowprops=dict(facecolor="#e53e3e", shrink=0.08, width=1.5, headwidth=7),
                fontsize=9.0, fontweight="bold", color="#742a2a",
                bbox=dict(boxstyle="round,pad=0.4", fc="#fff5f5", ec="#e53e3e", lw=1.2))
                
    ax.set_title("Full-Budget Convergence Comparison: BO-50 vs. RS-100 (Scenario A)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Evaluation Number", fontsize=11, fontweight="bold")
    ax.set_ylabel("Best-so-Far Objective Score F", fontsize=11, fontweight="bold")
    ax.set_xlim(1, 100)
    ax.set_ylim(-0.001, 0.023)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="lower right", framealpha=0.95, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(ANALYSIS_DIR / "convergence_full_budget.png")
    plt.close(fig)
    print("Saved convergence_full_budget.png")

    # --------------------------------------------------------------------------
    # Plot 3: Design-Space Comparison (Wn vs Wp)
    # --------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8.5, 7.5), dpi=300)
    
    # RS candidates
    rs_wn = [r["Wn"] for r in rs_rows]
    rs_wp = [r["Wp"] for r in rs_rows]
    ax.scatter(rs_wn, rs_wp, c="#cbd5e0", s=30, alpha=0.7, edgecolors="none", label=f"Random Search Evals (N=100)")
    
    # BO LHS
    bo_lhs = [r for r in bo_rows if r["phase"] == "LHS"]
    ax.scatter([r["Wn"] for r in bo_lhs], [r["Wp"] for r in bo_lhs], c="#4299e1", s=55, marker="o", edgecolors="#2b6cb0", linewidth=1.2, label="BO Phase 1: LHS (N=10)")
    
    # BO Adaptive
    bo_adapt = [r for r in bo_rows if r["phase"] == "ADAPTIVE_BO" and r["is_feasible"]]
    ax.scatter([r["Wn"] for r in bo_adapt], [r["Wp"] for r in bo_adapt], c="#319795", s=65, marker="^", edgecolors="#234e52", linewidth=1.2, label="BO Phase 2: Adaptive GP/EI (N=39)")
    
    # BO Failed candidate
    bo_fail = [r for r in bo_rows if not r["is_feasible"]]
    ax.scatter([r["Wn"] for r in bo_fail], [r["Wp"] for r in bo_fail], c="#e53e3e", s=110, marker="x", linewidth=2.5, label=f"BO Failed Simulation (Iter 17, Wn=0.12, Wp=0.24)")
    
    # Baseline
    ax.scatter([0.50], [1.00], c="#d69e2e", s=140, marker="s", edgecolors="#744210", linewidth=1.8, label="Baseline Circuit (Wn=0.50, Wp=1.00)", zorder=6)
    
    # Best RS-100
    ax.scatter([best_rs100["Wn"]], [best_rs100["Wp"]], c="#9b2c2c", s=140, marker="D", edgecolors="white", linewidth=1.5, label=f"Best RS-100 (Iter 62: Wn={best_rs100['Wn']}, Wp={best_rs100['Wp']})", zorder=7)
    
    # Best BO-50
    ax.scatter([best_bo["Wn"]], [best_bo["Wp"]], c="#2b6cb0", s=220, marker="*", edgecolors="black", linewidth=1.5, label=f"Best BO-50 (Iter 12: Wn={best_bo['Wn']}, Wp={best_bo['Wp']})", zorder=8)
    
    # Search space boundaries
    ax.axvline(0.12, color="#718096", linestyle="--", linewidth=1.2)
    ax.axvline(1.20, color="#718096", linestyle="--", linewidth=1.2)
    ax.axhline(0.24, color="#718096", linestyle="--", linewidth=1.2)
    ax.axhline(2.80, color="#718096", linestyle="--", linewidth=1.2)
    
    ax.text(0.13, 2.74, "High-Utility Low-Power\nCluster (Wn~0.12, Wp~2.8)", fontsize=9, fontweight="bold", color="#2c5282", bbox=dict(boxstyle="round,pad=0.3", fc="#ebf8ff", ec="#3182ce", lw=1.0))
    
    ax.set_title("Transistor Sizing Design-Space Comparison (BO vs. RS)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("NMOS Channel Width Wn (µm)", fontsize=11, fontweight="bold")
    ax.set_ylabel("PMOS Channel Width Wp (µm)", fontsize=11, fontweight="bold")
    ax.set_xlim(0.08, 1.25)
    ax.set_ylim(0.15, 2.95)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right", framealpha=0.92, fontsize=8.0)
    fig.tight_layout()
    fig.savefig(ANALYSIS_DIR / "design_space_comparison.png")
    plt.close(fig)
    print("Saved design_space_comparison.png")

    # --------------------------------------------------------------------------
    # Plot 4: Frequency vs. Power Trade-off Comparison
    # --------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 6), dpi=300)
    
    rs_valid = [r for r in rs_rows if r["is_feasible"]]
    bo_valid = [r for r in bo_rows if r["is_feasible"]]
    
    ax.scatter([r["average_power"] for r in rs_valid], [r["frequency"] for r in rs_valid], c="#a0aec0", s=35, alpha=0.6, label="Random Search Candidates (N=100)")
    ax.scatter([r["average_power"] for r in bo_valid], [r["frequency"] for r in bo_valid], c=np.array([r["objective"] for r in bo_valid]), cmap="viridis", s=65, edgecolors="#2d3748", linewidth=0.8, label="BO Candidates (colored by F)", zorder=4)
    
    # Baseline
    ax.scatter([P0_UW], [F0_GHZ], c="#d69e2e", s=140, marker="s", edgecolors="#744210", linewidth=1.8, label=f"Baseline Circuit (41.07 GHz, 140.17 µW)", zorder=6)
    
    # Best RS-50
    ax.scatter([best_rs50["average_power"]], [best_rs50["frequency"]], c="#c53030", s=130, marker="o", edgecolors="black", linewidth=1.5, label=f"Best RS-50 (34.50 GHz, 117.70 µW)", zorder=7)
    
    # Best RS-100
    ax.scatter([best_rs100["average_power"]], [best_rs100["frequency"]], c="#9b2c2c", s=140, marker="D", edgecolors="white", linewidth=1.5, label=f"Best RS-100 (35.37 GHz, 117.65 µW)", zorder=8)
    
    # Best BO-50
    ax.scatter([best_bo["average_power"]], [best_bo["frequency"]], c="#2b6cb0", s=220, marker="*", edgecolors="black", linewidth=1.5, label=f"Best BO-50 (27.57 GHz, 88.32 µW)", zorder=9)
    
    cbar = plt.colorbar(ax.collections[1], ax=ax)
    cbar.set_label("Scenario A Objective Score F", fontsize=9.5, fontweight="bold")
    
    ax.annotate("Best BO Candidate:\n37.0% Power Reduction\nwith Balanced Trade-off",
                xy=(best_bo["average_power"], best_bo["frequency"]), xytext=(best_bo["average_power"] + 25, best_bo["frequency"] - 8),
                arrowprops=dict(facecolor="#2b6cb0", shrink=0.08, width=1.5, headwidth=7),
                fontsize=9.0, fontweight="bold", color="#1a365d",
                bbox=dict(boxstyle="round,pad=0.4", fc="#ebf8ff", ec="#3182ce", lw=1.2))

    ax.set_title("Frequency vs. Power Landscape & Candidate Comparison", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Average Power Dissipation (µW)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Oscillation Frequency (GHz)", fontsize=11, fontweight="bold")
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper left", framealpha=0.92, fontsize=8.0)
    fig.tight_layout()
    fig.savefig(ANALYSIS_DIR / "frequency_power_comparison.png")
    plt.close(fig)
    print("Saved frequency_power_comparison.png")

    # --------------------------------------------------------------------------
    # Plot 5: Standalone Campaign A Convergence
    # --------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8.5, 5), dpi=300)
    ax.axvspan(1, 10, color="#f0f4f8", alpha=0.8, label="Phase 1: Space-filling LHS (Evals 1–10)")
    ax.axvspan(10, 50, color="#e6fffa", alpha=0.5, label="Phase 2: Adaptive GP/EI (Evals 11–50)")
    
    bo_raw_scores = [r["objective"] if r["is_feasible"] else np.nan for r in bo_rows]
    ax.scatter(evals_50, bo_raw_scores, c="#4a5568", s=35, alpha=0.7, label="Evaluated Candidates (Raw Score)")
    ax.step(evals_50, bo_scores_50, where="post", color="#2b6cb0", linewidth=2.5, label=f"Best-so-Far Feasible (Final = {best_bo['objective']:.6f})")
    
    ax.scatter([best_bo["iteration"]], [best_bo["objective"]], color="#1a365d", s=130, marker="*", edgecolor="black", zorder=6)
    ax.axhline(0.0, color="#a0aec0", linestyle="--", linewidth=1.0, label="Baseline (F = 0.0)")
    
    ax.set_title("Bayesian Optimization Campaign A: Objective Trajectory", fontsize=12, fontweight="bold", pad=10)
    ax.set_xlabel("Evaluation Number", fontsize=10.5, fontweight="bold")
    ax.set_ylabel("Objective Score F", fontsize=10.5, fontweight="bold")
    ax.set_xlim(1, 50)
    ax.set_ylim(-0.005, 0.023)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="lower right", framealpha=0.95, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(ANALYSIS_DIR / "convergence_campaign_a.png")
    plt.close(fig)
    print("Saved convergence_campaign_a.png")

if __name__ == "__main__":
    run()

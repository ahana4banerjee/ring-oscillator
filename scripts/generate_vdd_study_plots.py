"""
Generate VDD Sensitivity Study Visualizations.
"""

import sys
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def generate_vdd_plots():
    csv_path = PROJECT_ROOT / "results" / "processed" / "experiment_log_vdd_study.csv"
    plots_dir = PROJECT_ROOT / "results" / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    df['vdd_volts'] = pd.to_numeric(df['vdd_volts'], errors='coerce')
    df['wn_um'] = pd.to_numeric(df['wn_um'], errors='coerce')
    df['wp_um'] = pd.to_numeric(df['wp_um'], errors='coerce')
    df['ratio_wp_wn'] = pd.to_numeric(df['ratio_wp_wn'], errors='coerce')
    df['freq_ghz'] = pd.to_numeric(df['freq_ghz'], errors='coerce')
    df['power_mw'] = pd.to_numeric(df['power_mw'], errors='coerce')
    df['delay_ps'] = pd.to_numeric(df['delay_ps'], errors='coerce')

    # 1. Plot 1: Success Rate vs VDD
    fig, ax = plt.subplots(figsize=(7, 5))
    vdd_vals = [1.2, 1.5, 1.8, 2.0]
    rates = []
    for v in vdd_vals:
        sub = df[df['vdd_volts'] == v]
        succ = len(sub[sub['status'] == 'SUCCESS'])
        rates.append((succ / len(sub)) * 100.0)

    ax.bar([str(v) + "V" for v in vdd_vals], rates, color=['#4e79a7', '#f28e2b', '#e15759', '#76b7b2'], width=0.5, edgecolor='black')
    ax.set_ylim(0, 100)
    ax.set_ylabel('Feasibility / Success Rate (%)', fontsize=11, fontweight='bold')
    ax.set_xlabel('Supply Voltage VDD (V)', fontsize=11, fontweight='bold')
    ax.set_title('Feasibility Success Rate Across Supply Voltages (N=20 Fixed Candidates)', fontsize=12, fontweight='bold')
    ax.grid(True, linestyle=':', alpha=0.6, axis='y')
    for i, r in enumerate(rates):
        ax.text(i, r + 2, f"{r:.0f}%", ha='center', fontweight='bold', fontsize=11)
    
    plt.tight_layout()
    p1 = plots_dir / "vdd_success_rate_comparison.png"
    plt.savefig(p1, dpi=300)
    plt.close()

    # 2. Plot 2: Performance Trends vs VDD for Common Feasible Candidates
    # Pick common candidates functional across multiple VDDs: e.g. 0.22/0.38, 0.28/0.55, 0.25/0.50, 0.24/0.46
    common_cands = [(0.22, 0.38), (0.28, 0.55), (0.25, 0.50), (0.24, 0.46)]
    fig, (ax_f, ax_p, ax_d) = plt.subplots(1, 3, figsize=(15, 4.5))

    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

    for idx, (wn, wp) in enumerate(common_cands):
        sub_c = df[(df['wn_um'] == wn) & (df['wp_um'] == wp) & (df['status'] == 'SUCCESS')]
        if not sub_c.empty:
            label = f"Wn={wn}u, Wp={wp}u"
            ax_f.plot(sub_c['vdd_volts'], sub_c['freq_ghz'], 'o-', label=label, color=colors[idx], lw=2, ms=7)
            ax_p.plot(sub_c['vdd_volts'], sub_c['power_mw'], 's-', label=label, color=colors[idx], lw=2, ms=7)
            ax_d.plot(sub_c['vdd_volts'], sub_c['delay_ps'], '^-', label=label, color=colors[idx], lw=2, ms=7)

    ax_f.set_title('Frequency vs VDD', fontweight='bold')
    ax_f.set_xlabel('VDD (V)', fontweight='bold')
    ax_f.set_ylabel('Frequency (GHz)', fontweight='bold')
    ax_f.grid(True, linestyle=':', alpha=0.6)
    ax_f.legend(fontsize=8)

    ax_p.set_title('Average Power vs VDD', fontweight='bold')
    ax_p.set_xlabel('VDD (V)', fontweight='bold')
    ax_p.set_ylabel('Power (mW)', fontweight='bold')
    ax_p.grid(True, linestyle=':', alpha=0.6)

    ax_d.set_title('Stage Delay vs VDD', fontweight='bold')
    ax_d.set_xlabel('VDD (V)', fontweight='bold')
    ax_d.set_ylabel('Propagation Delay (ps)', fontweight='bold')
    ax_d.grid(True, linestyle=':', alpha=0.6)

    plt.tight_layout()
    p2 = plots_dir / "vdd_performance_trends.png"
    plt.savefig(p2, dpi=300)
    plt.close()

    # 3. Plot 3: Search-space comparison across VDD (Wn vs Wp scatter faceted by VDD)
    fig, axes = plt.subplots(1, 4, figsize=(16, 4), sharex=True, sharey=True)

    for idx, v in enumerate(vdd_vals):
        ax_v = axes[idx]
        sub = df[df['vdd_volts'] == v]
        succ = sub[sub['status'] == 'SUCCESS']
        fail = sub[sub['status'] != 'SUCCESS']

        ax_v.scatter(fail['wn_um'], fail['wp_um'], color='#d9534f', marker='x', s=60, label='Infeasible')
        ax_v.scatter(succ['wn_um'], succ['wp_um'], color='#5cb85c', marker='o', s=100, edgecolors='black', label='Feasible')

        wn_line = np.linspace(0.18, 0.80, 50)
        ax_v.plot(wn_line, 2.0 * wn_line, '--', color='blue', alpha=0.5, label='Ratio=2.0')

        ax_v.set_title(f"VDD = {v:.1f} V (Yield: {len(succ)}/{len(sub)})", fontweight='bold')
        ax_v.set_xlabel('Wn (µm)', fontweight='bold')
        if idx == 0:
            ax_v.set_ylabel('Wp (µm)', fontweight='bold')
        ax_v.grid(True, linestyle=':', alpha=0.6)
        if idx == 0:
            ax_v.legend(fontsize=8, loc='upper left')

    plt.tight_layout()
    p3 = plots_dir / "vdd_search_space_comparison.png"
    plt.savefig(p3, dpi=300)
    plt.close()

    print(f"Generated Plot 1: {p1}")
    print(f"Generated Plot 2: {p2}")
    print(f"Generated Plot 3: {p3}")

if __name__ == "__main__":
    generate_vdd_plots()

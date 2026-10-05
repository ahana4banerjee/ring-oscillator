"""
Visualizer & Analytics Module.

Generates 2D scatter plots and diagnostic charts of search space evaluations,
highlighting feasible vs infeasible parameter regions, Wp/Wn ratios, and performance metrics.
"""

from pathlib import Path
from typing import Union, Optional
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np


def plot_search_space_characterization(csv_path: Union[str, Path],
                                        output_plot_path: Union[str, Path]) -> Path:
    """Generate search-space characterization scatter plot from experiment_log.csv."""
    csv_path = Path(csv_path)
    output_plot_path = Path(output_plot_path)
    output_plot_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)

    df['wn_um'] = pd.to_numeric(df['wn_um'], errors='coerce')
    df['wp_um'] = pd.to_numeric(df['wp_um'], errors='coerce')
    df['freq_ghz'] = pd.to_numeric(df['freq_ghz'], errors='coerce')
    df['objective_score'] = pd.to_numeric(df['objective_score'], errors='coerce')

    fig, ax = plt.subplots(figsize=(9, 7))

    success_df = df[df['status'] == 'SUCCESS']
    failed_df = df[df['status'] != 'SUCCESS']

    ax.scatter(failed_df['wn_um'], failed_df['wp_um'],
               color='#d9534f', marker='x', s=80, linewidths=2, label=f'Infeasible / NO_OSC (n={len(failed_df)})')

    ax.scatter(success_df['wn_um'], success_df['wp_um'],
               color='#5cb85c', marker='o', s=140, edgecolors='black', linewidths=1.5,
               label=f'Feasible / Oscillating (n={len(success_df)})')

    for _, row in success_df.iterrows():
        ax.annotate(f"Iter {int(row['iteration'])}\n{row['freq_ghz']:.1f}GHz",
                    (row['wn_um'], row['wp_um']),
                    xytext=(row['wn_um'] + 0.02, row['wp_um'] + 0.03),
                    fontsize=9, fontweight='bold',
                    arrowprops=dict(arrowstyle='->', lw=1, color='green'))

    wn_line = np.linspace(0.18, 0.80, 100)
    wp_line_2 = 2.0 * wn_line
    ax.plot(wn_line, wp_line_2, '--', color='blue', alpha=0.6, label='Reference Ratio Wp/Wn = 2.0')

    ax.set_xlim(0.15, 0.85)
    ax.set_ylim(0.30, 1.65)

    ax.set_xlabel('NMOS Width Wn (µm)', fontsize=12, fontweight='bold')
    ax.set_ylabel('PMOS Width Wp (µm)', fontsize=12, fontweight='bold')
    ax.set_title('Phase 5.4 Search-Space Characterization (20-Iteration Random Search)', fontsize=13, fontweight='bold', pad=12)

    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend(loc='upper left', frameon=True, facecolor='white', framealpha=0.9)

    plt.tight_layout()
    plt.savefig(output_plot_path, dpi=300)
    plt.close()

    return output_plot_path


def plot_focused_validation_results(csv_path: Union[str, Path],
                                   output_scatter_path: Union[str, Path],
                                   output_ratio_path: Union[str, Path]) -> tuple[Path, Path]:
    """Generate Phase 5.4A 2D scatter plot and ratio distribution analysis plot.

    Args:
        csv_path: Path to experiment_log_focused_100iter.csv
        output_scatter_path: Path for 2D Wn vs Wp scatter PNG
        output_ratio_path: Path for Wp/Wn ratio analysis PNG
    """
    csv_path = Path(csv_path)
    output_scatter_path = Path(output_scatter_path)
    output_ratio_path = Path(output_ratio_path)

    output_scatter_path.parent.mkdir(parents=True, exist_ok=True)
    output_ratio_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    df['wn_um'] = pd.to_numeric(df['wn_um'], errors='coerce')
    df['wp_um'] = pd.to_numeric(df['wp_um'], errors='coerce')
    df['ratio_wp_wn'] = pd.to_numeric(df['ratio_wp_wn'], errors='coerce')
    df['score_config_b'] = pd.to_numeric(df['score_config_b'], errors='coerce')
    df['freq_ghz'] = pd.to_numeric(df['freq_ghz'], errors='coerce')

    success_df = df[df['status'] == 'SUCCESS']
    failed_df = df[df['status'] != 'SUCCESS']

    # 1. 2D Scatter Plot Wn vs Wp
    fig, ax = plt.subplots(figsize=(9, 7))

    ax.scatter(failed_df['wn_um'], failed_df['wp_um'],
               color='#d9534f', marker='x', s=50, alpha=0.7, label=f'NO_OSCILLATION (n={len(failed_df)})')

    sc = ax.scatter(success_df['wn_um'], success_df['wp_um'],
                    c=success_df['score_config_b'], cmap='viridis', marker='o', s=120,
                    edgecolors='black', linewidths=1.2, label=f'SUCCESS / Valid (n={len(success_df)})')

    cbar = plt.colorbar(sc, ax=ax)
    cbar.set_label('Config B Objective Score', fontsize=11, fontweight='bold')

    wn_line = np.linspace(0.18, 0.50, 100)
    ax.plot(wn_line, 2.0 * wn_line, '--', color='red', alpha=0.7, label='Ratio Wp/Wn = 2.0')
    ax.plot(wn_line, 1.5 * wn_line, ':', color='orange', alpha=0.7, label='Ratio Wp/Wn = 1.5')

    ax.set_xlim(0.16, 0.52)
    ax.set_ylim(0.32, 1.25)
    ax.set_xlabel('NMOS Width Wn (µm)', fontsize=12, fontweight='bold')
    ax.set_ylabel('PMOS Width Wp (µm)', fontsize=12, fontweight='bold')
    ax.set_title('Phase 5.4A Focused Search-Space Validation (100 Iterations, Seed=2026)', fontsize=13, fontweight='bold', pad=12)
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend(loc='upper left', frameon=True, facecolor='white', framealpha=0.9)

    plt.tight_layout()
    plt.savefig(output_scatter_path, dpi=300)
    plt.close()

    # 2. Ratio Analysis Plot (Wp/Wn Ratio vs Config B Score & Status Histogram)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # Ax1: Ratio vs Config B Score for successful points
    ax1.scatter(success_df['ratio_wp_wn'], success_df['score_config_b'],
                color='#2b5c8f', s=90, edgecolors='black', alpha=0.9)
    ax1.axvline(2.0, color='red', linestyle='--', label='Theoretical Ideal Ratio Wp/Wn = 2.0')
    ax1.set_xlabel('PMOS to NMOS Width Ratio (Wp / Wn)', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Config B Objective Score', fontsize=11, fontweight='bold')
    ax1.set_title('Feasible Candidates: Ratio vs Objective Score', fontsize=12, fontweight='bold')
    ax1.grid(True, linestyle=':', alpha=0.6)
    ax1.legend(loc='upper right')

    # Ax2: Ratio Distribution Histogram (Success vs Failed)
    bins = np.linspace(0.5, 8.5, 25)
    ax2.hist([failed_df['ratio_wp_wn'], success_df['ratio_wp_wn']], bins=bins,
             stacked=True, color=['#d9534f', '#5cb85c'], label=['Infeasible (NO_OSC)', 'Feasible (SUCCESS)'],
             edgecolor='black', alpha=0.85)
    ax2.axvline(2.0, color='red', linestyle='--', label='Ratio Wp/Wn = 2.0')
    ax2.set_xlabel('PMOS to NMOS Width Ratio (Wp / Wn)', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Candidate Count', fontsize=11, fontweight='bold')
    ax2.set_title('Wp/Wn Ratio Distribution of 100 Samples', fontsize=12, fontweight='bold')
    ax2.grid(True, linestyle=':', alpha=0.6)
    ax2.legend(loc='upper right')

    plt.tight_layout()
    plt.savefig(output_ratio_path, dpi=300)
    plt.close()

    return output_scatter_path, output_ratio_path

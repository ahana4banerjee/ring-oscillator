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
    """Generate search-space characterization scatter plot from experiment_log.csv.

    Args:
        csv_path: Path to experiment_log.csv file.
        output_plot_path: Path to save output figure PNG.

    Returns:
        Path pointing to saved PNG figure.
    """
    csv_path = Path(csv_path)
    output_plot_path = Path(output_plot_path)
    output_plot_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)

    # Convert numeric columns
    df['wn_um'] = pd.to_numeric(df['wn_um'], errors='coerce')
    df['wp_um'] = pd.to_numeric(df['wp_um'], errors='coerce')
    df['freq_ghz'] = pd.to_numeric(df['freq_ghz'], errors='coerce')
    df['objective_score'] = pd.to_numeric(df['objective_score'], errors='coerce')

    fig, ax = plt.subplots(figsize=(9, 7))

    # Separate success vs failure
    success_df = df[df['status'] == 'SUCCESS']
    failed_df = df[df['status'] != 'SUCCESS']

    # Plot failed points
    ax.scatter(failed_df['wn_um'], failed_df['wp_um'],
               color='#d9534f', marker='x', s=80, linewidths=2, label=f'Infeasible / NO_OSC (n={len(failed_df)})')

    # Plot successful points
    sc = ax.scatter(success_df['wn_um'], success_df['wp_um'],
                    color='#5cb85c', marker='o', s=140, edgecolors='black', linewidths=1.5,
                    label=f'Feasible / Oscillating (n={len(success_df)})')

    # Annotate successful points with iteration index and frequency
    for _, row in success_df.iterrows():
        ax.annotate(f"Iter {int(row['iteration'])}\n{row['freq_ghz']:.1f}GHz",
                    (row['wn_um'], row['wp_um']),
                    xytext=(row['wn_um'] + 0.02, row['wp_um'] + 0.03),
                    fontsize=9, fontweight='bold',
                    arrowprops=dict(arrowstyle='->', lw=1, color='green'))

    # Draw reference ratio line Wp/Wn = 2.0
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

"""
Generate Phase 5.4A Focused Validation Plot Artifacts.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.visualizer import plot_focused_validation_results

if __name__ == "__main__":
    csv_file = PROJECT_ROOT / "results" / "processed" / "experiment_log_focused_100iter.csv"
    scatter_file = PROJECT_ROOT / "results" / "plots" / "phase5_4a_search_space.png"
    ratio_file = PROJECT_ROOT / "results" / "plots" / "phase5_4a_ratio_analysis.png"

    p1, p2 = plot_focused_validation_results(csv_file, scatter_file, ratio_file)
    print(f"Phase 5.4A Scatter Plot saved: {p1}")
    print(f"Phase 5.4A Ratio Plot saved  : {p2}")

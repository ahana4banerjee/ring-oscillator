"""
Generate Phase 5.4 Search Space Scatter Plot.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.visualizer import plot_search_space_characterization

if __name__ == "__main__":
    csv_file = PROJECT_ROOT / "results" / "processed" / "experiment_log.csv"
    plot_file = PROJECT_ROOT / "results" / "plots" / "phase5_4_search_space.png"

    saved_path = plot_search_space_characterization(csv_file, plot_file)
    print(f"Phase 5.4 plot generated successfully: {saved_path}")

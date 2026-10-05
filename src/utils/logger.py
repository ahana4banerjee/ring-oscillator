"""
Experiment Logger Module.

Handles structured CSV iteration logging and JSON summary artifact generation
for optimization campaign tracking.
"""

import csv
import json
import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union, List


class ExperimentLogger:
    """Manages atomic CSV log appending and JSON run summary export."""

    CSV_HEADERS = [
        "experiment_id",
        "iteration",
        "method",
        "timestamp",
        "wn_um",
        "wp_um",
        "status",
        "freq_ghz",
        "power_mw",
        "delay_ps",
        "objective_score",
        "sim_time_sec"
    ]

    def __init__(self,
                 csv_path: Union[str, Path],
                 summary_path: Optional[Union[str, Path]] = None,
                 experiment_id: str = "exp_001",
                 method: str = "RANDOM_SEARCH"):
        """
        Args:
            csv_path: Destination path for experiment_log.csv file.
            summary_path: Destination path for run_summary.json file.
            experiment_id: Unique string identifier for the campaign run.
            method: Optimization method name ("RANDOM_SEARCH" or "BAYESIAN_OPT").
        """
        self.csv_path = Path(csv_path)
        self.summary_path = Path(summary_path) if summary_path else None
        self.experiment_id = experiment_id
        self.method = method

        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        if self.summary_path:
            self.summary_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize CSV header if file does not exist
        if not self.csv_path.exists() or self.csv_path.stat().st_size == 0:
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_HEADERS)

    def log_iteration(self,
                      iteration: int,
                      candidate: Dict[str, float],
                      result: Dict[str, Any]) -> Dict[str, Any]:
        """Append a single evaluation iteration record to the CSV file.

        Args:
            iteration: Iteration index (0-indexed).
            candidate: Dictionary containing 'wn' and 'wp' (in meters).
            result: Dictionary containing evaluation output payload.

        Returns:
            Dictionary row payload written to CSV.
        """
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        wn_um = candidate["wn"] * 1e6
        wp_um = candidate["wp"] * 1e6

        metrics = result.get("metrics", {})
        status = result.get("status", "UNKNOWN")
        obj_score = result.get("objective_score", -1.0e9)
        sim_time = result.get("sim_time_sec", 0.0)

        freq_ghz = metrics.get("freq_ghz") if metrics.get("is_oscillating") else None
        power_mw = metrics.get("power_mw") if metrics.get("is_oscillating") else None
        delay_ps = metrics.get("delay_ps") if metrics.get("is_oscillating") else None

        row = [
            self.experiment_id,
            iteration,
            self.method,
            timestamp,
            f"{wn_um:.4f}",
            f"{wp_um:.4f}",
            status,
            f"{freq_ghz:.4f}" if freq_ghz is not None else "NaN",
            f"{power_mw:.4f}" if power_mw is not None else "NaN",
            f"{delay_ps:.4f}" if delay_ps is not None else "NaN",
            f"{obj_score:.6f}",
            f"{sim_time:.3f}"
        ]

        with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(row)

        record = {
            "experiment_id": self.experiment_id,
            "iteration": iteration,
            "method": self.method,
            "timestamp": timestamp,
            "wn_um": wn_um,
            "wp_um": wp_um,
            "status": status,
            "freq_ghz": freq_ghz,
            "power_mw": power_mw,
            "delay_ps": delay_ps,
            "objective_score": obj_score,
            "sim_time_sec": sim_time
        }
        return record

    def write_summary(self,
                      total_evaluations: int,
                      best_candidate_record: Optional[Dict[str, Any]] = None,
                      config_snapshot: Optional[Dict[str, Any]] = None) -> Path:
        """Write structured JSON summary artifact at campaign completion."""
        if not self.summary_path:
            raise ValueError("summary_path was not configured for this logger instance")

        summary = {
            "experiment_id": self.experiment_id,
            "method": self.method,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "total_evaluations": total_evaluations,
            "best_candidate": best_candidate_record,
            "config_snapshot": config_snapshot or {}
        }

        with open(self.summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)

        return self.summary_path

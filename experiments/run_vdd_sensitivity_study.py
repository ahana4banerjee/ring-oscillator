"""
Phase 5.4B: Controlled Supply Voltage (VDD) Sensitivity Study.

Evaluates a fixed, deterministic set of 20 Wn/Wp candidates across 4 representative
supply voltages (VDD = 1.2V, 1.5V, 1.8V, 2.0V) to characterize oscillation feasibility,
frequency/power/delay sensitivity, and search-space stability prior to Phase 5.5.
"""

import sys
import csv
import json
import yaml
import time
import datetime
from pathlib import Path
from typing import Dict, Any, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ltspice.parameterizer import NetlistParameterizer
from src.simulation.runner import LTspiceRunner
from src.evaluation.extractor import MetricExtractor
from src.evaluation.objective import ObjectiveEvaluator

# Fixed, deterministic list of N=20 candidates representing Phase 5.3/5.4/5.4A observations
FIXED_CANDIDATES = [
    # A. Previously successful candidates
    {"wn_um": 0.28, "wp_um": 0.55, "category": "A_Success_Iter03_5.3"},
    {"wn_um": 0.29, "wp_um": 0.59, "category": "A_Success_Iter08_5.3"},
    {"wn_um": 0.22, "wp_um": 0.38, "category": "A_Success_Iter96_5.4A_Best"},
    {"wn_um": 0.47, "wp_um": 0.94, "category": "A_Success_Iter56_5.4A"},
    {"wn_um": 0.48, "wp_um": 0.94, "category": "A_Success_Iter60_5.4A"},
    # B. Low-ratio candidates (Ratio < 1.5)
    {"wn_um": 0.70, "wp_um": 0.62, "category": "B_LowRatio_0.89"},
    {"wn_um": 0.56, "wp_um": 0.53, "category": "B_LowRatio_0.95"},
    {"wn_um": 0.55, "wp_um": 0.42, "category": "B_LowRatio_0.76"},
    {"wn_um": 0.48, "wp_um": 0.41, "category": "B_LowRatio_0.85"},
    # C. Ratio-near-2 candidates (1.5 <= Ratio <= 2.5)
    {"wn_um": 0.25, "wp_um": 0.50, "category": "C_RatioNear2_2.00"},
    {"wn_um": 0.24, "wp_um": 0.46, "category": "C_RatioNear2_1.92"},
    {"wn_um": 0.31, "wp_um": 0.49, "category": "C_RatioNear2_1.58"},
    {"wn_um": 0.21, "wp_um": 0.50, "category": "C_RatioNear2_2.38"},
    {"wn_um": 0.36, "wp_um": 0.81, "category": "C_RatioNear2_2.25"},
    # D. Higher-ratio candidates (Ratio > 2.5)
    {"wn_um": 0.22, "wp_um": 1.43, "category": "D_HighRatio_6.50"},
    {"wn_um": 0.19, "wp_um": 1.56, "category": "D_HighRatio_8.21"},
    {"wn_um": 0.37, "wp_um": 1.01, "category": "D_HighRatio_2.73"},
    {"wn_um": 0.30, "wp_um": 1.00, "category": "D_HighRatio_3.33"},
    # E. Larger-width candidates (Wn >= 0.5um)
    {"wn_um": 0.63, "wp_um": 1.10, "category": "E_LargeWidth_0.63"},
    {"wn_um": 0.78, "wp_um": 1.36, "category": "E_LargeWidth_0.78"}
]

VDD_TEST_VALUES = [1.2, 1.5, 1.8, 2.0]


def run_vdd_sensitivity_study(config_path: Path):
    """Execute controlled VDD sensitivity experiment across 20 candidates and 4 VDD values (80 total runs)."""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    template_path = PROJECT_ROOT / config["circuit"]["template_netlist"]
    ltspice_exe = Path(config["simulation"]["ltspice_executable"])
    timeout_sec = float(config["simulation"]["timeout_seconds"])

    parameterizer = NetlistParameterizer(template_path)
    runner = LTspiceRunner(ltspice_exe, timeout_seconds=timeout_sec)
    extractor = MetricExtractor(stages=config["circuit"]["stages"])

    norm_cfg = config["normalization"]
    f0 = float(norm_cfg["baseline_frequency_hz"])
    p0 = float(norm_cfg["baseline_power_w"])
    penalty = float(config["optimization"].get("penalty_value", -1.0e9))

    evaluator_b = ObjectiveEvaluator(
        baseline_freq_hz=f0, baseline_power_w=p0, w_f=0.5, w_p=0.5, objective_mode="weighted", penalty_value=penalty
    )
    evaluator_s = ObjectiveEvaluator(
        baseline_freq_hz=f0, baseline_power_w=p0, w_f=0.7, w_p=0.3, objective_mode="weighted", penalty_value=penalty
    )

    csv_log_path = PROJECT_ROOT / "results" / "processed" / "experiment_log_vdd_study.csv"
    summary_json_path = PROJECT_ROOT / "results" / "processed" / "run_summary_vdd_study.json"
    csv_log_path.parent.mkdir(parents=True, exist_ok=True)

    work_dir = PROJECT_ROOT / "results" / "raw" / "vdd_study"
    work_dir.mkdir(parents=True, exist_ok=True)

    headers = [
        "experiment_id",
        "sim_idx",
        "vdd_volts",
        "wn_um",
        "wp_um",
        "ratio_wp_wn",
        "category",
        "status",
        "freq_ghz",
        "power_mw",
        "delay_ps",
        "score_config_b",
        "score_config_s",
        "sim_time_sec",
        "failure_reason"
    ]

    with open(csv_log_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

    print("=" * 90)
    print(f"STARTING CONTROLLED VDD SENSITIVITY STUDY (80 TOTAL SIMULATIONS)")
    print(f"VDD Values Tested: {VDD_TEST_VALUES} Volts")
    print(f"Fixed Candidates : {len(FIXED_CANDIDATES)} sizing vectors")
    print(f"Output CSV Log   : {csv_log_path}")
    print("=" * 90)

    all_records = []
    vdd_summaries: Dict[float, Dict[str, Any]] = {}
    sim_count = 0
    start_wall_time = time.time()

    for vdd in VDD_TEST_VALUES:
        print(f"\n--- TESTING VDD = {vdd:.1f} V ---")
        vdd_success = 0
        vdd_fail = 0
        vdd_records = []

        for c_idx, cand in enumerate(FIXED_CANDIDATES):
            sim_count += 1
            wn_um = cand["wn_um"]
            wp_um = cand["wp_um"]
            wn_m = wn_um * 1e-6
            wp_m = wp_um * 1e-6
            ratio = wp_um / wn_um
            category = cand["category"]

            iter_str = f"vdd_{int(vdd*10)}v_cand_{c_idx:02d}"
            netlist_path = work_dir / f"run_{iter_str}.net"

            # Inject Wn, Wp, and VDD_VAL
            parameterizer.generate_netlist({"Wn": wn_m, "Wp": wp_m, "VDD_VAL": vdd}, netlist_path)
            sim_res = runner.run(netlist_path)
            metrics = extractor.extract(sim_res)

            score_b, feasible_b, _ = evaluator_b.evaluate(metrics)
            score_s, feasible_s, _ = evaluator_s.evaluate(metrics)

            status = metrics.get("status", "FAILED")
            failure_reason = metrics.get("error_message") or ("No 0.9V crossings" if status == "NO_OSCILLATION" else "")

            freq_ghz = metrics.get("freq_ghz") if feasible_b else None
            power_mw = metrics.get("power_mw") if feasible_b else None
            delay_ps = metrics.get("delay_ps") if feasible_b else None

            row = [
                "exp_vdd_sensitivity",
                sim_count,
                f"{vdd:.1f}",
                f"{wn_um:.4f}",
                f"{wp_um:.4f}",
                f"{ratio:.4f}",
                category,
                status,
                f"{freq_ghz:.4f}" if freq_ghz is not None else "NaN",
                f"{power_mw:.4f}" if power_mw is not None else "NaN",
                f"{delay_ps:.4f}" if delay_ps is not None else "NaN",
                f"{score_b:.6f}",
                f"{score_s:.6f}",
                f"{sim_res.elapsed_time:.3f}",
                failure_reason
            ]

            with open(csv_log_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row)

            rec = {
                "sim_idx": sim_count,
                "vdd": vdd,
                "wn_um": wn_um,
                "wp_um": wp_um,
                "ratio": ratio,
                "category": category,
                "status": status,
                "freq_ghz": freq_ghz,
                "power_mw": power_mw,
                "delay_ps": delay_ps,
                "score_config_b": score_b,
                "score_config_s": score_s,
                "sim_time_sec": sim_res.elapsed_time,
                "failure_reason": failure_reason
            }
            all_records.append(rec)
            vdd_records.append(rec)

            if feasible_b:
                vdd_success += 1
                print(f"  [VDD={vdd:.1f}V | {wn_um:0.2f}u/{wp_um:0.2f}u (Ratio={ratio:0.2f})] -> "
                      f"SUCCESS | Freq: {freq_ghz:6.3f}GHz | Pwr: {power_mw:6.2f}mW | "
                      f"ScoreB: {score_b:+.4f}")
            else:
                vdd_fail += 1
                print(f"  [VDD={vdd:.1f}V | {wn_um:0.2f}u/{wp_um:0.2f}u (Ratio={ratio:0.2f})] -> "
                      f"{status:14s} | Score: {score_b:+.1e}")

        vdd_summaries[vdd] = {
            "vdd_volts": vdd,
            "total": len(FIXED_CANDIDATES),
            "success": vdd_success,
            "failed": vdd_fail,
            "success_rate_pct": (vdd_success / len(FIXED_CANDIDATES)) * 100.0
        }

    total_wall_time = time.time() - start_wall_time

    overall_summary = {
        "experiment_id": "exp_vdd_sensitivity",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "vdd_values_tested": VDD_TEST_VALUES,
        "fixed_candidates_count": len(FIXED_CANDIDATES),
        "total_simulations": sim_count,
        "total_wall_time_sec": total_wall_time,
        "vdd_summaries": vdd_summaries,
        "candidates_list": FIXED_CANDIDATES
    }

    with open(summary_json_path, 'w', encoding='utf-8') as f:
        json.dump(overall_summary, f, indent=2)

    print("\n" + "=" * 90)
    print("CONTROLLED VDD SENSITIVITY STUDY COMPLETE")
    print(f"Total Simulations Executed: {sim_count}")
    print(f"Total Wall-Clock Time     : {total_wall_time:.2f}s (~{total_wall_time/sim_count:.2f}s/sim)")
    print("-" * 90)
    print("VDD SUCCESS RATE SUMMARY:")
    for vdd, vsum in vdd_summaries.items():
        print(f"  VDD = {vdd:.1f} V : {vsum['success']:2d} / {vsum['total']} SUCCESS ({vsum['success_rate_pct']:5.1f}%)")
    print("=" * 90)

    return overall_summary


if __name__ == "__main__":
    cfg_file = PROJECT_ROOT / "configs" / "optimization_config.yaml"
    run_vdd_sensitivity_study(cfg_file)

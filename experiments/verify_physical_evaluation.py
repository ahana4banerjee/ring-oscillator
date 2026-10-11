"""
Verification Script: Single Real LTspice Evaluation (Phase 6 · Step 6.2.1 Readiness Verification)

Executes exactly ONE real physical simulation using PhysicalCandidateEvaluator:
- Candidate: Nominal baseline Wn = 0.50 um, Wp = 1.00 um (Ln = Lp = 40 nm, 5-stage ring oscillator)
- Scenario A weights: w_f = 0.5, w_p = 0.5
- Real LTspice executable invocation
- Verifies extraction, units, physical plausibility, objective scoring, and file generation.
- Completely isolated: zero Random Search data read or used.
"""

import json
import math
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.run_bayesian_opt_scenario_a import (
    PhysicalCandidateEvaluator,
    load_and_validate_bo_config,
    _safe_write_file
)
from src.evaluation.objective import ObjectiveEvaluator


def run_single_real_evaluation():
    print("=" * 80)
    print("STEP 3: RUNNING ONE REAL LTSPICE EVALUATION FOR READINESS VERIFICATION")
    print("=" * 80)

    # 1. Load formal configuration
    config_path = PROJECT_ROOT / "configs" / "bayesian_optimization_config.yaml"
    config = load_and_validate_bo_config(config_path, scenario_key="scenario_a")

    circ_cfg = config["circuit"]
    sim_cfg = config["simulation"]
    norm_cfg = config["normalization"]
    sc_a_cfg = config["optimization"]["scenarios"]["scenario_a"]

    template_path = PROJECT_ROOT / circ_cfg["template_netlist"]
    ltspice_exe = Path(sim_cfg["ltspice_executable"])
    work_dir = PROJECT_ROOT / "experiments" / "bayesian_optimization" / "scenario_05_05" / "single_eval_readiness_test"
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"Template netlist: {template_path}")
    print(f"LTspice executable: {ltspice_exe}")
    print(f"Work directory: {work_dir}")

    # 2. Configure Objective Evaluator
    obj_eval = ObjectiveEvaluator(
        baseline_freq_hz=norm_cfg["baseline_frequency_hz"],
        baseline_power_w=norm_cfg["baseline_power_w"],
        w_f=sc_a_cfg["w_f"],
        w_p=sc_a_cfg["w_p"],
        objective_mode="weighted",
        penalty_value=config["optimization"]["penalty_value"]
    )

    # 3. Instantiate Physical Evaluator
    evaluator = PhysicalCandidateEvaluator(
        template_netlist_path=template_path,
        ltspice_executable=ltspice_exe,
        work_dir=work_dir,
        objective_evaluator=obj_eval,
        timeout_seconds=float(sim_cfg["timeout_seconds"]),
        num_stages=int(circ_cfg["stages"])
    )
    assert evaluator.is_physical is True, "Evaluator must be physical!"

    # 4. Known-valid candidate: Nominal baseline
    candidate = {
        "wn": float(circ_cfg["nominal_wn"]),  # 0.50 um
        "wp": float(circ_cfg["nominal_wp"])   # 1.00 um
    }
    print(f"\nEvaluating candidate: Wn = {candidate['wn']*1e6:.2f} µm, Wp = {candidate['wp']*1e6:.2f} µm")

    t0 = time.time()
    result = evaluator.evaluate(candidate, iteration_idx=0)
    elapsed = time.time() - t0

    print(f"LTspice evaluation completed in {elapsed:.2f} s")
    print(f"Simulation result status: {result['status']}")
    print(f"Is physical (is_synthetic == False): {not result['is_synthetic']}")
    print(f"Is feasible: {result['is_feasible']}")

    metrics = result["metrics"]
    print("\n--- EXTRACTED PHYSICAL METRICS ---")
    print(f"  Oscillation status : {'VALID' if metrics.get('is_oscillating') else 'FAILED'}")
    print(f"  Frequency (GHz)    : {metrics.get('freq_ghz'):.6f} GHz ({metrics.get('freq_hz'):.2f} Hz)")
    print(f"  Period (ps)        : {metrics.get('period_s')*1e12:.4f} ps")
    print(f"  Stage delay (ps)   : {metrics.get('delay_ps'):.4f} ps")
    print(f"  Average power (µW) : {metrics.get('power_mw')*1000:.3f} µW ({metrics.get('power_w'):.6e} W)")
    print(f"  PDP (fJ)           : {metrics.get('pdp_j')*1e15:.6f} fJ")

    print("\n--- OBJECTIVE CALCULATION (Scenario A: Balanced 0.5/0.5) ---")
    print(f"  Objective score F  : {result['objective_score']:.6f}")
    breakdown = result.get("breakdown", {})
    print(f"  Norm freq (f/f0)   : {breakdown.get('norm_freq'):.6f}")
    print(f"  Norm power (P/P0)  : {breakdown.get('norm_power'):.6f}")
    print(f"  Freq component     : {breakdown.get('freq_component'):.6f}")
    print(f"  Power component    : {breakdown.get('power_component'):.6f}")

    # 5. Check output files
    expected_net = work_dir / "run_iter_0000.net"
    expected_log = work_dir / "run_iter_0000.log"
    print("\n--- OUTPUT ARTIFACT VERIFICATION ---")
    print(f"  Netlist generated: {expected_net.exists()} ({expected_net})")
    print(f"  Log generated    : {expected_log.exists()} ({expected_log})")

    # 6. Physical consistency checks
    f_hz = metrics["freq_hz"]
    t_s = metrics["period_s"]
    recip_err = abs(f_hz * t_s - 1.0)
    delay_err = abs(metrics["delay_s"] - t_s / 10.0)
    print(f"  Reciprocity check |f*T - 1|: {recip_err:.2e} (pass: {recip_err < 1e-3})")
    print(f"  Delay check |t_pd - T/10|  : {delay_err:.2e} s (pass: {delay_err < 1e-15})")

    # Save summary record
    record_payload = {
        "candidate": candidate,
        "evaluation_time_sec": elapsed,
        "is_physical": True,
        "result": result
    }
    out_record_path = work_dir / "single_evaluation.json"
    _safe_write_file(out_record_path, json.dumps(record_payload, indent=2))
    print(f"\nReadiness evaluation record persisted to: {out_record_path}")

    return result


if __name__ == "__main__":
    run_single_real_evaluation()

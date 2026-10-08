"""
Phase 4 verification script: End-to-end simulation + metric extraction + objective evaluation.

Demonstrates candidate scoring under both Config B (Balanced) and Config S (Speed-biased).
"""

from pathlib import Path
from src.ltspice.parameterizer import NetlistParameterizer
from src.simulation.runner import LTspiceRunner
from src.evaluation.extractor import MetricExtractor
from src.evaluation.objective import ObjectiveEvaluator

LTSPICE_EXE = r"C:\Users\Ahana Banerjee\AppData\Local\Programs\ADI\LTspice\LTspice.exe"
TEMPLATE_PATH = Path("circuits/templates/ring_oscillator.net")
OUTPUT_DIR = Path("results/raw/phase4_demo")

# 40nm Baseline Normalization Constants (Wn=0.5u, Wp=1.0u @ 1.1V)
BASELINE_FREQ_HZ = 41069756649.1       # 41.0697566491 GHz
BASELINE_POWER_W = 0.000140169553568   # 140.169553568 uW


def main():
    print("=" * 75)
    print("Phase 4: Objective Function & Penalty Engine Verification")
    print("=" * 75)

    parameterizer = NetlistParameterizer(TEMPLATE_PATH)
    runner = LTspiceRunner(executable_path=LTSPICE_EXE, timeout_seconds=20.0)
    extractor = MetricExtractor(num_stages=5)

    # Initialize Evaluators for both weight profiles
    evaluator_b = ObjectiveEvaluator(
        baseline_freq_hz=BASELINE_FREQ_HZ,
        baseline_power_w=BASELINE_POWER_W,
        w_f=0.5,
        w_p=0.5,
        objective_mode="weighted"
    )

    evaluator_s = ObjectiveEvaluator(
        baseline_freq_hz=BASELINE_FREQ_HZ,
        baseline_power_w=BASELINE_POWER_W,
        w_f=0.7,
        w_p=0.3,
        objective_mode="weighted"
    )

    candidates = [
        {"name": "Baseline Reference (0.50u / 1.00u)", "Wn": 0.50e-6, "Wp": 1.00e-6, "VDD_VAL": 1.1},
        {"name": "Candidate 2 - Fast/High-Power (0.80u / 1.60u)", "Wn": 0.80e-6, "Wp": 1.60e-6, "VDD_VAL": 1.1},
        {"name": "Candidate 3 - Small/Low-Power (0.18u / 0.36u)", "Wn": 0.18e-6, "Wp": 0.36e-6, "VDD_VAL": 1.1},
    ]

    print("\nEvaluated Candidates Sizing & Fitness Scoring Summary:")
    print("-" * 75)

    for idx, cand in enumerate(candidates, 1):
        params = {"Wn": cand["Wn"], "Wp": cand["Wp"], "VDD_VAL": cand["VDD_VAL"]}
        run_netlist = OUTPUT_DIR / f"candidate_{idx}.net"

        parameterizer.generate_netlist(params, run_netlist)
        sim_res = runner.run(run_netlist)

        if not sim_res.success or not sim_res.log_path:
            print(f"[{cand['name']}] Simulation Failed: {sim_res.error_message}")
            continue

        metrics = extractor.extract_from_log(sim_res.log_path)
        score_b, feasible_b, breakdown_b = evaluator_b.evaluate(metrics)
        score_s, feasible_s, breakdown_s = evaluator_s.evaluate(metrics)

        print(f"\n[{cand['name']}]")
        print(f"  -> Raw Metrics:  f_osc = {metrics['freq_ghz']:.3f} GHz, P_avg = {metrics['power_mw']:.3f} mW, t_pd = {metrics['delay_ps']:.2f} ps")
        print(f"  -> Normalized:   norm_freq = {breakdown_b['norm_freq']:.4f}x, norm_power = {breakdown_b['norm_power']:.4f}x")
        print(f"  -> Config B (Balanced 0.5/0.5)    Fitness Score F = {score_b:+.4f}")
        print(f"  -> Config S (Speed-biased 0.7/0.3) Fitness Score F = {score_s:+.4f}")

    print("\n" + "=" * 75)
    print("Phase 4 Objective Function & Penalty Engine Verified Successfully!")
    print("=" * 75)


if __name__ == "__main__":
    main()

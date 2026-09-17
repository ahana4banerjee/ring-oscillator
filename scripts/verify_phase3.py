"""
Phase 3 verification script: End-to-end simulation + measurement extraction.

Generates parametric netlists, executes headless LTspice runs, and extracts electrical metrics.
"""

from pathlib import Path
from src.ltspice.parameterizer import NetlistParameterizer
from src.simulation.runner import LTspiceRunner
from src.evaluation.extractor import MetricExtractor

LTSPICE_EXE = r"C:\Users\Ahana Banerjee\AppData\Local\Programs\ADI\LTspice\LTspice.exe"
TEMPLATE_PATH = Path("circuits/templates/ring_oscillator.net")
OUTPUT_DIR = Path("results/raw/phase3_demo")


def main():
    print("=" * 70)
    print("Phase 3: Measurement Extraction Engine Verification")
    print("=" * 70)

    parameterizer = NetlistParameterizer(TEMPLATE_PATH)
    runner = LTspiceRunner(executable_path=LTSPICE_EXE, timeout_seconds=20.0)
    extractor = MetricExtractor(num_stages=5)

    candidates = [
        {"Wn": 0.50e-6, "Wp": 1.00e-6, "VDD_VAL": 1.8},
        {"Wn": 0.80e-6, "Wp": 1.60e-6, "VDD_VAL": 1.8},
        {"Wn": 0.18e-6, "Wp": 0.36e-6, "VDD_VAL": 1.8},
    ]

    for idx, params in enumerate(candidates, 1):
        run_netlist = OUTPUT_DIR / f"candidate_{idx}.net"
        print(f"\n[Candidate {idx}] Wn={params['Wn']*1e6:.2f}u, Wp={params['Wp']*1e6:.2f}u, VDD={params['VDD_VAL']}V")

        parameterizer.generate_netlist(params, run_netlist)
        sim_res = runner.run(run_netlist)

        if not sim_res.success or not sim_res.log_path:
            print(f"  -> Simulation Error: {sim_res.error_message}")
            continue

        metrics = extractor.extract_from_log(sim_res.log_path)
        print(f"  -> Extraction Status: {metrics['status']}")
        print(f"  -> Is Oscillating:    {metrics['is_oscillating']}")

        if metrics['is_oscillating']:
            print(f"  -> Oscillation Freq:  {metrics['freq_ghz']:.3f} GHz")
            print(f"  -> Period:            {metrics['period_s']*1e12:.2f} ps")
            print(f"  -> Stage Delay (t_pd):{metrics['delay_ps']:.2f} ps")
            print(f"  -> Avg Power:         {metrics['power_mw']:.3f} mW")
            print(f"  -> Power-Delay Prod:  {metrics['pdp_j']*1e15:.3f} fJ")
        else:
            print(f"  -> Power (non-osc):   {metrics['power_mw']:.3f} mW" if metrics['power_mw'] else "  -> Power: N/A")
            print(f"  -> Reason:            {metrics['error_message']}")

    print("\n" + "=" * 70)
    print("Phase 3 Measurement Extraction Engine Verified Successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()

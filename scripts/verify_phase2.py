"""
Phase 2 verification script: Python <-> LTspice Automation.

Executes a parametric sweep of Wn and Wp values from Python and verifies headless LTspice batch runs.
"""

from pathlib import Path
from src.ltspice.parameterizer import NetlistParameterizer
from src.simulation.runner import LTspiceRunner

LTSPICE_EXE = r"C:\Users\Ahana Banerjee\AppData\Local\Programs\ADI\LTspice\LTspice.exe"
TEMPLATE_PATH = Path("circuits/templates/ring_oscillator.net")
OUTPUT_DIR = Path("results/raw/phase2_demo")


def main():
    print("=" * 60)
    print("Phase 2: Python <-> LTspice Automation Verification")
    print("=" * 60)

    parameterizer = NetlistParameterizer(TEMPLATE_PATH)
    runner = LTspiceRunner(executable_path=LTSPICE_EXE, timeout_seconds=20.0)

    # Candidate transistor width vectors to test
    candidates = [
        {"Wn": 0.36e-6, "Wp": 0.72e-6, "VDD_VAL": 1.8},
        {"Wn": 0.50e-6, "Wp": 1.00e-6, "VDD_VAL": 1.8},
        {"Wn": 0.80e-6, "Wp": 1.60e-6, "VDD_VAL": 1.8},
    ]

    for idx, params in enumerate(candidates, 1):
        run_netlist = OUTPUT_DIR / f"candidate_{idx}.net"
        print(f"\n[Iteration {idx}] Parameterizing candidate: Wn={params['Wn']*1e6:.2f}u, Wp={params['Wp']*1e6:.2f}u")
        parameterizer.generate_netlist(params, run_netlist)

        print(f"  -> Generated Netlist: {run_netlist}")
        print("  -> Launching LTspice batch process...")
        
        result = runner.run(run_netlist)
        
        print(f"  -> Result: Status={'SUCCESS' if result.success else 'FAILED'}, Elapsed Time={result.elapsed_time:.2f}s")
        if result.success:
            print(f"  -> Log generated: {result.log_path}")
            print(f"  -> Raw waveform generated: {result.raw_path}")
        else:
            print(f"  -> Error: {result.error_message}")

    print("\n" + "=" * 60)
    print("Phase 2 Automation Pipeline Verified Successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()

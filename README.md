# Automated Optimization of a CMOS Ring Oscillator Using Bayesian Optimization and LTspice

This project implements an automated pipeline coupling Python with LTspice to optimize transistor sizing ($W_n$ and $W_p$) for a 5-stage CMOS ring oscillator.

The goal is to explore performance trade-offs across oscillation frequency, power consumption, and propagation delay using Bayesian Optimization, with Random Search serving as a baseline comparison.

---

## System Architecture

The system coordinates simulation and optimization through a modular feedback loop:

```
Python Optimizer (Bayesian / Random Search)
       │
       ▼ (Candidate Wn, Wp)
Circuit Parameterizer (SPICE Netlist Injection)
       │
       ▼ (Headless Simulation Execution)
LTspice Simulation Engine (Transient Analysis)
       │
       ▼ (Simulation .log / .raw Output)
Measurement Extractor (Frequency, Power, Delay)
       │
       ▼ (Scalar Objective Calculation)
Objective Evaluator & Experiment Logger
       │
       ▼ (Surrogate Update & Next Candidate Selection)
Back to Python Optimizer
```

---

## Methodology

1. **Target Circuit:** A 5-stage CMOS ring oscillator parameterized by NMOS width ($W_n$) and PMOS width ($W_p$).
2. **Simulation Layer:** Automated headless LTspice batch simulation (`-b`) with watchdog timeout and crash protection.
3. **Metric Extraction:** Parsing SPICE `.meas` statements from simulation logs to extract oscillation frequency ($f_{osc}$), average power dissipation ($P_{avg}$), and propagation delay ($t_{pd}$).
4. **Optimization Strategies:**
   - **Bayesian Optimization:** Sample-efficient search using a Gaussian Process surrogate model and acquisition function (e.g., Expected Improvement).
   - **Random Search:** Unbiased baseline running across identical parameter bounds and evaluation pipelines.
5. **Experiment Tracking:** Logging of all evaluated candidates, status, electrical metrics, and objective scores into structured CSV and JSON summaries.

---

## Phased Implementation Plan

- **Phase 0: Environment & Dependencies** — Setup directory layout, configuration schema, and Python dependencies.
- **Phase 1: Baseline LTspice Circuit Validation** — Confirm standalone oscillation and transient measurements of the baseline 5-stage ring oscillator.
- **Phase 2: Python ↔ LTspice Automation** — Implement netlist parameter injection and headless subprocess execution with timeout handling.
- **Phase 3: Measurement Extraction** — Implement robust parsing of SPICE output logs for frequency, power, and timing metrics.
- **Phase 4: Objective Function & Penalties** — Formulate multi-metric objective evaluation and non-oscillation penalty policies.
- **Phase 5: Random Search Baseline** — Implement uniform random sampling optimization pipeline and logging.
- **Phase 6: Bayesian Optimization** — Implement Gaussian Process surrogate model, acquisition function, and optimization loop.
- **Phase 7: Experiment Logging & Visualization** — Build automated CSV/JSON run trackers and convergence/Pareto plotting scripts.
- **Phase 8: Validation & Comparative Benchmark** — Benchmark Bayesian Optimization against Random Search across identical budgets.
- **Phase 9: Extended Experiments (Optional)** — Evaluate optimal sizing robustness across supply voltage ($V_{DD}$) and temperature variations.

---

## Current Status

- **Current Phase:** **Phase 4 (Objective Function & Penalty Engine)**
- **Completed:** 
  - **Phase 0 completed**: Project structure, `.gitignore`, initial config, and isolated `venv`.
  - **Phase 1 completed**: Baseline 5-stage ring oscillator schematic ([ltspice.asc](circuits/baseline/ltspice.asc)) validated.
  - **Phase 2 completed**: Python ↔ LTspice automation pipeline (`src/ltspice/parameterizer.py`, `src/simulation/runner.py`).
  - **Phase 3 completed**: Measurement extraction engine (`src/ltspice/parser.py`, `src/evaluation/extractor.py`) implemented and verified; reliably extracts $f_{osc}$, $P_{avg}$, stage delay ($t_{pd}$), period ($T$), and Power-Delay Product (PDP) into a validated dictionary.
- **Next Immediate Step:** Implement `src/evaluation/objective.py` to formulate multi-objective scoring and non-oscillation penalty policies.

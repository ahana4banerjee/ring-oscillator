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
4. **Decided Objective Function:**
   - Evaluates multi-metric trade-offs via normalized weighted utility:
     $$\mathcal{F} = w_f \cdot \left(\frac{f_{osc}}{f_0}\right) - w_p \cdot \left(\frac{P_{avg}}{P_0}\right)$$
   - **Baseline Normalization ($f_0, P_0$):** Derived from the validated Phase 1–3 reference baseline ($f_0 = 28.492\text{ GHz}, P_0 = 141.16\text{ mW}$). Yields $\mathcal{F} = 0.0$ for baseline under balanced weights.
   - **Supported Configurations:**
     - **Config B (Balanced):** $w_f = 0.5, w_p = 0.5$
     - **Config S (Speed-biased):** $w_f = 0.7, w_p = 0.3$
5. **Supply Voltage Note:** $V_{DD} = 1.8\text{ V}$ is currently used as a **temporary development/simulation value**; final physical $V_{DD}$ remains TBD.
6. **Optimization Strategies:**
   - **Bayesian Optimization:** Sample-efficient search using a Gaussian Process surrogate model and acquisition function (e.g., Expected Improvement).
6. **Staged Optimization Methodology:**
   - **Phase 5 (Staged Random Search & Characterization):** Uses Random Search in stages (5.1 Implementation $\to$ 5.2 Smoke Test $\to$ 5.3 Development Run $\to$ 5.4 Search-Space Characterization $\to$ 5.5 Final Search-Bound Decision).
   - **Temporary Bounds Note:** Current bounds ($W_n \in [0.18\mu\text{m}, 0.80\mu\text{m}]$, $W_p \in [0.36\mu\text{m}, 1.60\mu\text{m}]$) are **temporary development bounds**. Final search bounds will be frozen in Phase 5.5 before Phase 6.
   - **Phase 6 (Bayesian Optimization):** Fits a Gaussian Process surrogate to learn $(W_n, W_p) \to \mathcal{F}$ and uses acquisition functions to balance exploration and exploitation across the frozen final bounds. BO will NOT simply search around the best Random Search point.
7. **Experiment Tracking:** Logging of all evaluated candidates, status, electrical metrics, and objective scores into structured CSV and JSON summaries.

---

## Phased Implementation Plan

- **Phase 0: Environment & Dependencies** — Setup directory layout, configuration schema, and Python dependencies.
- **Phase 1: Baseline LTspice Circuit Validation** — Confirm standalone oscillation and transient measurements of the baseline 5-stage ring oscillator.
- **Phase 2: Python ↔ LTspice Automation** — Implement netlist parameter injection and headless subprocess execution with timeout handling.
- **Phase 3: Measurement Extraction** — Implement robust parsing of SPICE output logs for frequency, power, and timing metrics.
- **Phase 4: Objective Function & Penalties** — Formulate multi-metric objective evaluation and non-oscillation penalty policies.
- **Phase 5: Staged Random Search & Search-Space Characterization** — 
  - *Phase 5.1:* Random Search implementation.
  - *Phase 5.2:* 5-iteration smoke test.
  - *Phase 5.3:* 20-iteration development run (temporary bounds).
  - *Phase 5.4:* Search-space feasibility & trade-off characterization.
  - *Phase 5.5:* Formal final $W_n/W_p$ search bounds decision (`TBD-03` resolution).
- **Phase 6: Bayesian Optimization** — Implement GP surrogate model, acquisition function, and optimization loop using final bounds.
- **Phase 7: Experiment Logging & Visualization** — Build automated CSV/JSON run trackers and convergence/Pareto plotting scripts.
- **Phase 8: Validation & Comparative Benchmark** — Benchmark Bayesian Optimization against Random Search across identical budgets and bounds.
- **Phase 9: Extended Experiments (Optional)** — Evaluate optimal sizing robustness across supply voltage ($V_{DD}$) and temperature variations.

---

## Current Status

- **Current Phase:** **Phase 5 (Staged Random Search & Search-Space Characterization)**
- **Completed:** 
  - **Phase 0 completed**: Project structure, `.gitignore`, initial config, and isolated `venv`.
  - **Phase 1 completed**: Baseline 5-stage ring oscillator schematic ([ring_oscillator.asc](circuits/baseline/ring_oscillator.asc)) validated.
  - **Phase 2 completed**: Python ↔ LTspice automation pipeline (`src/ltspice/parameterizer.py`, `src/simulation/runner.py`).
  - **Phase 3 completed**: Measurement extraction engine (`src/ltspice/parser.py`, `src/evaluation/extractor.py`).
  - **Phase 4 completed**: Objective function & penalty engine (`src/evaluation/objective.py`) implemented; calculates weighted multi-objective utility $\mathcal{F} = w_f \frac{f}{f_0} - w_p \frac{P}{P_0}$ normalized against Phase 1–3 baseline constants ($f_0 = 28.492\text{ GHz}, P_0 = 141.16\text{ mW}$) under Config B ($0.5/0.5$) and Config S ($0.7/0.3$), with automated penalty assignment ($-\infty / -1.0\times 10^9$) for invalid or non-oscillating candidates.
  - **Phase 5 Methodology Staging:** Detailed Phase 5.1–5.5 staged roadmap defined in `SRS.md`.
- **Next Immediate Step:** **Phase 5.1 — Random Search Implementation** (`src/optimization/random_search.py`).


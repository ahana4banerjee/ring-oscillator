# Automated Optimization of a CMOS Ring Oscillator Using Bayesian Optimization and LTspice

This repository implements an automated software-hardware simulation optimization pipeline coupling Python with LTspice to optimize transistor channel widths ($W_n$ and $W_p$) for a 5-stage CMOS ring oscillator.

The goal is to explore trade-offs across oscillation frequency ($f_{osc}$), average power dissipation ($P_{avg}$), propagation delay ($t_{pd}$), and Power-Delay Product ($PDP$) using Bayesian Optimization, benchmarked against a formal Random Search baseline.

---

## 1. System Architecture

The pipeline coordinates simulation execution and numerical optimization through a modular feedback loop:

```text
Python Optimization Layer (Bayesian Optimization / Random Search)
       │
       ▼ (Candidate Wn, Wp)
Circuit Parameterizer (SPICE Netlist Injection via .param Wn=.. Wp=..)
       │
       ▼ (Headless Execution -b -Run)
LTspice Simulation Engine (5-Stage CMOS Ring Inverter Chain Transient Analysis)
       │
       ▼ (Output .log Measurement Parsing)
Measurement Extractor (Frequency, Power, Period, Delay, PDP)
       │
       ▼ (Scalar Objective Utility Calculation & Penalty Policy)
Objective Evaluator & Experiment Logger (CSV / JSON / Plots)
       │
       ▼ (Surrogate Model Update & Next Candidate Selection)
Back to Python Optimization Engine
```

---

## 2. Technology Node & Baseline Configuration

- **Technology Scaling Assumption:** 40 nm CMOS design rules ($L_n = L_p = 40\text{ nm} = 0.04\mu\text{m}$). (**TBD-01 RESOLVED**)
- **Transistor Model:** Generic Level-1 MOS model (`.model NMOS NMOS(LEVEL=1 VTO=0.15 KP=20m)`, `.model PMOS PMOS(LEVEL=1 VTO=-0.15 KP=10m)`). *(Note: Uncalibrated simulation model used for numerical optimization research, not a calibrated foundry BSIM4 PDK).*
- **Supply Voltage:** $V_{DD} = 1.1\text{ V}$ fixed nominal operating voltage. (**TBD-02 RESOLVED**)
- **Operating Temperature:** $25^\circ\text{C}$.
- **Baseline Sizing Reference:** $W_n = 0.50\mu\text{m}$, $W_p = 1.00\mu\text{m}$, load capacitors $C_1 .. C_5 = 0.5\text{ fF}$.
- **Verified Reference Baseline Measurements:**
  - Oscillation Frequency: $f_0 = 41.0697566491\text{ GHz}$
  - Average Power Dissipation: $P_0 = 140.169553568\mu\text{W}$
  - Stage Propagation Delay: $t_{pd0} = 2.43488172707\text{ ps}$
  - Power-Delay Product: $PDP_0 \approx 0.341300\text{ fJ}$
  - Baseline Objective Score: $\mathcal{F}_0 = 0.000000$

---

## 3. Frozen Formal Search Bounds

The design space was characterized through 90 exploratory Random Search evaluations (10 pilot + 30 boundary + 50 focused) and frozen prior to formal benchmarking:

- **NMOS Width ($W_n$):** $W_n \in [0.12\mu\text{m}, 1.20\mu\text{m}]$ (**TBD-03 RESOLVED**)
- **PMOS Width ($W_p$):** $W_p \in [0.24\mu\text{m}, 2.80\mu\text{m}]$ (**TBD-03 RESOLVED**)
- **Grid Resolution:** $10\text{ nm} = 0.01\mu\text{m}$ discrete DRC manufacturing grid step.
- **Sampling Constraint:** $W_n$ and $W_p$ are sampled independently. No artificial ratio constraints ($W_p = 2 W_n$ or $1 \le W_p/W_n \le 5$) are imposed.
- **Modeling-Scope Rationale:** The lower $W_n$ bound of $0.12\mu\text{m}$ is adopted as a conservative modeling-scope limit for the generic Level-1 MOS model. Exploratory results below $0.15\mu\text{m}$ showed increasing utility, but these results represent model extrapolation rather than calibrated physical 40 nm behavior.

---

## 4. Multi-Objective Utility Formulation

The objective utility function is normalized against the 40 nm reference baseline:

$$\mathcal{F}(W_n, W_p) = w_f \cdot \left(\frac{f_{osc}}{f_0}\right) - w_p \cdot \left(\frac{P_{avg}}{P_0}\right)$$

### Two Objective Weight Scenarios:
1. **Scenario A — Balanced Objective (Config B):** $w_f = 0.5, w_p = 0.5$
   - Completed for formal Random Search ($\mathcal{F}_{baseline} = 0.000000$, best observed score $\mathcal{F} = 0.010923$).
2. **Scenario B — Frequency-Priority Objective (Config S):** $w_f = 0.7, w_p = 0.3$
   - Investigates parameter shift under speed-priority preference.
   - **Re-scoring Strategy:** The Random Search benchmark for Scenario B is obtained by **re-scoring the exact same 100 physical simulations** from Scenario A. NO additional circuit simulations are required.

---

## 5. Completed Work & Key Findings

### A. Exploratory Campaigns (90 Evaluations)
- 3 exploratory campaigns mapped the design space structure.
- Identified two key regimes: a primary low-power / high-utility region ($W_n \le 0.30\mu\text{m}, W_p \ge 1.80\mu\text{m}$) and a secondary high-speed region ($W_n \approx 1.00 - 1.20\mu\text{m}$).

### B. Formal Random Search Campaign (100 Physical Evaluations, Seed 2026)
- **Feasibility:** 100 / 100 valid oscillating simulations (100.0% feasibility; 99 unique sizing pairs, 1 duplicate).
- **Best Observed Formal RS Candidate:** Iteration 62 ($W_n = 0.19\mu\text{m}, W_p = 2.66\mu\text{m}$, Ratio = 14.00)
  - Objective Score: $\mathcal{F} = \mathbf{0.010923}$
  - Frequency: $35.368852\text{ GHz}$ (-13.88% vs baseline)
  - Average Power: $117.651\mu\text{W}$ (-16.07% vs baseline)
  - Delay: $2.8273\text{ ps}$ (+16.12% vs baseline)
  - PDP: $0.332639\text{ fJ}$ (-2.54% vs baseline)
- **Empirical Convergence:** Best-so-far curve reached 25% of final score at Iteration 27 and 100% at Iteration 62 (plateauing thereafter).
- **PDP Invariance:** PDP showed only ~3.08% total variation across a 6x frequency range (15.8 GHz to 93.4 GHz), empirically confirming dynamic capacitive switching energy dominance.

---

## 6. Current Project Status Ledger

| Phase / Experiment | Status | Physical Evals | Key Output / Artifact |
| :--- | :--- | :---: | :--- |
| **Phases 0–4 (Infrastructure & Pipeline)** | **COMPLETE** | N/A | [RE_AUDIT_PHASE_0_4.md](RE_AUDIT_PHASE_0_4.md) (20/20 tests pass) |
| **Exploratory Random Search** | **COMPLETE** | 90 | 3 campaigns (10 + 30 + 50 evals) |
| **Formal Search Space Bounds Decision** | **FROZEN** | N/A | $W_n \in [0.12, 1.20]\mu\text{m}, W_p \in [0.24, 2.80]\mu\text{m}$ |
| **Formal Random Search (Scenario A: 0.5/0.5)** | **COMPLETE** | 100 | [RANDOM_SEARCH_FORMAL_100.md](RANDOM_SEARCH_FORMAL_100.md) |
| **Formal Random Search (Scenario B: 0.7/0.3)** | **READY FOR RE-SCORING** | 0 (Re-scored) | Dataset ready for 0.7/0.3 re-scoring |
| **Bayesian Optimization (Experiment A: 0.5/0.5)** | **NOT STARTED** | 100 (Planned) | Planned budget = 100 evaluations |
| **Bayesian Optimization (Experiment B: 0.7/0.3)** | **NOT STARTED** | 100 (Planned) | Planned budget = 100 evaluations |
| **Final RS vs BO Comparative Benchmark** | **NOT STARTED** | N/A | Planned after BO completion |

---

## 7. Next Planned Phase

The next experimental phase is **BAYESIAN OPTIMIZATION**:
1. Implement GP surrogate modeling and Expected Improvement acquisition in Python.
2. Execute BO Experiment A ($0.5/0.5$, budget 100 physical evaluations) across the frozen bounds $[0.12, 1.20]\mu\text{m} \times [0.24, 2.80]\mu\text{m}$.
3. Execute BO Experiment B ($0.7/0.3$, budget 100 physical evaluations) across the frozen bounds $[0.12, 1.20]\mu\text{m} \times [0.24, 2.80]\mu\text{m}$.
4. Perform fair comparative benchmark (RQ1, RQ2, RQ3) comparing BO against the formal Random Search baseline.

---

## 8. Repository Structure

```text
ring-oscillator/
├── SRS.md                         # Single Source of Truth specification
├── README.md                      # Developer onboarding and project entry point
├── RANDOM_SEARCH_FORMAL_100.md    # Formal 100-evaluation Random Search report
├── RE_AUDIT_PHASE_0_4.md          # Pipeline re-audit report (20/20 tests passing)
├── CONTEXT.md                     # Engineering journal and decision log
├── requirements.txt               # Pinned Python package dependencies
├── .gitignore                     # Ignore SPICE binary outputs (*.raw, *.db)
│
├── configs/                       # Configuration files
│   └── optimization_config.yaml   # Primary simulation & optimizer configuration
│
├── circuits/                      # SPICE circuit definitions
│   ├── baseline/                  # Human-readable LTspice schematic reference
│   ├── templates/                 # Parameterized SPICE netlist template (.net)
│   └── models/                    # Transistor model definitions
│
├── src/                           # Source implementation modules
│   ├── optimization/              # Optimization engines (BaseOptimizer, RandomSearchOptimizer)
│   ├── ltspice/                   # Netlist parameterizer & log parser
│   ├── simulation/                # Subprocess runner with watchdog timeout
│   ├── evaluation/                # Electrical metric extractor & objective evaluator
│   └── utils/                     # Configuration validator & logger
│
├── experiments/                   # Experiment execution scripts & results
│   ├── run_formal_random_search_100.py # Formal 100-iteration RS campaign script
│   ├── analyze_formal_100.py          # Analysis script for formal RS dataset
│   └── random_search/
│       ├── exploratory_10/         # Exploratory Batch 1 (N=10)
│       ├── exploratory_30_boundary/# Exploratory Batch 2 (N=30)
│       ├── exploratory_50_focused/ # Exploratory Batch 3 (N=50)
│       └── formal_100/             # Authoritative Formal RS Dataset (100 evals)
│           ├── config.json
│           ├── results.csv
│           ├── summary.md
│           └── plots/
│
├── results/                       # Consolidated processed data & plots
│   ├── processed/                 # Historical CSV logs & JSON summaries
│   └── plots/                     # Characterization figures & scatter maps
│
└── tests/                         # Automated unit & integration tests (20 tests)
```

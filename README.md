# Automated Optimization of a CMOS Ring Oscillator Using Bayesian Optimization and LTspice

This repository implements an automated software-hardware simulation optimization pipeline coupling Python with LTspice to optimize transistor channel widths ($W_n$ and $W_p$) for a 5-stage CMOS ring oscillator.

The goal is to explore trade-offs across oscillation frequency ($f_{osc}$), average power dissipation ($P_{avg}$), propagation delay ($t_{pd}$), and Power-Delay Product ($PDP$) using Bayesian Optimization, benchmarked against a formal Random Search baseline.

> **Research Report & Comprehensive Synthesis:**
> For the complete, publication-grade research analysis consolidating all 290 physical simulations, cross-scenario trade-offs, Pareto comparisons, and artifact navigation, see **[`ANALYSIS.md`](ANALYSIS.md)**.

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

### C. Formal Bayesian Optimization Campaigns (100 Physical Evaluations)
- **Campaign A (Balanced 0.5/0.5, Seed 2026, 50 Evaluations):**
  - **Best Candidate:** Iteration 12 ($W_n = 0.12\mu\text{m}, W_p = 2.80\mu\text{m}$, Ratio = 23.33)
  - **Score:** $\mathcal{F}_A = \mathbf{+0.020616}$ ($f = 27.571\text{ GHz}$, $P = 88.319\mu\text{W}$, $t_{pd} = 3.627\text{ ps}$, $\text{PDP} = 0.3203\text{ fJ}$)
  - **Efficiency:** Achieved $-36.99\%$ power reduction. Outperformed equal-budget Random Search (RS-50: $+0.004793$) by $>4.3\times$, and exceeded full-budget Random Search (RS-100: $+0.010923$) in half the evaluation count.
- **Campaign B (Frequency-Priority 0.7/0.3, Seed 3031, 50 Evaluations):**
  - **Best Candidate:** Iteration 11 ($W_n = 1.20\mu\text{m}, W_p = 2.80\mu\text{m}$, Ratio = 2.33)
  - **Score:** $\mathcal{F}_B = \mathbf{+1.028414}$ ($\Delta \mathcal{F}_B = +0.628414$, $f = 105.656\text{ GHz}$, $P = 360.891\mu\text{W}$, $t_{pd} = 0.9465\text{ ps}$, $\text{PDP} = 0.3416\text{ fJ}$)
  - **Speedup:** Achieved $+157.26\%$ frequency increase with sub-picosecond stage delay ($0.9465\text{ ps}$).

### D. Cross-Method Synthesis & Key Research Conclusions
1. **Sample Efficiency:** Bayesian Optimization rapidly discovered optimal boundary corners through directed surrogate modeling (Matérn 5/2 GP + Expected Improvement), whereas Random Search required double the budget and still lagged in utility.
2. **Multi-Objective Bifurcation:** Shifting user preference from balanced power/delay to speed-priority caused an optimal sizing shift from the minimum-$W_n$ boundary ($0.12\mu\text{m}$) to the maximum-$W_n$ boundary ($1.20\mu\text{m}$), while $W_p$ remained pinned to maximum width ($2.80\mu\text{m}$) in both scenarios.
3. **Comprehensive Synthesis:** For full comparative Pareto frontiers, convergence curves, and discussion, see **[`ANALYSIS.md`](ANALYSIS.md)**.

---

## 6. Current Project Status Ledger

| Phase / Experiment | Status | Physical Evals | Scalar Obj Evals | Key Output / Artifact |
| :--- | :--- | :---: | :---: | :--- |
| **Phases 0–4 (Infrastructure & Pipeline)** | **COMPLETE** | N/A | N/A | [RE_AUDIT_PHASE_0_4.md](RE_AUDIT_PHASE_0_4.md) (20/20 tests pass) |
| **Exploratory Random Search** | **COMPLETE** | 90 | 90 | 3 campaigns (10 pilot + 30 boundary + 50 focused) |
| **Formal Search Space Decision** | **FROZEN** | N/A | N/A | $W_n \in [0.12, 1.20]\mu\text{m}, W_p \in [0.24, 2.80]\mu\text{m}$, 10 nm grid (**TBD-03**) |
| **Formal RS Scenario A (0.5/0.5)** | **COMPLETE** | 100 | 100 | [RANDOM_SEARCH_FORMAL_100.md](RANDOM_SEARCH_FORMAL_100.md) (Seed 2026) |
| **Formal RS Scenario B (0.7/0.3)** | **COMPLETE** | **0** (Offline re-scored) | 100 | [RANDOM_SEARCH_RESCORING_07_03.md](RANDOM_SEARCH_RESCORING_07_03.md) |
| **BO Engine (`src/optimization/bayesian.py`)** | **COMPLETE & VERIFIED** | N/A | N/A | 17/17 unit tests pass (`tests/test_bayesian.py`) |
| **BO Campaign A (0.5/0.5 Balanced)** | **COMPLETE & VERIFIED** | 50 | 50 | [campaign_a_analysis.md](experiments/bayesian_optimization/scenario_05_05/analysis/campaign_a_analysis.md) (Seed 2026) |
| **BO Campaign B (0.7/0.3 Speed-Priority)**| **COMPLETE & VERIFIED** | 50 | 50 | [campaign_b_analysis.md](experiments/bayesian_optimization/scenario_07_03/analysis/campaign_b_analysis.md) (Seed 3031) |
| **Comprehensive Research Synthesis** | **COMPLETE** | N/A | N/A | [ANALYSIS.md](ANALYSIS.md) (Root-level research document) |
| **Current Completed Total** | — | **290** (90 exploratory + 100 RS + 100 BO) | **390** | Complete and physically verified |
| **Projected Final Total** | — | **290** | **390** | Formal optimization = 200 physical simulations |

---

## 7. Bayesian Optimization: Completed Campaigns & Findings

### 7.1 Campaign Summary & Performance Highlights
Both 50-evaluation Bayesian Optimization campaigns have been physically executed in LTspice and analyzed:

1. **Campaign A (Balanced Objective: $w_f = 0.5, w_p = 0.5$, Seed 2026):**
   - **Evaluations:** 50 physical runs (10 LHS + 40 adaptive GP/EI), 49 feasible (98.0%).
   - **Best Candidate:** Iteration 12 ($W_n = 0.12\ \mu\text{m}, W_p = 2.80\ \mu\text{m}$, Ratio = 23.33)
   - **Performance:** Frequency = $27.57\text{ GHz}$, Average Power = $88.32\ \mu\text{W}$ ($-36.99\%$ power reduction), Delay = $3.63\text{ ps}$, PDP = $0.3203\text{ fJ}$ ($-6.14\%$ switching energy reduction), Objective score $\mathcal{F}_A = \mathbf{+0.020616}$.
   - **Benchmarking:** Outperformed equal-budget Random Search (RS-50: $+0.004793$) by $>4.3\times$, and surpassed full-budget Random Search (RS-100: $+0.010923$) in half the evaluation count.
   - **Detailed Report:** [`experiments/bayesian_optimization/scenario_05_05/analysis/campaign_a_analysis.md`](experiments/bayesian_optimization/scenario_05_05/analysis/campaign_a_analysis.md)

2. **Campaign B (Frequency-Priority: $w_f = 0.7, w_p = 0.3$, Seed 3031):**
   - **Evaluations:** 50 physical runs (10 LHS + 40 adaptive GP/EI), 49 feasible (98.0%).
   - **Best Candidate:** Iteration 11 ($W_n = 1.20\ \mu\text{m}, W_p = 2.80\ \mu\text{m}$, Ratio = 2.33)
   - **Performance:** Frequency = $105.66\text{ GHz}$ ($+157.26\%$ speedup), Average Power = $360.89\ \mu\text{W}$, Stage Delay = $0.9465\text{ ps}$ (sub-picosecond delay), PDP = $0.3416\text{ fJ}$ ($+0.08\%$), Objective score $\mathcal{F}_B = \mathbf{+1.028414}$ ($\Delta \mathcal{F}_B = +0.628414$).
   - **Detailed Report:** [`experiments/bayesian_optimization/scenario_07_03/analysis/campaign_b_analysis.md`](experiments/bayesian_optimization/scenario_07_03/analysis/campaign_b_analysis.md)

### 7.2 Methodological Architecture
1. **Two Independent Objective Campaigns:**
   - **Scenario A (Balanced: 0.5f / 0.5P):** $\mathcal{F}_A = 0.5(f/f_0) - 0.5(P/P_0)$
   - **Scenario B (Speed-Priority: 0.7f / 0.3P):** $\mathcal{F}_B = 0.7(f/f_0) - 0.3(P/P_0)$
   - Separate runs with independent evaluation budgets; no solution or surrogate transfer between scenarios.
2. **Evaluation Budget (50 Evaluations per Scenario):**
   - **Phase 1 (Initial Design):** $N_{init} = 10$ space-filling Latin Hypercube Sampling (LHS) evaluations with deterministic seeds.
   - **Phase 2 (Adaptive BO):** $N_{adaptive} = 40$ sequential iterations guided by surrogate re-fitting and Expected Improvement maximization.
   - **Total Completed BO Physical Simulations:** 100 LTspice runs (50 Scenario A + 50 Scenario B).
3. **Strict Isolation from Benchmark Data:**
   - BO was **NOT** pre-trained or initialized with Random Search benchmark evaluations.
4. **Surrogate Model & Kernel:**
   - **Model:** Gaussian Process Regression (GPR).
   - **Kernel:** Matérn 5/2 covariance kernel with Automatic Relevance Determination (ARD) lengthscales $\ell_{W_n}, \ell_{W_p}$.
   - **Normalization:** Inputs normalized to $[0, 1]^2$; objective outputs standardized.
   - **Noise Handling:** Numerical nugget $\sigma_n^2 \approx 10^{-6}$ added to covariance diagonal for Cholesky solver stability.
   - **Fitting Policy:** Log Marginal Likelihood maximization via L-BFGS-B at each adaptive step.
5. **Acquisition Function:**
   - **Expected Improvement (EI):** $\alpha_{EI}(\mathbf{x}) = \mathbb{E}[\max(0, \mathcal{F}(\mathbf{x}) - \mathcal{F}^+ - \xi)]$ with exploration jitter $\xi = 0.01$ evaluated in the standardized domain.
6. **Search Space & 10 nm Grid Discretization:**
   - Frozen bounds: $W_n \in [0.12, 1.20]\mu\text{m}$, $W_p \in [0.24, 2.80]\mu\text{m}$ (28,013 valid candidate points).
   - Continuous proposals snapped to $10\text{ nm}$ DRC grid with strict duplicate rejection.

---

## 8. Repository Structure

```text
ring-oscillator/
├── ANALYSIS.md                    # Comprehensive Root-Level Research Report (All Findings & Comparisons)
├── SRS.md                         # Single Source of Truth specification
├── README.md                      # Developer onboarding and project entry point
├── RANDOM_SEARCH_FORMAL_100.md    # Formal 100-evaluation Random Search report
├── RANDOM_SEARCH_RESCORING_07_03.md # Random Search 0.7/0.3 offline re-scoring report
├── RE_AUDIT_PHASE_0_4.md          # Pipeline re-audit report (20/20 tests pass)
├── CONTEXT.md                     # Engineering journal and decision log
├── requirements.txt               # Pinned Python package dependencies
├── .gitignore                     # Ignore SPICE binary outputs (*.raw, *.db)
│
├── configs/                       # Configuration files
│   ├── optimization_config.yaml   # Primary simulation & legacy optimizer configuration
│   └── bayesian_optimization_config.yaml # Dedicated frozen BO campaign configuration
│
├── circuits/                      # SPICE circuit definitions
│   ├── baseline/                  # Human-readable LTspice schematic reference
│   ├── templates/                 # Parameterized SPICE netlist template (.net)
│   └── models/                    # Transistor model definitions
│
├── src/                           # Source implementation modules
│   ├── optimization/              # Optimization engines (BayesianOptimizer, RandomSearchOptimizer)
│   ├── ltspice/                   # Netlist parameterizer & log parser
│   ├── simulation/                # Subprocess runner with watchdog timeout
│   ├── evaluation/                # Electrical metric extractor & objective evaluator
│   └── utils/                     # Configuration validator & logger
│
├── experiments/                   # Experiment execution scripts & results
│   ├── run_formal_random_search_100.py # Formal 100-iteration RS campaign script
│   ├── run_bayesian_opt_scenario_a.py  # Scenario A BO physical runner
│   ├── run_bayesian_opt_scenario_b.py  # Scenario B BO physical runner
│   ├── analyze_formal_100.py          # Analysis script for formal RS dataset
│   │
│   ├── random_search/
│   │   ├── exploratory_10/         # Exploratory Batch 1 (N=10)
│   │   ├── exploratory_30_boundary/# Exploratory Batch 2 (N=30)
│   │   ├── exploratory_50_focused/ # Exploratory Batch 3 (N=50)
│   │   └── formal_100/             # Authoritative Formal RS Dataset (100 evals)
│   │
│   └── bayesian_optimization/
│       ├── scenario_05_05/         # BO Scenario A (Balanced 0.5/0.5, Seed 2026)
│       │   ├── results.csv         # Physical results ledger (50 evals)
│       │   ├── checkpoint.json     # Campaign checkpoint & best candidate
│       │   ├── config.json         # Campaign configuration metadata
│       │   ├── summary.md          # Execution summary
│       │   ├── raw_results/        # 50 physical SPICE netlists & logs
│       │   └── analysis/           # Markdown report, comparison CSV, 5 plots
│       │
│       └── scenario_07_03/         # BO Scenario B (Speed-Priority 0.7/0.3, Seed 3031)
│           ├── results.csv         # Physical results ledger (50 evals)
│           ├── checkpoint.json     # Campaign checkpoint & best candidate
│           ├── config.json         # Campaign configuration metadata
│           ├── summary.md          # Execution summary
│           ├── raw_results/        # 50 physical SPICE netlists & logs
│           └── analysis/           # Markdown report, comparison CSV, 4 plots
│
├── results/                       # Consolidated processed data & plots
└── tests/                         # Automated unit & integration tests
```

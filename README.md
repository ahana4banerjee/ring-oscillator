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

| Phase / Experiment | Status | Physical Evals | Scalar Obj Evals | Key Output / Artifact |
| :--- | :--- | :---: | :---: | :--- |
| **Phases 0–4 (Infrastructure & Pipeline)** | **COMPLETE** | N/A | N/A | [RE_AUDIT_PHASE_0_4.md](RE_AUDIT_PHASE_0_4.md) (20/20 tests pass) |
| **Exploratory Random Search** | **COMPLETE** | 90 | 90 | 3 campaigns (10 pilot + 30 boundary + 50 focused) |
| **Formal Search Space Decision** | **FROZEN** | N/A | N/A | $W_n \in [0.12, 1.20]\mu\text{m}, W_p \in [0.24, 2.80]\mu\text{m}$, 10 nm grid (**TBD-03**) |
| **Formal RS Scenario A (0.5/0.5)** | **COMPLETE** | 100 | 100 | [RANDOM_SEARCH_FORMAL_100.md](RANDOM_SEARCH_FORMAL_100.md) (Seed 2026) |
| **Formal RS Scenario B (0.7/0.3)** | **COMPLETE** | **0** (Offline re-scored) | 100 | [RANDOM_SEARCH_RESCORING_07_03.md](RANDOM_SEARCH_RESCORING_07_03.md) |
| **BO Engine (`src/optimization/bayesian.py`)** | **REFINED & VERIFIED (Step 6.1.1)** | N/A | N/A | 17/17 unit tests pass (`tests/test_bayesian.py`) |
| **BO Campaign A (0.5/0.5)** | **PENDING APPROVAL** | 50 (Planned) | 50 (Planned) | 10 LHS + 40 adaptive GP/EI |
| **BO Campaign B (0.7/0.3)** | **PENDING APPROVAL** | 50 (Planned) | 50 (Planned) | 10 LHS + 40 adaptive GP/EI |
| **Current Completed Total** | — | **190** (90 exploratory + 100 formal) | **290** | Complete and verified |
| **Projected Final Total** | — | **290** (190 completed + 100 BO) | **390** | Formal optimization = 200 physical simulations |

---

## 7. Bayesian Optimization: Status & Next Step

### 7.1 Current Status: Engine Refined & Verified (Step 6.1.1)
The Bayesian Optimization Engine (`BayesianOptimizer` in `src/optimization/bayesian.py`) has been fully refined and unit-verified across 17 test cases (`tests/test_bayesian.py`):
- **ISS-01 (Standardized Domain EI):** Expected Improvement evaluated in the standardized target domain with $\xi = 0.01\sigma_y$, guaranteeing scale-invariant exploration across both Scenario A and Scenario B.
- **ISS-02 (Fallback Selection):** Fallback condition corrected to `max_unvisited_ei > 0.0`; when non-positive, selects unvisited candidate with maximum posterior predictive mean $\mu(\mathbf{x})$, strictly excluding previously evaluated points.
- **ISS-03 (Conditioned Penalties):** Failed observations ($\mathcal{F}_{penalty} = -1.0\times 10^9$) are recorded verbatim in `self.history`, while GP training target scores are conditioned to a soft penalty floor ($\min(y_{feas}) - \max(2\sigma_{feas}, 0.2)$) to prevent numerical distortion of covariance fitting.
- **ISS-04 (Configuration Decoupling):** Dedicated `configs/bayesian_optimization_config.yaml` created with frozen bounds ($[0.12, 1.20]\mu\text{m} \times [0.24, 2.80]\mu\text{m}$, 28,013 valid points) and strict bounds validator `validate_frozen_bounds()`, leaving legacy Random Search config intact.
- **Surrogate:** Gaussian Process Regression with Matérn 5/2 kernel and ARD lengthscales (`GaussianProcessMatern52`).
- **Initialization:** Space-filling Latin Hypercube Sampling (LHS) for the initial $N_{init} = 10$ candidates.
- **Discrete Grid Snapping:** $10\text{ nm}$ DRC grid snapping over all 28,013 valid points with duplicate avoidance.

### 7.2 Next Pending Step: Campaign Execution (Awaiting Approval)
- **Step 6.2:** Execute BO Campaign A (Scenario A: Balanced Objective $0.5/0.5$, budget 50 physical evaluations).

### 7.3 Methodological Design Principles
1. **Two Independent Objective Campaigns:**
   - **Scenario A (Balanced: 0.5f / 0.5P):** $\mathcal{F}_A = 0.5(f/f_0) - 0.5(P/P_0)$
   - **Scenario B (Speed-Priority: 0.7f / 0.3P):** $\mathcal{F}_B = 0.7(f/f_0) - 0.3(P/P_0)$
   - Separate runs with independent evaluation budgets; no solution or surrogate transfer between scenarios.
2. **Evaluation Budget (50 Evaluations per Scenario):**
   - **Phase 1 (Initial Design):** $N_{init} = 10$ space-filling Latin Hypercube Sampling (LHS) evaluations with deterministic seeds. *(Note: These 10 points establish the initial GP prior covariance and are NOT Bayesian-guided).*
   - **Phase 2 (Adaptive BO):** $N_{adaptive} = 40$ sequential iterations guided by surrogate re-fitting and Expected Improvement maximization.
   - **Total Planned BO Physical Simulations:** 100 LTspice runs (50 Scenario A + 50 Scenario B).
3. **Strict Isolation from Benchmark Data:**
   - BO is **NOT** pre-trained or initialized with the 100 Random Search benchmark evaluations. It begins with its own clean budget.
4. **Surrogate Model & Kernel:**
   - **Model:** Gaussian Process Regression (GPR).
   - **Kernel:** Matérn 5/2 covariance kernel with Automatic Relevance Determination (ARD) lengthscales $\ell_{W_n}, \ell_{W_p}$.
   - **Normalization:** Inputs normalized to $[0, 1]^2$; objective outputs standardized.
   - **Noise Handling:** Numerical nugget $\sigma_n^2 \approx 10^{-6}$ added to covariance diagonal for Cholesky solver stability.
   - **Fitting Policy:** Log Marginal Likelihood maximization via L-BFGS-B at each adaptive step.
5. **Acquisition Function:**
   - **Expected Improvement (EI):** $\alpha_{EI}(\mathbf{x}) = \mathbb{E}[\max(0, \mathcal{F}(\mathbf{x}) - \mathcal{F}^+ - \xi)]$ with exploration jitter $\xi = 0.01$.
6. **Search Space & 10 nm Grid Discretization:**
   - Frozen bounds: $W_n \in [0.12, 1.20]\mu\text{m}$, $W_p \in [0.24, 2.80]\mu\text{m}$ (28,013 valid candidate points).
   - Unconstrained aspect ratio ($W_n$ and $W_p$ sampled independently; no artificial $W_p=2W_n$ constraints).
   - Continuous proposals snapped to $10\text{ nm}$ DRC grid.
   - **Duplicate Mitigation:** Already-evaluated coordinates are rejected by querying the discrete acquisition surface for the next-best unvisited grid candidate.
7. **Fair Benchmarking Framework:**
   - **Equal-Budget Comparison (Primary):** Random Search first 50 physical evaluations vs. BO 50 total evaluations.
   - **Full Random Search Reference:** Random Search 100 physical evaluations vs. BO 50 evaluations.
   - Convergence tracking: Best-so-far curves compared across evaluations 1 to 50.
8. **Methodological Limitations & Constraints:**
   - Results represent empirical findings within a numerical optimization study using a generic Level-1 MOS model at 40 nm, not a silicon-calibrated foundry PDK.
   - BO provides no mathematical proof of global optimality; all reporting uses "best observed candidate".
   - Success is defined by rigorous methodology and execution parity, not guaranteed outperformance over Random Search.

### 7.4 Resolved Configuration Decoupling (ISS-04 Resolved)
- BO configuration has been decoupled from legacy Random Search configuration. A dedicated configuration file `configs/bayesian_optimization_config.yaml` contains the frozen bounds ($W_n \in [0.12, 1.20]\mu\text{m}$, $W_p \in [0.24, 2.80]\mu\text{m}$, 28,013 valid points) and campaign parameters.
- Legacy `configs/optimization_config.yaml` is retained intact for Random Search regression testing.
- `src/optimization/bayesian.py` enforces frozen bounds validation via `validate_frozen_bounds()`, preventing silent inheritance of legacy bounds.

---

## 8. Repository Structure

```text
ring-oscillator/
├── SRS.md                         # Single Source of Truth specification
├── README.md                      # Developer onboarding and project entry point
├── RANDOM_SEARCH_FORMAL_100.md    # Formal 100-evaluation Random Search report
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

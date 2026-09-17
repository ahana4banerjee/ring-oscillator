# Software Requirements Specification (SRS)

## Automated Optimization of a CMOS Ring Oscillator Using Bayesian Optimization and LTspice

---

## 1. Project Overview

This project implements an automated, software-driven circuit optimization pipeline that couples Python-based numerical optimization algorithms with the LTspice electronic circuit simulator. The target under test is a 5-stage CMOS ring oscillator. The pipeline automatically searches the transistor sizing design space (specifically NMOS channel width $W_n$ and PMOS channel width $W_p$) to discover Pareto-optimal or objective-maximizing parameter configurations across oscillation frequency, power dissipation, and propagation delay.

The system provides two comparative optimization engines:
1. **Bayesian Optimization (BO)** as the primary, sample-efficient surrogate-model-guided search strategy.
2. **Random Search (RS)** as an unbiased baseline comparison strategy executing across the identical parameter bounds and evaluation pipeline.

---

## 2. Purpose and Scope

### 2.1 Purpose
This document serves as the formal **Single Source of Truth (SSOT)** for all software and hardware-simulation implementation decisions, architectural boundaries, component interfaces, failure handling protocols, data contracts, and verification criteria.

### 2.2 Scope
- **In Scope:**
  - Automated generation, parameterization, and netlist injection for LTspice simulations.
  - Headless execution and process management of LTspice from Python on Windows/POSIX environments.
  - Raw simulation waveform parsing and electrical metric extraction (`.measure` logs and/or raw transient output parsing).
  - Multi-metric objective function calculation and configurable constraint verification.
  - Implementation of Bayesian Optimization and Random Search algorithms.
  - Persistent, reproducible experiment tracking, structured tabular/JSON logging, and analytical visualization.
  - Fault tolerance, process timeout handling, convergence failure mitigation, and non-oscillation handling.
- **Out of Scope:**
  - Academic research paper drafting, literature review, and manuscript preparation.
  - Silicon tape-out, physical layout design (GDSII), and post-layout parasitics extraction (PEX) (reserved for future work).
  - Manual interactive circuit schematic tuning via GUI.

---

## 3. Goals and Non-Goals

### 3.1 Goals
- **G-1 Modular Separation:** Maintain strict decoupling between optimization math, circuit simulation execution, measurement extraction, and persistence.
- **G-2 Black-Box Circuit Interface:** Ensure the optimizer interacts with LTspice exclusively via a well-defined candidate evaluation contract `evaluate(params) -> dict[metric, float]`.
- **G-3 Complete Experiment Traceability:** Log every candidate evaluation (successful or failed) with input vectors, metrics, timestamp, duration, and failure diagnostics.
- **G-4 Deterministic Reproducibility:** Ensure optimization trajectories can be identically repeated when supplied with identical random seeds and configuration profiles.
- **G-5 Robust Crash Recovery:** Prevent single-simulation crashes (convergence faults, singular matrix, timeouts) from aborting long-running optimization campaigns.

### 3.2 Non-Goals
- **NG-1 Arbitrary Topology Optimization:** The system is not intended to evolve or alter circuit topology; the 5-stage ring inverter chain remains structurally invariant.
- **NG-2 Dynamic Netlist Synthesis:** The circuit netlist structure is statically parameterized, not generated through symbolic code synthesis.
- **NG-3 Real-Time Hardware-in-the-Loop:** Simulations run purely in numerical simulation; physical instrumentation is not interfaced.

---

## 4. System Overview & Architecture

### 4.1 Architecture Diagram

```
+---------------------------------------------------------------------------------------+
|                                    Python Layer                                       |
|                                                                                       |
|  +------------------------+                +---------------------------------------+  |
|  |  Optimization Engine   |                |         Experiment Manager            |  |
|  |  (Bayesian Opt / RS)   |                |  - Run Logger (CSV / JSON / SQLite)   |  |
|  +-----------+------------+                |  - Artifact Store & Plotting          |  |
|              |                             +-------------------+-------------------+  |
|              | Candidate [Wn, Wp]                              ^                      |
|              v                                                 | Metrics & Result     |
|  +------------------------+                +-------------------+-------------------+  |
|  | Circuit Parameterizer  |                |         Evaluation Engine             |  |
|  | - Template Injection   |                |  - Raw Log / Raw Waveform Parser      |  |
|  | - .param Wn=.. Wp=..   |                |  - Metric Validator & Objective Calc  |  |
|  +-----------+------------+                +-------------------+-------------------+  |
|              |                                                 ^                      |
|              | Parameterized Netlist / .cir                    | .log / .raw Files    |
|              v                                                 |                      |
|  +-------------------------------------------------------------+-------------------+  |
|  |                         LTspice Execution Harness                               |  |
|  |  - Batch Process Invocation (`scad3.exe` / `XVIIx64.exe` / `LTspice.exe` -b)    |  |
|  |  - Timeout & Subprocess Watchdog                                               |  |
|  +-------------------------------------+-------------------------------------------+  |
+----------------------------------------|----------------------------------------------+
                                         | CLI Invocation
                                         v
                         +-------------------------------+
                         |     LTspice Engine (SPICE)    |
                         | - Transient Analysis (.tran)  |
                         | - SPICE Measurement (.meas)   |
                         +-------------------------------+
```

### 4.2 Data Flow Pipeline

```
Step 1: Optimizer proposes candidate parameter vector: theta = [Wn, Wp]
  |
Step 2: Circuit Parameterizer writes or updates SPICE netlist with .param Wn=... Wp=...
  |
Step 3: Execution Harness triggers LTspice batch mode with watchdog timeout (e.g., -b -Run netlist.cir)
  |
Step 4: LTspice executes transient simulation and outputs simulation .log and/or .raw files
  |
Step 5: Output Parser inspects return code, reads .log, and extracts frequency, power, delay
  |
Step 6: Evaluation Engine validates oscillation sanity checks:
        - If valid: calculates scalar objective f(theta)
        - If failed/non-oscillating: triggers fallback penalty policy without crashing
  |
Step 7: Experiment Manager records (Experiment_ID, Iteration, Wn, Wp, Freq, Power, Delay, Objective, Status)
  |
Step 8: Optimizer updates internal surrogate model / observation history with (theta, f(theta))
  |
Step 9: Optimizer queries acquisition function for next candidate until max_iterations reached
```

---

## 5. Component Responsibilities

| Component | Responsibility Module | Primary Inputs | Primary Outputs |
| :--- | :--- | :--- | :--- |
| **Config Loader** | `src/utils/config.py` | `configs/optimization_config.yaml` | Validated configuration schema |
| **Optimization Engine** | `src/optimization/` | Search space config, iteration budgets, priors | Candidate vectors `[Wn, Wp]` |
| **Circuit Parameterizer** | `src/ltspice/parameterizer.py`| Baseline netlist template, candidate values | Run-specific netlist (`.cir` / `.net`) |
| **Simulation Harness** | `src/simulation/runner.py` | Run-specific netlist, timeout duration | Process exit code, `.log`, `.raw` paths |
| **Measurement Extractor**| `src/evaluation/extractor.py` | LTspice `.log` and/or `.raw` files | Raw electrical metrics dictionary |
| **Objective Evaluator** | `src/evaluation/objective.py` | Extracted metrics, weights, penalty rules | Scalar fitness score, feasibility flag |
| **Experiment Logger** | `src/utils/logger.py` | Iteration payloads, metrics, status | Tabular log entries (CSV), JSON run summary |
| **Plotting & Analytics**| `src/utils/visualizer.py` | Historical experiment logs | Optimization convergence and Pareto plots |

---

## 6. Functional Requirements

### 6.1 Configuration & Initialization
- **[REQ-CFG-01]** The system shall load all execution parameters from a single YAML file (`configs/optimization_config.yaml`).
- **[REQ-CFG-02]** The configuration must explicitly specify: search bounds, transistor length $L$, supply voltage $V_{DD}$, simulation transient stop time, maximum iterations, acquisition function, surrogate model type, random seeds, and logging directories.

### 6.2 Circuit Parameterization
- **[REQ-PAR-01]** The parameterizer shall accept candidate transistor widths $W_n$ and $W_p$ and inject them into the baseline netlist via standard SPICE `.param` statements or parameterized subcircuit calls.
- **[REQ-PAR-02]** Transistor channel length $L$ shall be held constant at the technology baseline value (or configured separately).
- **[REQ-PAR-03]** Parameter substitution must not alter non-parameterized circuit elements, power supply rails, stage interconnection topology, or measurement scripts.

### 6.3 Simulation Execution
- **[REQ-SIM-01]** The runner shall launch LTspice in batch/headless mode without graphical interface popup (`-b -Run` flags).
- **[REQ-SIM-02]** The runner shall enforce a strict per-simulation timeout threshold (configurable, default: 30 seconds) to terminate hanging or non-converging simulations.
- **[REQ-SIM-03]** Temporary run files (`.raw`, `.log`, `.net`) must either be uniquely isolated per iteration or cleanly overwritten to prevent cross-run stale data ingestion.

### 6.4 Measurement Extraction
- **[REQ-EXT-01]** The extractor shall parse the LTspice `.log` file generated by SPICE `.meas` statements.
- **[REQ-EXT-02]** Extracted raw metrics must include:
  1. Fundamental Oscillation Frequency ($f_{osc}$ in Hz).
  2. Average Dynamic + Static Power Consumption ($P_{avg}$ in Watts).
  3. Propagation Delay per Stage ($t_{pd}$ or period $T_{period}$ in seconds).
- **[REQ-EXT-03]** If `.meas` statements fail to parse or return invalid flags (e.g. "Measurement failed"), the extractor shall flag the simulation as `FAILED_MEASUREMENT`.

### 6.5 Objective Evaluation & Optimization
- **[REQ-OPT-01]** The optimization engine shall provide a uniform interface `suggest() -> dict` and `register(candidate, result) -> None` for both Bayesian Optimization and Random Search.
- **[REQ-OPT-02]** The optimization loop shall evaluate the design space across $N$ iterations specified by the configuration.
- **[REQ-OPT-03]** Bayesian Optimization shall initialize with $N_{init}$ random samples before updating the surrogate model and maximizing the acquisition function.

### 6.6 Experiment Tracking & Reporting
- **[REQ-EXP-01]** Every evaluated candidate must be appended to an experiment ledger (`results/processed/experiment_log.csv`) immediately upon evaluation.
- **[REQ-EXP-02]** When an optimization run completes, the system shall generate a structured summary artifact (`run_summary.json`) identifying the optimal parameter set, best objective score, total execution time, and failure rate.
- **[REQ-EXP-03]** The visualizer shall generate Pareto comparison plots and convergence curves comparing Bayesian Optimization against Random Search.

---

## 7. Non-Functional Requirements

- **[NFR-REL-01] Robustness:** An unhandled simulation crash or non-oscillating circuit candidate must never terminate the Python parent process.
- **[NFR-PER-02] Simulation Overhead:** The Python orchestration layer must introduce $< 100\text{ ms}$ processing overhead per iteration beyond the raw LTspice execution time.
- **[NFR-MNT-03] Modularity:** The optimization algorithm backend must be decoupled from the simulation backend; swapping Bayesian Optimization libraries (e.g., BoTorch, scikit-optimize, Optuna) must require changes only within `src/optimization/`.
- **[NFR-ENV-04] Portability:** The path to the LTspice executable must be configurable via configuration file or environment variable (`LTSPICE_EXECUTABLE_PATH`).
- **[NFR-DAT-05] Data Integrity:** Experiment logs must use atomic append operations or write-flushes to prevent log corruption in case of unexpected termination.

---

## 8. Baseline Circuit Specification

### 8.1 Circuit Topology
- **Type:** 5-stage CMOS inverter chain configured in a closed ring.
- **Number of Inverter Stages ($N_{stages}$):** 5.
- **Transistor Models:** Predictive Technology Model (PTM) or standard CMOS PDK model (e.g., TSMC 180nm, BSIM4 45nm, or generic CMOS models). *(Exact model file: TBD / Open Decision based on existing baseline setup)*.
- **Supply Voltage ($V_{DD}$):** Configurable (Nominal: TBD, typical 1.8V for 180nm, 1.2V for 90nm/65nm, or 1.0V for 45nm).
- **Oscillation Trigger:** Transient initial condition (`.ic V(out1)=0` or pulse initial disturbance) to kick-start oscillation from metastable state.

### 8.2 Baseline Parameter Table

| Parameter | Symbol | Nominal Baseline Value | Status |
| :--- | :--- | :--- | :--- |
| Number of Stages | $N$ | 5 | **Fixed** |
| Channel Length | $L_n, L_p$ | `TBD` (e.g. 180nm, 45nm) | Open Decision |
| Baseline NMOS Width | $W_{n,base}$ | `TBD` | Open Decision |
| Baseline PMOS Width | $W_{p,base}$ | `TBD` | Open Decision |
| Supply Voltage | $V_{DD}$ | `TBD` (e.g. 1.8V / 1.2V) | Open Decision |
| Transient Duration | $t_{stop}$ | `TBD` (e.g. 100ns, sufficient for $\ge 20$ cycles) | Open Decision |
| Transient Start Save | $t_{start}$ | `TBD` (discard initial transient startup phase) | Open Decision |
| Max Time Step | $t_{step}$ | `TBD` (e.g. 10ps) | Open Decision |

---

## 9. Optimization Variables & Search Space

### 9.1 Variable Definitions

| Variable Name | Symbol | Units | Nature | Grid Step / Resolution | Search Range |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `nmos_width` | $W_n$ | Meters ($\mu\text{m}$) | Continuous or Discrete Grid | `TBD` (e.g., $10\text{ nm}$ or continuous) | $[W_{n,min}, W_{n,max}]$ (`TBD`) |
| `pmos_width` | $W_p$ | Meters ($\mu\text{m}$) | Continuous or Discrete Grid | `TBD` (e.g., $10\text{ nm}$ or continuous) | $[W_{p,min}, W_{p,max}]$ (`TBD`) |

### 9.2 Sizing Constraints & Validity Rules
1. **Physical Aspect Ratio:** $\frac{W_p}{W_n}$ typically lies between $1.0$ and $5.0$ to balance rise/fall times, but the search space may explore beyond this ratio unless explicitly restricted.
2. **Fabrication Grid Snapping:** If manufacturing grid discretization is enabled, floating-point candidates from the optimizer shall be rounded to the nearest discrete DRC grid step (e.g., $5\text{ nm}$ or $10\text{ nm}$) prior to netlist injection.
3. **Out-of-Bound Mitigation:** Candidate proposals violating minimum transistor sizing rules ($W < W_{min}$) are clamped to boundaries or assigned an immediate infeasible penalty.

---

## 10. Simulation Engine & Parameterization

### 10.1 Netlist Injection Strategy
Two injection approaches are supported:
- **Approach A (Recommended - Parameter Override):** Maintain a static netlist template `ring_oscillator.net` containing explicit SPICE parameters:
  ```spice
  .param Wn=0.5u
  .param Wp=1.0u
  ```
  During each iteration, the parameterizer generates an overlay include file (`params.inc`) or rewrites a working copy netlist (`run_temp.cir`) with:
  ```spice
  .param Wn={candidate_wn}
  .param Wp={candidate_wp}
  ```
- **Approach B (Schematic CLI Modification):** Not recommended due to binary/GUI coupling of `.asc` files. Netlist-level (`.cir` / `.net`) manipulation shall be the primary execution target.

### 10.2 SPICE Transient & Measurement Control Block

The netlist will incorporate SPICE `.meas` statements to automate measurement extraction inside LTspice:
```spice
* Transient Analysis: Run 100ns, start measuring after 20ns startup transient
.tran 0 100n 20n 10p

* Frequency Measurement on Node V(out)
.meas TRAN Tperiod TRIG V(out)=0.5*Vdd RISE=5 TARG V(out)=0.5*Vdd RISE=6
.meas TRAN Freq PARAM 1/Tperiod

* Propagation Delay per stage: Tperiod / (2 * N_stages)
.meas TRAN Tpd PARAM Tperiod/10

* Average Power Dissipation over steady-state oscillation window
.meas TRAN AvgPower AVG -V(Vdd)*I(Vsupply) FROM=20n TO=100n
```
*(Note: Threshold voltages and cycle counts will be parameterized in `configs/optimization_config.yaml`).*

---

## 11. Objective Function Formulation

The optimization problem seeks to explore the fundamental trade-offs between speed (frequency), energy (power), and delay.

### 11.1 Metric Classification
1. **Raw Measurements:**
   - $T_{period}$ [s]: Oscillation period.
   - $P_{avg}$ [W]: Total average power drawn from $V_{DD}$.
2. **Derived Metrics:**
   - $f_{osc} = \frac{1}{T_{period}}$ [Hz]: Oscillation frequency.
   - $t_{pd} = \frac{T_{period}}{2 \times N_{stages}}$ [s]: Stage propagation delay ($N=5$).
   - $PDP = P_{avg} \times t_{pd}$ [Joules]: Power-Delay Product per switching event.
   - Energy per cycle $E_{cycle} = \frac{P_{avg}}{f_{osc}}$ [Joules].

### 11.2 Scalar Objective Formulations (Configurable)

The engine shall support configurable optimization modes defined in `configs/optimization_config.yaml`:

- **Mode 1: Maximum Frequency subject to Power Constraint**
  $$\max W(W_n, W_p) = f_{osc} \quad \text{s.t.} \quad P_{avg} \le P_{max}$$

- **Mode 2: Minimum Power-Delay Product (PDP)**
  $$\min \text{PDP} = P_{avg} \cdot t_{pd}$$

- **Mode 3: Weighted Multi-Objective Utility Function**
  $$\max \mathcal{F}(W_n, W_p) = w_f \cdot \left(\frac{f_{osc}}{f_{norm}}\right) - w_p \cdot \left(\frac{P_{avg}}{P_{norm}}\right)$$
  Where:
  - $w_f, w_p \ge 0$ are user-specified importance weights ($w_f + w_p = 1.0$).
  - $f_{norm}, P_{norm}$ are normalization scalars derived from the nominal baseline design.

*(Exact choice of primary objective mode and weights: **TBD / Open Decision**; the implementation shall support all modes via configuration).*

---

## 12. Optimization Algorithms

### 12.1 Bayesian Optimization (Primary)
- **Surrogate Model:** Gaussian Process Regression (GPR) with Matérn 5/2 or RBF covariance kernel.
- **Acquisition Function:** Expected Improvement (EI), Upper Confidence Bound (UCB), or Probability of Improvement (PI) (Configurable, default: EI).
- **Exploration/Exploitation Parameter:** $\xi = 0.01$ (for EI) or $\beta = 2.0$ (for UCB).
- **Initial Design:** Latin Hypercube Sampling (LHS) or Uniform Random Initialization with $N_{init}$ points (default: 5 to 10 points).
- **Candidate Search:** Quasi-Newton (L-BFGS-B) optimization over the continuous acquisition surface, followed by snapping to manufacturing resolution if applicable.

### 12.2 Random Search (Baseline)
- **Sampling Strategy:** Independent and identically distributed (i.i.d.) uniform random sampling across the bounded domain:
  $$W_n \sim \mathcal{U}(W_{n,min}, W_{n,max}), \quad W_p \sim \mathcal{U}(W_{p,min}, W_{p,max})$$
- **Evaluation Parity:** Uses the exact same execution harness, timeout settings, objective formulation, and result logger as Bayesian Optimization.

---

## 13. Failure Handling & Circuit Fault Detection

Simulations can fail due to physical, numerical, or environment defects. The pipeline enforces non-crashing graceful degradation.

| Failure Mode | Detection Condition | Pipeline Action | Logged Status | Objective Penalty Score |
| :--- | :--- | :--- | :--- | :--- |
| **Timeout** | Subprocess execution duration $> t_{limit}$ | Kill process PID tree, record timeout | `TIMEOUT` | $f_{penalty} = -1.0 \times 10^{9}$ (or configurable min) |
| **SPICE Convergence Error** | Return code $\ne 0$ or "Iteration limit reached" in `.log` | Parse error log, clean up locks | `CONVERGENCE_FAIL` | $f_{penalty}$ |
| **Non-Oscillation** | Node voltage steady-state $V(out)$ has zero crossings $< 4$ | Waveform / measurement fails threshold trigger | `NO_OSCILLATION` | $f_{penalty}$ |
| **Measurement Parsing Failure** | `.meas` key missing or evaluated as NaN | Fallback to raw parsing or flag error | `MEAS_PARSE_FAIL` | $f_{penalty}$ |
| **Process Crash** | Subprocess returns non-zero OS code | Capture stderr stream | `EXEC_ERROR` | $f_{penalty}$ |

---

## 14. Experiment Tracking & Data Persistence

### 14.1 Log Record Schema (`results/processed/experiment_log.csv`)

Every evaluated candidate appends a standardized row:
1. `experiment_id` (str): Unique UUID or timestamp hash for the campaign.
2. `iteration` (int): Sequential evaluation index ($0, 1, \dots, N-1$).
3. `method` (str): `BAYESIAN_OPT` or `RANDOM_SEARCH`.
4. `timestamp` (str): ISO 8601 UTC timestamp.
5. `wn_um` (float): NMOS channel width in microns.
6. `wp_um` (float): PMOS channel width in microns.
7. `status` (str): `SUCCESS`, `NO_OSCILLATION`, `TIMEOUT`, `CONVERGENCE_FAIL`.
8. `freq_ghz` (float): Extracted oscillation frequency in GHz (NaN on failure).
9. `power_mw` (float): Extracted average power in mW (NaN on failure).
10. `delay_ps` (float): Stage propagation delay in ps (NaN on failure).
11. `objective_value` (float): Computed scalar objective score.
12. `sim_time_sec` (float): Wall-clock simulation runtime in seconds.

### 14.2 Experiment Artifact Schema (`results/processed/run_summary.json`)
```json
{
  "experiment_id": "exp_bo_20260917_001",
  "method": "Bayesian_Optimization",
  "total_evaluations": 50,
  "successful_evaluations": 48,
  "failed_evaluations": 2,
  "optimal_parameters": {
    "Wn_um": 0.65,
    "Wp_um": 1.42
  },
  "optimal_metrics": {
    "freq_ghz": 2.45,
    "power_mw": 0.85,
    "delay_ps": 40.8,
    "objective_score": 1.842
  },
  "config_snapshot": { ... }
}
```

---

## 15. Repository Structure

```
ring-oscillator/
├── SRS.md                         # Single Source of Truth specification
├── README.md                      # Developer onboarding and execution guide
├── requirements.txt               # Pinned Python package dependencies
├── .gitignore                     # Ignore SPICE outputs (.raw, .log, .net), artifacts
│
├── configs/                       # Configuration files
│   └── optimization_config.yaml   # Primary simulation & optimizer configuration
│
├── circuits/                      # SPICE circuit definitions
│   ├── baseline/
│   │   └── ring_oscillator.asc    # Human-readable LTspice schematic reference
│   ├── templates/
│   │   └── ring_oscillator.net    # Parameterized SPICE netlist template
│   └── models/                    # Transistor model libraries (PTM / BSIM4)
│       └── tbd_transistor.model   # Model file (TBD)
│
├── src/                           # Source implementation modules
│   ├── optimization/              # Optimization engines
│   │   ├── base.py                # Abstract optimizer base class
│   │   ├── bayesian.py            # Gaussian Process / Bayesian Optimization
│   │   └── random_search.py       # Random Search baseline
│   ├── ltspice/                   # LTspice interface utilities
│   │   ├── parameterizer.py       # Netlist parameter injection
│   │   └── parser.py              # .log and .raw output file parsers
│   ├── simulation/                # Subprocess management
│   │   └── runner.py              # Headless LTspice execution with watchdog
│   ├── evaluation/                # Metrics and fitness calculation
│   │   ├── extractor.py           # Electrical metric extractor
│   │   └── objective.py           # Objective / utility calculation
│   └── utils/                     # System utilities
│       ├── config.py              # YAML config loader and validator
│       ├── logger.py              # Structured CSV/JSON experiment logger
│       └── visualizer.py          # Convergence and Pareto plotting scripts
│
├── experiments/                   # Experiment scripts and campaign runs
│   ├── run_baseline.py            # Single run on baseline circuit
│   ├── run_random_search.py       # Random Search campaign runner
│   ├── run_bayesian_opt.py        # Bayesian Optimization campaign runner
│   └── compare_methods.py         # Comparative analysis script
│
├── results/                       # Generated outputs
│   ├── raw/                       # Cached simulation logs (optional/ephemeral)
│   ├── processed/                 # Consolidated CSV logs & JSON summaries
│   └── plots/                     # Output figures (convergence, Pareto frontier)
│
├── tests/                         # Automated unit & integration tests
│   ├── test_config.py             # Config validation tests
│   ├── test_parameterizer.py      # Netlist formatting tests
│   ├── test_parser.py             # SPICE log parsing tests
│   └── test_objective.py          # Objective evaluation logic tests
│
└── scripts/                       # Developer utility scripts
    └── check_ltspice_install.py   # Verify LTspice path and CLI functionality
```

---

## 16. Implementation Phasing & Roadmap

```
+-----------+    +-----------+    +-----------+    +-----------+    +-----------+
|  Phase 0  | -> |  Phase 1  | -> |  Phase 2  | -> |  Phase 3  | -> |  Phase 4  |
| Envt/Deps |    | Baseline  |    | Netlist & |    | Metric    |    | Objective |
|   Setup   |    | SPICE Run |    | Subproc   |    | Extractor |    | Function  |
+-----------+    +-----------+    +-----------+    +-----------+    +-----------+
                                                                          |
                                                                          v
+-----------+    +-----------+    +-----------+    +-----------+    +-----------+
|  Phase 9  | <- |  Phase 8  | <- |  Phase 7  | <- |  Phase 6  | <- |  Phase 5  |
| Extended  |    | Method    |    | Logging & |    | Bayesian  |    | Random    |
| PVT Runs  |    | Comparison|    | Visuals   |    | Optimizer |    | Search    |
+-----------+    +-----------+    +-----------+    +-----------+    +-----------+
```

### Phase 0: Repository, Dependencies & Environment
- **Deliverables:** Directory structure, `requirements.txt` (numpy, scipy, scikit-optimize/optuna/botorch, matplotlib, pyyaml), `.gitignore`.
- **Completion Criteria:** Environment installs cleanly with `pip install -r requirements.txt`.

### Phase 1: Baseline Circuit Netlist Validation
- **Deliverables:** Locate/import baseline 5-stage ring oscillator schematic or netlist into `circuits/baseline/`.
- **Completion Criteria:** Standalone manual run in LTspice oscillates correctly with steady-state waveform.

### Phase 2: Python ↔ LTspice Headless Runner
- **Deliverables:** `src/ltspice/parameterizer.py`, `src/simulation/runner.py`.
- **Completion Criteria:** Python script successfully launches LTspice in batch mode, completes transient run, and generates `.log` file without GUI popup.

### Phase 3: Measurement Extraction Engine
- **Deliverables:** `src/ltspice/parser.py`, `src/evaluation/extractor.py`.
- **Completion Criteria:** Python accurately extracts frequency, power, and period from SPICE `.log` output into a validated dictionary.

### Phase 4: Objective Formulation & Penalty Engine
- **Deliverables:** `src/evaluation/objective.py`.
- **Completion Criteria:** Unit tests pass verifying valid metric scoring and penalty assignment for invalid/non-oscillating inputs.

### Phase 5: Random Search Baseline Engine
- **Deliverables:** `src/optimization/random_search.py`, `experiments/run_random_search.py`.
- **Completion Criteria:** 20-iteration Random Search runs end-to-end and outputs structured CSV records.

### Phase 6: Bayesian Optimization Engine
- **Deliverables:** `src/optimization/bayesian.py`, `experiments/run_bayesian_opt.py`.
- **Completion Criteria:** 20-iteration BO runs end-to-end, fitting GP surrogate and exploring design space.

### Phase 7: Experiment Logging, Persistence & Visualization
- **Deliverables:** `src/utils/logger.py`, `src/utils/visualizer.py`.
- **Completion Criteria:** Automated generation of `experiment_log.csv`, `run_summary.json`, and convergence/Pareto comparison curves in `results/plots/`.

### Phase 8: Systematic Comparison & Validation
- **Deliverables:** `experiments/compare_methods.py`.
- **Completion Criteria:** Benchmark run of BO vs. RS across identical budgets ($N=50$ or $100$) demonstrating convergence efficiency.

### Phase 9: Extended Experiments (PVT Operating Variations - Optional)
- **Deliverables:** Config-driven sweep over supply voltage $V_{DD}$ ($\pm 10\%$) and temperature ($-40^\circ\text{C}$ to $125^\circ\text{C}$).
- **Completion Criteria:** Sizing sensitivity under operational variations documented in experiment logs.

---

## 17. Verification and Testing Strategy

### 17.1 Unit Tests (`pytest`)
- `tests/test_config.py`: Verify missing/corrupted YAML keys trigger informative validation exceptions.
- `tests/test_parameterizer.py`: Verify candidate $W_n, W_p$ floats are correctly formatted into SPICE engineering notation (e.g. `0.5u`, `180n`).
- `tests/test_parser.py`: Verify regex parsers accurately extract frequency and power from simulated mock `.log` files (including measurement failure lines).
- `tests/test_objective.py`: Verify mathematical score calculation, normalization, and penalty handling for corner cases.

### 17.2 Integration Tests
- `tests/test_ltspice_integration.py`: End-to-end test running a single headless simulation on a minimal inverter/oscillator netlist, confirming process exit code 0 and valid measurement extraction.

---

## 18. Definition of Done (DoD)

The project implementation will be declared complete when:
1. [x] Baseline 5-stage ring oscillator netlist is confirmed functional in LTspice.
2. [x] $W_n$ and $W_p$ are dynamically parameterizable via Python without manual netlist edits.
3. [x] Python automates batch LTspice execution with robust timeout and process watchdog handling.
4. [] Oscillation frequency, power consumption, and propagation delay are parsed reliably.
5. [] Objective evaluation handles both valid outputs and failed/non-oscillating circuits.
6. [] Random Search executes over the defined search space under the unified evaluation contract.
7. [] Bayesian Optimization executes over the identical search space with GP surrogate updating.
8. [] All evaluations are tracked in structured CSV and JSON log artifacts.
9. [] Results are reproducible given the same random seed and configuration file.
10. [] A comparison script generates Pareto frontier and convergence curves comparing BO vs. RS.
11. [] Automated test suite (`pytest`) covers configuration, parameterization, and parsing modules.

---

## 19. Open Decisions and TBD Inventory

The following items are deliberately classified as **TBD / Open Decision** pending initial baseline circuit inspection and user confirmation:

| ID | Item Description | Status / Default Assumption | Impact Area |
| :--- | :--- | :--- | :--- |
| **TBD-01** | **Physical Transistor Technology Node & Models** | TBD (e.g., TSMC 180nm, BSIM4 45nm PTM, or default LTspice CMOS) | Circuit files, length $L$ |
| **TBD-02** | **Nominal Supply Voltage ($V_{DD}$)** | TBD (1.8V for 180nm, 1.2V for 90nm/65nm, 1.0V for 45nm) | SPICE netlist & power |
| **TBD-03** | **Search Space Bounds ($W_{n,min..max}$, $W_{p,min..max}$)** | TBD (e.g., $W_n \in [0.18\mu\text{m}, 2.0\mu\text{m}]$, $W_p \in [0.36\mu\text{m}, 4.0\mu\text{m}]$) | Optimizer configuration |
| **TBD-04** | **Specific Bayesian Optimization Library** | TBD (`scikit-optimize`, `Optuna`, or `BoTorch`/`GPyOpt`) | `src/optimization/bayesian.py` |
| **TBD-05** | **Exact Objective Function Formulation & Weights** | TBD (Default: Weighted multi-objective $\mathcal{F} = w_f \frac{f}{f_0} - w_p \frac{P}{P_0}$) | `src/evaluation/objective.py` |
| **TBD-06** | **LTspice Installation Path on Target OS** | TBD (Configurable via `configs/optimization_config.yaml`) | Subprocess runner |

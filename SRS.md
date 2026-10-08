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
- **Technology Node & Transistor Models:** 40 nm CMOS scaling assumption ($L_n = L_p = 40\text{ nm} = 0.04\mu\text{m}$). Generic Level-1 MOS model (`.model NMOS NMOS(LEVEL=1 VTO=0.15 KP=20m)`, `.model PMOS PMOS(LEVEL=1 VTO=-0.15 KP=10m)`) active for fast numerical simulation optimization (**TBD-01 RESOLVED**). *(Note: Level-1 MOS model is a simplified simulation model and is not a calibrated foundry BSIM4 PDK).*
- **Supply Voltage ($V_{DD}$):** Fixed at $V_{DD} = 1.1\text{ V}$ (**TBD-02 RESOLVED**).
- **Oscillation Trigger:** Transient initial condition (`.ic V(n002)=0` or `.ic V(OSC)=0`) to kick-start oscillation from metastable state.

### 8.2 Baseline Parameter Table

| Parameter | Symbol | Nominal Baseline Value | Status |
| :--- | :--- | :--- | :--- |
| Number of Stages | $N$ | 5 | **Fixed** |
| Channel Length | $L_n, L_p$ | $40\text{ nm} = 0.04\mu\text{m}$ | **Resolved (TBD-01)** |
| Supply Voltage | $V_{DD}$ | $1.1\text{ V}$ | **Resolved (TBD-02)** |
| Baseline NMOS Width | $W_{n,base}$ | $0.5\mu\text{m}$ | **Fixed Baseline** |
| Baseline PMOS Width | $W_{p,base}$ | $1.0\mu\text{m}$ | **Fixed Baseline** |
| Stage Load Capacitances | $C_1 .. C_5$ | $0.5\text{ fF}$ | **Fixed Baseline** |
| Baseline Frequency | $f_0$ | $41.0697566491\text{ GHz}$ | **Validated Baseline** |
| Baseline Power | $P_0$ | $140.169553568\mu\text{W}$ | **Validated Baseline** |
| Stage Propagation Delay | $t_{pd}$ | $2.434881727\text{ ps}$ | **Validated Baseline** |
| Transient Duration | $t_{stop}$ | $1\text{ ns}$ ($\ge 40$ cycles) | **Fixed** |
| Transient Start Save | $t_{start}$ | $0.2\text{ ns}$ | **Fixed** |
| Max Time Step | $t_{step}$ | $0.01\text{ ps}$ | **Fixed** |

---

## 9. Optimization Variables & Search Space

### 9.1 Variable Definitions

| Variable Name | Symbol | Units | Nature | Grid Step / Resolution | Frozen Search Range | Resolution Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `nmos_width` | $W_n$ | Meters ($\mu\text{m}$) | Discrete DRC Grid | $10\text{ nm} = 0.01\mu\text{m}$ | $[0.12\mu\text{m}, 1.20\mu\text{m}]$ | **RESOLVED (TBD-03)** |
| `pmos_width` | $W_p$ | Meters ($\mu\text{m}$) | Discrete DRC Grid | $10\text{ nm} = 0.01\mu\text{m}$ | $[0.24\mu\text{m}, 2.80\mu\text{m}]$ | **RESOLVED (TBD-03)** |

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

### 11.2 Decided Development Objective Function

The decided development objective function is a weighted multi-objective utility formulation normalized against the verified 40 nm reference baseline:

$$\mathcal{F}(W_n, W_p) = w_f \cdot \left(\frac{f_{osc}}{f_0}\right) - w_p \cdot \left(\frac{P_{avg}}{P_0}\right)$$

Where:
- $f_{osc}$ = candidate oscillation frequency (Hz)
- $P_{avg}$ = candidate average power consumption (W)
- $f_0 = 41,069,756,649.1\text{ Hz}$ ($41.0697566491\text{ GHz}$), validated baseline frequency at $1.1\text{V}$ nominal $V_{DD}$
- $P_0 = 0.000140169553568\text{ W}$ ($140.169553568\mu\text{W}$), validated baseline power at $1.1\text{V}$ nominal $V_{DD}$
- $w_f, w_p \ge 0$ are user-specified importance weights satisfying $w_f + w_p = 1.0$

#### Decided Weight Configurations (Two Objective Scenarios):
1. **Scenario A — Balanced Objective (Config B):**
   $$w_f = 0.5, \quad w_p = 0.5 \implies \mathcal{F}_{0.5/0.5} = 0.5 \cdot \left(\frac{f_{osc}}{f_0}\right) - 0.5 \cdot \left(\frac{P_{avg}}{P_0}\right)$$
   Evaluated during the completed formal 100-evaluation Random Search campaign (yielding best observed candidate Iteration 62 with score $\mathcal{F}_{0.5/0.5} = 0.010923$).

2. **Scenario B — Frequency-Priority Objective (Config S):**
   $$w_f = 0.7, \quad w_p = 0.3 \implies \mathcal{F}_{0.7/0.3} = 0.7 \cdot \left(\frac{f_{osc}}{f_0}\right) - 0.3 \cdot \left(\frac{P_{avg}}{P_0}\right)$$
   Investigates how shifting engineering priorities from balanced trade-off optimization to frequency-priority optimization alters parameter selection.

#### Re-scoring Methodology for Scenario B Random Search:
*Crucial Methodological Distinction:* Random Search candidate sampling locations $(W_n, W_p)$ are independent of the objective weight assignment. Therefore, the Random Search benchmark for Scenario B ($0.7/0.3$) is obtained by **re-scoring the exact same 100 physical LTspice simulations** generated during the formal Random Search campaign. **NO additional circuit simulations are required or performed** for Random Search under Scenario B.

#### Baseline Normalization Consistency:
Evaluating the baseline candidate ($f_{osc}=f_0, P_{avg}=P_0$) relative to itself under balanced weights ($w_f=0.5, w_p=0.5$) satisfies:
$$\mathcal{F}_{baseline} = 0.5(1.0) - 0.5(1.0) = 0.0$$
For Scenario B ($w_f=0.7, w_p=0.3$), the baseline reference evaluates to $0.7(1.0) - 0.3(1.0) = 0.4000$. Relative score differentials $(\mathcal{F} - \mathcal{F}_{baseline})$ maintain mathematical equivalence across candidate comparisons.

#### Penalty Policy for Failed Candidates:
Candidates that fail to simulate, do not oscillate, or encounter SPICE convergence failures are assigned a scalar penalty score of $\mathcal{F}_{penalty} = -1.0 \times 10^9$. Valid candidates are evaluated using the utility formula without penalty.

### 11.3 Oscillation Validity Rule

A candidate configuration $[W_n, W_p]$ is classified as a **VALID** oscillating candidate if and only if all of the following deterministic conditions are satisfied:
1. **Simulation Health:** SPICE transient simulation process completes cleanly (return code 0) without fatal errors or singular matrix divergence.
2. **Measurable Waveform:** The output node waveform $V(\text{OSC})$ produces at least 4 threshold crossings ($0.5 \times V_{DD}$) to allow steady-state period extraction (`tperiod`).
3. **Finite Positive Period:** Extracted oscillation period $T_{period} > 0$ and is a finite number (not `None`, `NaN`, or `Inf`).
4. **Finite Positive Frequency:** Derived oscillation frequency $f_{osc} = \frac{1}{T_{period}} > 0$ and is a finite number.
5. **Internal Consistency:** Stage propagation delay $t_{pd} = \frac{T_{period}}{2 \times N_{stages}} > 0$ and power consumption $P_{avg} > 0$.

Candidates failing any condition above are assigned `status = NO_OSCILLATION` and evaluated using the penalty policy without crashing the optimization process.

*(Note: Mathematical objective function, validity rule, and physical operating parameters $V_{DD} = 1.1\text{V}$ and technology node $40\text{nm}$ are resolved under TBD-01 and TBD-02).*

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

### Phase 5 — Staged & Formal Random Search Campaigns (COMPLETE)
**Status:** **COMPLETE & VERIFIED**

Phase 5 was executed in two major stages:
1. **Exploratory Stage (90 Evaluations):** 3 exploratory campaigns (10 pilot + 30 boundary + 50 focused) were executed to map the design space feasibility and identify utility trends. Exploratory findings revealed a primary low-power / high-utility region ($W_n \le 0.30\mu\text{m}, W_p \ge 1.80\mu\text{m}$) and a secondary high-speed region at larger $W_n$.
2. **Formal Search Bounds Decision (TBD-03 RESOLVED):** Search bounds were formally frozen at:
   $$W_n \in [0.12\text{ µm}, 1.20\text{ µm}], \quad W_p \in [0.24\text{ µm}, 2.80\text{ µm}], \quad \text{Grid step } = 10\text{ nm } (0.01\mu\text{m})$$
   *(Note: The lower $W_n$ bound of $0.12\mu\text{m}$ is adopted as a conservative modeling-scope limit for the generic Level-1 MOS model. Exploratory results below $0.15\mu\text{m}$ showed increasing utility, but these results represent model extrapolation rather than calibrated physical 40 nm behavior).*
3. **Formal Random Search Campaign (100 Evaluations, Seed 2026):**
   - **Evaluations:** 100 physical LTspice simulations executed independently under seed `2026`.
   - **Feasibility:** 100 / 100 valid oscillating simulations (100.0% feasibility; 99 unique sizing pairs, 1 duplicate).
   - **Best Observed Formal Candidate (Scenario A 0.5/0.5):** Iteration 62 ($W_n = 0.19\mu\text{m}, W_p = 2.66\mu\text{m}$, Ratio = 14.00) yielding $\mathcal{F}_{0.5/0.5} = 0.010923$ ($35.37\text{ GHz}, 117.65\mu\text{W}, 2.83\text{ ps}, 0.3326\text{ fJ}$).
   - **Scenario B Re-scoring (0.7/0.3 COMPLETE):** Obtained by re-scoring the exact same 100 physical simulations without running additional simulations. Yields best observed candidate Iteration 63 ($W_n = 1.08\mu\text{m}, W_p = 2.42\mu\text{m}$, Ratio = 2.24) with score $\mathcal{F}_{0.7/0.3} = 0.909112$ ($\Delta \mathcal{F} = +0.509112$, $93.38\text{ GHz}, 318.90\mu\text{W}, 1.07\text{ ps}, 0.3415\text{ fJ}$).

### Phase 6: Bayesian Optimization Engine (PLANNED / NEXT PHASE)
**Status:** **NOT STARTED (PLANNED)**

Bayesian Optimization will be executed in the upcoming phase across two independent experimental campaigns:
- **BO Experiment A (Balanced Objective 0.5/0.5):** Fixed budget of 100 physical LTspice evaluations over frozen bounds $[0.12, 1.20]\mu\text{m} \times [0.24, 2.80]\mu\text{m}$.
- **BO Experiment B (Frequency-Priority Objective 0.7/0.3):** Fixed budget of 100 physical LTspice evaluations over frozen bounds $[0.12, 1.20]\mu\text{m} \times [0.24, 2.80]\mu\text{m}$.
- **Methodology Principles:**
  - BO will fit a Gaussian Process (GP) surrogate $(W_n, W_p) \to \mathcal{F}$ and utilize an acquisition function (e.g., Expected Improvement) to balance exploration and exploitation across the frozen search space.
  - BO will execute with identical bounds, baseline normalization, grid snapping ($10\text{ nm}$), circuit topology, and simulation harness as Random Search.

### Phase 7: Experiment Logging, Persistence & Visualization (COMPLETE)
- **Deliverables:** `experiments/run_formal_random_search_100.py`, `experiments/analyze_formal_100.py`, `experiments/random_search/formal_100/`.
- **Completion Criteria:** CSV ledgers (`results.csv`), JSON configs (`config.json`), summaries (`summary.md`), convergence curves, and trade-off scatter plots generated cleanly.

### Phase 8: Systematic Method Comparison (PLANNED / NEXT PHASE)
- **Deliverables:** `experiments/compare_methods.py`.
- **Fair Comparison Principles:**
  1. Identical frozen search bounds $[0.12, 1.20]\mu\text{m} \times [0.24, 2.80]\mu\text{m}$.
  2. Identical objective function formulations (Scenario A 0.5/0.5 and Scenario B 0.7/0.3).
  3. Identical $10\text{ nm}$ DRC grid snapping.
  4. Identical execution harness, timeout settings, and baseline reference values.
  5. Identical evaluation budget of 100 physical simulations per campaign.

### Phase 9: Extended Experiments (PVT Operating Variations - Optional)
- **Deliverables:** Config-driven sweep over supply voltage $V_{DD}$ ($\pm 10\%$) and temperature ($-40^\circ\text{C}$ to $125^\circ\text{C}$).

---

## 17. Verification and Testing Strategy

### 17.1 Unit Tests (`pytest`)
- All 20 unit and integration tests passing cleanly (`pytest tests/`).

---

## 18. Definition of Done (DoD)

The project implementation will be declared complete when:
1. [x] Baseline 5-stage ring oscillator netlist is confirmed functional in LTspice.
2. [x] $W_n$ and $W_p$ are dynamically parameterizable via Python without manual netlist edits.
3. [x] Python automates batch LTspice execution with robust timeout and process watchdog handling.
4. [x] Oscillation frequency, power consumption, and propagation delay are parsed reliably.
5. [x] Objective evaluation handles both valid outputs and failed/non-oscillating circuits.
6. [x] Random Search campaign (100 physical evaluations, seed 2026) executed and characterized.
7. [x] FINAL $W_n/W_p$ bounds frozen and TBD-03 resolved.
8. [ ] Bayesian Optimization executes over the identical final search space with GP surrogate updating (PLANNED).
9. [x] All evaluations are tracked in structured CSV and JSON log artifacts.
10. [x] Results are reproducible given the same random seed and configuration file.
11. [ ] A comparison script generates Pareto frontier and convergence curves comparing BO vs. RS (PLANNED).
12. [x] Automated test suite (`pytest`) covers configuration, parameterization, and parsing modules.

---

## 19. Open Decisions and TBD Inventory

The following table tracks the formal resolution status of architectural choices and TBD inventory items:

| ID | Item Description | Status / Resolution Details | Impact Area |
| :--- | :--- | :--- | :--- |
| **TBD-01** | **Physical Transistor Technology Node & Models** | **RESOLVED** ($40\text{ nm}$ technology node assumption, $L_n = L_p = 40\text{ nm} = 0.04\mu\text{m}$. Generic Level-1 MOS model active) | Circuit files, length $L$ |
| **TBD-02** | **Nominal Supply Voltage ($V_{DD}$)** | **RESOLVED** ($V_{DD} = 1.1\text{ V}$ fixed nominal operating voltage) | SPICE netlist & power |
| **TBD-03** | **Search Space Bounds ($W_{n,min..max}$, $W_{p,min..max}$)** | **RESOLVED** ($W_n \in [0.12\mu\text{m}, 1.20\mu\text{m}]$, $W_p \in [0.24\mu\text{m}, 2.80\mu\text{m}]$, $10\text{ nm}$ grid frozen based on 90 exploratory evaluations) | Optimizer configuration |
| **TBD-04** | **Specific Bayesian Optimization Library** | **UNRESOLVED / NEXT PHASE** (`scikit-optimize`, `Optuna`, or `BoTorch`/`GPyOpt`; will be selected in upcoming BO phase) | `src/optimization/bayesian.py` |
| **TBD-06** | **LTspice Installation Path on Target OS** | **RESOLVED** (Configured centrally in repository `configs/optimization_config.yaml`, e.g. `C:\Users\Ahana Banerjee\AppData\Local\Programs\ADI\LTspice\LTspice.exe` on Windows) | Subprocess runner |


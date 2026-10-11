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
- **[REQ-OPT-03]** Bayesian Optimization shall initialize with $N_{init} = 10$ space-filling Latin Hypercube Sampling (LHS) candidates prior to adaptive surrogate modeling, followed by 40 adaptive Expected Improvement (EI) evaluations (total budget: 50 physical evaluations per objective scenario).

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

### 12.1 Bayesian Optimization (Primary Optimizer)

#### 12.1.1 Purpose & Comparative Research Questions
Bayesian Optimization (BO) is formulated as the primary sample-efficient surrogate-guided search strategy. Its objective is to determine whether an adaptive surrogate model can discover high-performance transistor sizing configurations using fewer computationally expensive LTspice simulations than unguided Random Search.

The BO experimental framework is specifically designed to answer five fundamental research questions:
1. **Solution Quality:** Can BO discover a superior candidate (higher scalar objective score $\mathcal{F}$) compared to the Random Search benchmark?
2. **Sample Efficiency:** How rapidly does BO reach high-utility regions of the design space compared to Random Search?
3. **Evaluation Budget Required:** How many physical LTspice evaluations does BO require to match or exceed the performance of 50 and 100 Random Search evaluations?
4. **Objective Sensitivity:** How does the performance and sizing trajectory of BO change when transitioning from a balanced trade-off ($0.5/0.5$) to a frequency-priority ($0.7/0.3$) preference?
5. **Design Space Exploitation:** Does BO exploit the underlying physical structure of the $W_n/W_p$ landscape (e.g., steep power gradients vs. saturation regions) more effectively than uniform sampling?

> [!IMPORTANT]
> **Optimality Terminology Constraint:** BO does NOT mathematically guarantee global optimality in black-box non-convex spaces. All findings, metrics, and comparisons must strictly use empirical terms such as **"best observed candidate"**, **"best observed objective score"**, and **"empirical sample efficiency"**, and must **never claim global optimality**.

---

#### 12.1.2 Dual Independent Objective Scenarios
BO shall be executed independently across the two authoritative objective scenarios established in Section 11.2:

1. **Scenario A — Balanced Objective ($w_f = 0.5, w_p = 0.5$):**
   $$\mathcal{F}_A(W_n, W_p) = 0.5 \cdot \left(\frac{f_{osc}}{f_0}\right) - 0.5 \cdot \left(\frac{P_{avg}}{P_0}\right)$$
2. **Scenario B — Frequency-Priority Objective ($w_f = 0.7, w_p = 0.3$):**
   $$\mathcal{F}_B(W_n, W_p) = 0.7 \cdot \left(\frac{f_{osc}}{f_0}\right) - 0.3 \cdot \left(\frac{P_{avg}}{P_0}\right)$$

**Independence Rule:** These two scenarios are completely separate optimization campaigns. The optimizer must NOT transfer surrogate models, observations, or optimal solutions between Scenario A and Scenario B.

---

#### 12.1.3 Search Space & Discrete 10 nm DRC Grid
- **Design Space Bounds:** Identical to the frozen formal Random Search bounds (**TBD-03 RESOLVED**):
  $$W_n \in [0.12\mu\text{m}, 1.20\mu\text{m}], \quad W_p \in [0.24\mu\text{m}, 2.80\mu\text{m}]$$
- **Discrete Manufacturing Grid:** $10\text{ nm} = 0.01\mu\text{m}$ grid step. The valid candidate coordinate sets are:
  $$W_n \in \{0.12, 0.13, \dots, 1.20\}\mu\text{m} \quad (109\text{ grid values})$$
  $$W_p \in \{0.24, 0.25, \dots, 2.80\}\mu\text{m} \quad (257\text{ grid values})$$
  Total discrete candidates in search space: $109 \times 257 = 28,013\text{ points}$.
- **Unconstrained Aspect Ratio:** $W_n$ and $W_p$ are treated as independent optimization dimensions. No artificial constraints ($W_p = 2W_n$ or bounded $W_p/W_n$ ratio) are imposed. The rectangular search space is intentional to allow unbiased discovery.
- **Candidate Discretization & Duplicate Mitigation:**
  - Continuous candidate proposals generated by maximizing the acquisition function are snapped to the nearest $10\text{ nm}$ grid coordinate:
    $$W_n = \text{round}(W_n / 10\text{nm}) \times 10\text{nm}, \quad W_p = \text{round}(W_p / 10\text{nm}) \times 10\text{nm}$$
  - Candidate bounds are clamped: $W_n \in [0.12\mu\text{m}, 1.20\mu\text{m}], W_p \in [0.24\mu\text{m}, 2.80\mu\text{m}]$.
  - **Duplicate Mitigation Protocol:** Because circuit simulations are deterministic (barring negligible numerical solver noise), re-evaluating an identical $[W_n, W_p]$ point yields no information and wastes simulation budget. If a snapped candidate has already been evaluated, the acquisition ranking across the discrete grid (or acquisition optimization with exclusion) shall select the next highest acquisition candidate not yet evaluated.

---

#### 12.1.4 Strict Isolation from Benchmark Data (No Prior Pre-training)
The 100 formal Random Search evaluations constitute the external baseline benchmark.
- **Prohibition of Data Leaks:** BO shall **NOT** be initialized, warm-started, or pre-trained using the 100 Random Search observations.
- Seeding the surrogate with Random Search points would confound optimization efficiency with prior data availability.
- BO must start from scratch with its own allocated evaluation budget. The Random Search dataset is reserved strictly for post-hoc comparative analysis.

---

#### 12.1.5 Evaluation Budget & Two-Phase Partitioning
Each BO objective scenario is allocated a fixed physical simulation budget of **50 LTspice evaluations**:

$$\text{Total BO Budget per Scenario} = 50\text{ physical LTspice evaluations}$$

The budget is partitioned into two distinct methodological phases:
1. **Phase 1 — Initial Space-Filling Design ($N_{init} = 10$ evaluations):**
   - 10 quasi-random space-filling candidates generated via Latin Hypercube Sampling (LHS).
   - *Methodological Classification:* These 10 points are **NOT Bayesian-guided observations**. They serve purely to establish the initial Gaussian Process prior covariance across the 2-D space.
2. **Phase 2 — Adaptive Bayesian Optimization ($N_{adaptive} = 40$ evaluations):**
   - 40 sequential iterations guided by surrogate updating and Expected Improvement acquisition maximization.
   - *Methodological Classification:* These 40 points represent active Bayesian-guided optimization.

**Total Planned BO Physical Simulations:**
- Scenario A (0.5/0.5): 50 physical simulations (10 LHS + 40 adaptive)
- Scenario B (0.7/0.3): 50 physical simulations (10 LHS + 40 adaptive)
- Combined Planned BO Total: **100 physical simulations** (executing independently).

---

#### 12.1.6 Initial Design: Latin Hypercube Sampling (LHS)
- **Method:** Latin Hypercube Sampling (LHS) over the normalized domain $[0, 1]^2$.
- **Properties:**
  - Deterministic and fully reproducible via fixed seed.
  - Uniform marginal projections ensuring broad space-filling coverage without clustering near the baseline ($0.5\mu\text{m}/1.0\mu\text{m}$).
  - Fully independent of Random Search sampling locations.
- **Seed Allocation:**
  - Scenario A Seed: Distinct deterministic integer recorded in experiment configuration.
  - Scenario B Seed: Distinct deterministic integer recorded in experiment configuration.

---

#### 12.1.7 Surrogate Model: Gaussian Process Regression (GPR)
- **Model Type:** Gaussian Process Regression (GPR).
- **Input Representation:** Candidate vector $\mathbf{x} = [W_n, W_p]^T$ normalized to the unit hypercube $[0, 1]^2$:
  $$x_1 = \frac{W_n - W_{n,min}}{W_{n,max} - W_{n,min}}, \quad x_2 = \frac{W_p - W_{p,min}}{W_{p,max} - W_{p,min}}$$
- **Output Representation:** Scalar objective $\mathcal{F}(\mathbf{x})$, standardized to zero mean and unit variance based on current observations.
- **Covariance Kernel:** Matérn 5/2 kernel with Automatic Relevance Determination (ARD) separate lengthscales:
  $$k(\mathbf{x}, \mathbf{x}') = \sigma_f^2 \left(1 + \sqrt{5}r + \frac{5}{3}r^2\right) \exp\left(-\sqrt{5}r\right), \quad r = \sqrt{\frac{(x_1 - x'_1)^2}{\ell_1^2} + \frac{(x_2 - x'_2)^2}{\ell_2^2}}$$
  - *Rationale:* Analog circuit performance exhibits smooth, continuous dependencies on transistor dimensions, but second-order physical transitions (e.g., velocity saturation, subthreshold conduction) violate the infinite differentiability assumption of the Squared Exponential (RBF) kernel. The Matérn 5/2 kernel enforces twice-differentiability ($\mathcal{C}^2$), providing realistic inductive bias without over-smoothing.
- **Observation Noise / Nugget:** A small constant nugget $\sigma_n^2 \approx 10^{-6}$ (or $10^{-5}$) added along the diagonal of the covariance matrix:
  $$\mathbf{K}_{noisy} = \mathbf{K} + \sigma_n^2 \mathbf{I}$$
  - *Rationale:* LTspice transient simulations are deterministic numerical evaluations with tiny floating-point solver tolerances. A small non-zero nugget guarantees numerical positive definiteness and prevents singular matrix inversion during Cholesky decomposition.
- **Hyperparameter Fitting Policy:** GP hyperparameters (signal variance $\sigma_f^2$, lengthscales $\ell_1, \ell_2$) are re-fitted at every adaptive iteration by maximizing the Log Marginal Likelihood (LML) using L-BFGS-B with multiple random restarts.

---

#### 12.1.8 Acquisition Function: Expected Improvement (EI)
- **Acquisition Strategy:** Expected Improvement (EI) evaluated in the standardized objective domain over the current best observed feasible score $\tilde{\mathcal{F}}^+$:
  $$\alpha_{EI}(\mathbf{x}) = \mathbb{E}\left[\max(0, \tilde{\mathcal{F}}(\mathbf{x}) - \tilde{\mathcal{F}}^+ - \xi)\right]$$
- **Analytical Closed Form (Standardized Domain):**
  $$\alpha_{EI}(\mathbf{x}) = (\mu_{std}(\mathbf{x}) - \tilde{\mathcal{F}}^+ - \xi) \Phi(Z) + \sigma_{std}(\mathbf{x}) \phi(Z)$$
  where:
  $$Z = \begin{cases} \frac{\mu_{std}(\mathbf{x}) - \tilde{\mathcal{F}}^+ - \xi}{\sigma_{std}(\mathbf{x})}, & \text{if } \sigma_{std}(\mathbf{x}) > 0 \\ 0, & \text{if } \sigma_{std}(\mathbf{x}) = 0 \end{cases}$$
  - $\mu_{std}(\mathbf{x})$: Posterior mean prediction in standardized output units.
  - $\sigma_{std}(\mathbf{x})$: Posterior predictive standard deviation in standardized output units.
  - $\tilde{\mathcal{F}}^+ = \frac{\mathcal{F}^+ - \mu_y}{\sigma_y}$: Best observed feasible score mapped to standardized output units.
  - $\xi = 0.01$: Exploration jitter parameter applied in the standardized domain ($0.01\sigma_y$), ensuring scale-invariant trade-off balance across both Scenario A and Scenario B.
- **Fallback Policy on Non-Positive EI ($\alpha_{EI} \le 0$):**
  If all unvisited candidates on the discrete grid produce non-positive Expected Improvement ($\alpha_{EI} \le 0$), the optimizer activates the documented fallback: selecting the unvisited candidate with the maximum posterior predictive mean $\mu(\mathbf{x})$, guaranteeing that only non-evaluated points are proposed.
- **Conditioned Penalty Handling for GP Surrogate:**
  Infeasible/failed candidates ($\mathcal{F}_{penalty} = -1.0 \times 10^9$) are recorded verbatim in `self.history`, but for GP training target assembly, their target score is conditioned to a soft penalty floor ($\min(y_{feasible}) - \max(2\sigma_{feasible}, 0.2)$) to prevent numerical distortion of target standardization and hyperparameter fitting.

---

#### 12.1.9 Formal Iterative Bayesian Optimization Execution Loop
At every step of the optimization campaign, the system executes the following strict 11-step protocol:

```text
Step 1:  Generate N_init = 10 space-filling candidate sizing pairs via Latin Hypercube Sampling (LHS).
Step 2:  Snap candidates to the discrete 10 nm DRC grid and clamp within [0.12, 1.20] x [0.24, 2.80] µm.
Step 3:  Evaluate each initial candidate in LTspice via headless execution harness; extract f_osc, P_avg, t_pd, PDP.
Step 4:  Calculate target scalar objective score F for all 10 candidates; initialize dataset D_10 = {(x_i, F_i)}_{i=1}^{10}.
Step 5:  FOR adaptive iteration k = 11 TO 50:
           a. Normalize inputs x in [0, 1]^2; standardize targets F.
           b. Fit/re-fit Gaussian Process hyperparameters via Log Marginal Likelihood maximization.
           c. Optimize acquisition function alpha_EI(x) over [0, 1]^2 using multi-start L-BFGS-B or grid search.
           d. Snap optimal proposal x* to the discrete 10 nm grid.
           e. Verify candidate is within bounds and has NOT been previously evaluated (Duplicate Mitigation).
              If duplicate: select next highest non-evaluated acquisition candidate on the 10 nm grid.
           f. Update SPICE netlist template with candidate .param Wn=... Wp=...
           g. Launch batch LTspice simulation with 30-second watchdog timeout.
           h. Parse .log file, validate oscillation criteria, extract electrical metrics.
           i. Compute scalar objective F_k (or assign F_penalty = -1e9 if non-oscillating).
           j. Append new observation (x_k, F_k) to training dataset D_k.
           k. Update best-so-far record and append iteration telemetry to experiment ledger CSV.
Step 6:  Record final summary JSON, convergence trajectories, and analytical report.
```

---

#### 12.1.10 Fair Comparison Framework Against Random Search
To ensure rigorous, statistically sound benchmarking between Bayesian Optimization and Random Search, the comparison shall be structured as follows:

1. **Equal-Budget Comparison (Primary Efficiency Benchmark):**
   $$\text{Random Search (First 50 Physical Evaluations)} \quad \text{vs.} \quad \text{Bayesian Optimization (50 Total Physical Evaluations)}$$
   - Direct sample-for-sample comparison at $N = 50$.
   - Answers: *Given the exact same simulation budget ($N=50$), does adaptive modeling outperform unguided sampling?*
2. **Full Random Search Reference Comparison (Asymptotic Quality Benchmark):**
   $$\text{Random Search (100 Physical Evaluations)} \quad \text{vs.} \quad \text{Bayesian Optimization (50 Total Physical Evaluations)}$$
   - Evaluates whether BO achieves comparable or superior sizing with **$50\%$ fewer physical evaluations**.
   - Answers: *Can BO match or beat a $2\times$ larger unguided random search budget?*
3. **Convergence Curve Tracking:**
   - Plot best-so-far objective score $\mathcal{F}^*(n) = \max_{i \le n} \mathcal{F}_i$ across evaluation indices $n \in [1, 50]$ for both methods.
   - Quantify milestone iterations (iterations required to reach 25%, 50%, 75%, 90%, and 100% of final achieved score).
4. **Standard Candidate Comparison Table:**
   For each scenario, construct a comparative summary:
   | Metric | Baseline | RS (50 Evals) | RS (100 Evals) | BO (50 Evals) | BO vs RS (50) $\Delta$ | BO vs RS (100) $\Delta$ |
   | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
   | $W_n$ ($\mu\text{m}$) | $0.50$ | ... | ... | ... | ... | ... |
   | $W_p$ ($\mu\text{m}$) | $1.00$ | ... | ... | ... | ... | ... |
   | $W_p / W_n$ Ratio | $2.00$ | ... | ... | ... | ... | ... |
   | $f_{osc}$ (GHz) | $41.07$ | ... | ... | ... | ... | ... |
   | $P_{avg}$ ($\mu\text{W}$) | $140.17$ | ... | ... | ... | ... | ... |
   | $t_{pd}$ (ps) | $2.43$ | ... | ... | ... | ... | ... |
   | $\text{PDP}$ (fJ) | $0.3413$ | ... | ... | ... | ... | ... |
   | Objective Score $\mathcal{F}$ | $0.0000$ | ... | ... | ... | ... | ... |
   | Discovery Iteration | N/A | ... | ... | ... | ... | ... |

---

#### 12.1.11 Experimental Comparison Architecture Diagram

```text
                     SCENARIO A (Balanced: 0.5f / 0.5P)
  Random Search Benchmark                      Bayesian Optimization
  [100 Physical Evaluations]                   [50 Physical Evaluations]
              │                                            │
              ├─────── Equal Budget (First 50 Evals) ──────┤  (RS-50 vs BO-50)
              │                                            │
              └─────── Full Budget Benchmark ──────────────┘  (RS-100 vs BO-50)

                     SCENARIO B (Frequency Priority: 0.7f / 0.3P)
  Random Search Benchmark                      Bayesian Optimization
  [100 Offline Re-scored]                      [50 Independent Physical Evals]
  (0 New Physical Simulations)                 (50 New Physical Simulations)
              │                                            │
              ├─────── Equal Budget (First 50 Evals) ──────┤  (RS-50 vs BO-50)
              │                                            │
              └─────── Full Budget Benchmark ──────────────┘  (RS-100 vs BO-50)
```

---

#### 12.1.12 Methodological Limitations
The documentation and analysis of Bayesian Optimization must explicitly acknowledge the following scientific limitations:
1. **Surrogate Calibration Dependency:** The predictive accuracy of the Gaussian Process depends on the coverage of initial samples. Poor initial coverage may bias early adaptive proposals.
2. **Deliberately Bounded Budget:** A budget of 50 evaluations is intentionally sample-constrained. While practical for analog simulation, it does not explore asymptotic convergence.
3. **Stochastic Nature of Realizations:** Although individual runs use deterministic random seeds, optimization trajectories are stochastic realizations. A single seed does not prove universal superiority across all possible random sequences.
4. **No Global Optimality Guarantee:** Black-box surrogate optimization provides no mathematical proof of global optimality in non-convex multi-modal landscapes.
5. **Transistor Model Abstraction:** The circuit uses a generic Level-1 MOS model at 40 nm dimensions. It serves as a methodology and numerical optimization study, not a silicon-qualified foundry PDK characterization.
6. **Discrete Grid Rounding Artifacts:** Snapping continuous proposals to a $10\text{ nm}$ DRC grid alters the exact acquisition argmax location, which can reduce local gradient exploitation near narrow peaks.
7. **Exploration-Exploitation Balance:** Expected Improvement with fixed $\xi = 0.01$ may tend toward over-exploitation if surrogate predictive variance shrinks too rapidly.
8. **Handling of Duplicates:** When the acquisition function repeatedly favors an already-evaluated grid coordinate, fallback to sub-optimal acquisition peaks is required.
9. **Simulation Overhead:** Unlike mathematical test functions, each evaluation incurs SPICE simulation latency (~0.3–0.5s per transient run).
10. **Objective Weight Sensitivity:** Fixed scalar weights ($0.5/0.5$ and $0.7/0.3$) compress a multi-dimensional Pareto surface into single utility curves; conclusions are specific to these utility formulations.

---

#### 12.1.13 Success & Verification Criteria
The Phase 6 Bayesian Optimization campaign shall be judged successful if and only if all of the following empirical criteria are satisfied:
1. **Simulation Budget:** BO completes exactly 50 physical LTspice evaluations per objective scenario (100 physical simulations total across both scenarios).
2. **Pipeline Invariance:** All evaluations execute through the exact same simulation harness, netlist template, extraction parser, and objective calculator as Random Search.
3. **Model & Circuit Invariance:** Transistor model, supply voltage ($1.1\text{V}$), channel length ($40\text{nm}$), and load capacitances ($0.5\text{fF}$) remain strictly identical to Random Search.
4. **Search Space Invariance:** All evaluations remain within the frozen bounds $[0.12, 1.20]\mu\text{m} \times [0.24, 2.80]\mu\text{m}$ on the $10\text{ nm}$ grid.
5. **Reproducibility:** Experiments execute with recorded deterministic seeds and reproduce identical results when re-run.
6. **Telemetry Logging:** Detailed convergence history, parameter vectors, metrics, acquisition scores, and timestamps are logged per evaluation.
7. **Rigorous Equal-Budget Comparison:** BO is systematically benchmarked against the first 50 Random Search evaluations as well as the full 100 evaluations.
8. **Empirical Reporting:** Best observed candidates are reported with full physical metrics ($W_n, W_p, f_{osc}, P_{avg}, t_{pd}, PDP, \mathcal{F}$).
9. **Scientific Objectivity:** Success is defined by rigorous methodology and execution parity, **NOT by whether BO outperforms Random Search**. Parity or negative comparative findings are valid and publishable research results.

---

#### 12.1.14 Expected Artifact Structure
Upon execution, Phase 6 will generate structured artifacts under dedicated scenario directories:
```text
experiments/
└── bayesian_optimization/
    ├── scenario_05_05/
    │   ├── results.csv          # 50-row detailed evaluation ledger
    │   ├── metadata.json        # Configuration, seeds, timing, hyperparameters
    │   ├── summary.md           # Campaign summary and best candidate findings
    │   └── plots/
    │       ├── convergence.png  # Best-so-far curve vs RS-50 and RS-100
    │       └── design_space.png # Sizing scatter map showing LHS vs Adaptive points
    │
    └── scenario_07_03/
        ├── results.csv          # 50-row detailed evaluation ledger
        ├── metadata.json        # Configuration, seeds, timing, hyperparameters
        ├── summary.md           # Campaign summary and best candidate findings
        └── plots/
            ├── convergence.png  # Best-so-far curve vs RS-50 and RS-100
            └── design_space.png # Sizing scatter map showing LHS vs Adaptive points
```

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

### Phase 6: Bayesian Optimization Engine (ENGINE IMPLEMENTED & VERIFIED)
**Status:** **ENGINE IMPLEMENTED / CAMPAIGN EXECUTION PENDING**

The Bayesian Optimization engine module has been formally implemented and unit tested (`src/optimization/bayesian.py`, 10/10 tests passing in `tests/test_bayesian.py`). The optimizer coordinates two strictly independent experimental campaigns to be executed sequentially upon user approval:
- **BO Experiment A (Balanced Objective 0.5/0.5):** Fixed budget of 50 physical LTspice evaluations (10 initial LHS space-filling + 40 adaptive GP/EI evaluations) over frozen bounds $[0.12, 1.20]\mu\text{m} \times [0.24, 2.80]\mu\text{m}$ on a $10\text{ nm}$ grid.
- **BO Experiment B (Frequency-Priority Objective 0.7/0.3):** Fixed budget of 50 physical LTspice evaluations (10 initial LHS space-filling + 40 adaptive GP/EI evaluations) over frozen bounds $[0.12, 1.20]\mu\text{m} \times [0.24, 2.80]\mu\text{m}$ on a $10\text{ nm}$ grid.
- **Key Implementation Highlights:**
  - `GaussianProcessMatern52`: Gaussian Process surrogate with Matérn 5/2 covariance kernel, ARD lengthscales, $[0, 1]^2$ input normalization, target standardization, and $\sigma_n^2 = 10^{-6}$ numerical nugget.
  - `BayesianOptimizer`: Expected Improvement ($\alpha_{EI}$) acquisition function with exploration parameter $\xi = 0.01$.
  - Discrete $10\text{ nm}$ DRC grid snapping over all 28,013 valid candidates with strict duplicate rejection.
  - Deterministic independent random seeds for full reproducibility.
  - Strict isolation: Random Search benchmark dataset is NOT used for BO initialization.

### Phase 7: Experiment Logging, Persistence & Visualization (COMPLETE)
- **Deliverables:** `experiments/run_formal_random_search_100.py`, `experiments/analyze_formal_100.py`, `experiments/random_search/formal_100/`.
- **Completion Criteria:** CSV ledgers (`results.csv`), JSON configs (`config.json`), summaries (`summary.md`), convergence curves, and trade-off scatter plots generated cleanly.

### Phase 8: Systematic Method Comparison (PLANNED / NEXT PHASE)
- **Deliverables:** `experiments/compare_methods.py`.
- **Fair Comparison Principles:**
  1. Identical frozen search bounds $[0.12, 1.20]\mu\text{m} \times [0.24, 2.80]\mu\text{m}$.
  2. Identical objective function formulations (Scenario A 0.5/0.5 and Scenario B 0.7/0.3).
  3. Identical $10\text{ nm}$ DRC grid snapping.
  4. Identical execution harness, timeout settings, and baseline reference values ($f_0 = 41.069757\text{ GHz}, P_0 = 140.169554\mu\text{W}$).
  5. **Equal-Budget Primary Comparison:** First 50 physical evaluations of Random Search vs. 50 total evaluations of Bayesian Optimization.
  6. **Full-Budget Reference Comparison:** Full 100 physical evaluations of Random Search vs. 50 total evaluations of Bayesian Optimization.

### Phase 9: Extended Experiments (PVT Operating Variations - Optional)
- **Deliverables:** Config-driven sweep over supply voltage $V_{DD}$ ($\pm 10\%$) and temperature ($-40^\circ\text{C}$ to $125^\circ\text{C}$).

### Physical Simulation Accounting Ledger

| Campaign / Scenario | Methodology | Status | Physical LTspice Simulations | Scalar Objective Evaluations |
| :--- | :--- | :--- | :---: | :---: |
| **Exploratory Random Search** | 3 batches (10 pilot + 30 boundary + 50 focused) | **COMPLETE** | 90 | 90 |
| **Formal RS Scenario A (0.5/0.5)** | Uniform random sampling (Seed 2026) | **COMPLETE** | 100 | 100 |
| **Formal RS Scenario B (0.7/0.3)** | Offline re-scoring of formal 100 RS dataset | **COMPLETE** | **0** (Offline re-scored) | 100 |
| **BO Scenario A (0.5/0.5)** | 10 LHS initial + 40 adaptive GP/EI | **METHODOLOGY DEFINED / NOT STARTED** | 50 (Planned) | 50 (Planned) |
| **BO Scenario B (0.7/0.3)** | 10 LHS initial + 40 adaptive GP/EI | **METHODOLOGY DEFINED / NOT STARTED** | 50 (Planned) | 50 (Planned) |
| **Current Completed Total** | — | **CURRENT COMPLETED** | **190** (90 exploratory + 100 formal) | **290** |
| **Projected Final Total** | — | **PROJECTED TOTAL** | **290** (90 exploratory + 100 formal RS + 100 BO) | **390** |

*(Note: Within the formal optimization campaigns excluding exploratory characterization, physical LTspice simulations currently total exactly 100, and will total 200 upon completion of both 50-evaluation BO campaigns).*

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
8. [ ] Bayesian Optimization executes over the identical final search space with GP surrogate updating (ENGINE IMPLEMENTED & VERIFIED / CAMPAIGN EXECUTION PENDING).
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
| **TBD-04** | **Bayesian Optimization Surrogate & Acquisition Formulation** | **RESOLVED IN SPECIFICATION** (Gaussian Process Regression with Matérn 5/2 kernel, Expected Improvement (EI) acquisition, $N_{init}=10$ LHS initial samples + 40 adaptive evaluations = 50 total evaluations per objective; implementation in Phase 6 using standard GP stack) | `src/optimization/bayesian.py` |
| **TBD-06** | **LTspice Installation Path on Target OS** | **RESOLVED** (Configured centrally in repository `configs/optimization_config.yaml`, e.g. `C:\Users\Ahana Banerjee\AppData\Local\Programs\ADI\LTspice\LTspice.exe` on Windows) | Subprocess runner |


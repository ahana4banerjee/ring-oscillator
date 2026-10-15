# Experimental Analysis: Bayesian Optimization and Random Search for CMOS Ring Oscillator Sizing

**Document Type:** Formal Research Analysis & Comparative Study  
**Project:** Automated Sizing Optimization of a 5-Stage CMOS Ring Oscillator  
**Target Simulator:** Headless LTspice (Level-1 MOS Model, 40 nm Nominal Channel Length)  
**Authoritative Specification:** [`SRS.md`](SRS.md)  
**Execution Context & History:** [`CONTEXT.md`](CONTEXT.md)  
**Date:** October 2026  

---

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Research Objectives and Questions](#2-research-objectives-and-questions)
3. [Experimental Setup and Methodology](#3-experimental-setup-and-methodology)
4. [Experimental Datasets and Data Quality Validation](#4-experimental-datasets-and-data-quality-validation)
5. [Scenario A Results — Balanced Objective (0.5 / 0.5)](#5-scenario-a-results--balanced-objective-05--05)
6. [Scenario B Results — Frequency-Priority Objective (0.7 / 0.3)](#6-scenario-b-results--frequency-priority-objective-07--03)
7. [Random Search Versus Bayesian Optimization](#7-random-search-versus-bayesian-optimization)
8. [Cross-Scenario Analysis: Impact of Objective Weights on Sizing](#8-cross-scenario-analysis-impact-of-objective-weights-on-sizing)
9. [Consolidated Results Matrix](#9-consolidated-results-matrix)
10. [Main Research Findings](#10-main-research-findings)
11. [Engineering Interpretation and Circuit Physics](#11-engineering-interpretation-and-circuit-physics)
12. [Limitations and Threats to Validity](#12-limitations-and-threats-to-validity)
13. [Defensible Research Conclusions](#13-defensible-research-conclusions)
14. [Prioritized Future Work](#14-prioritized-future-work)
15. [Reproducibility and Artifact Index](#15-reproducibility-and-artifact-index)

---

## 1. Executive Summary

This study evaluates the sample efficiency, optimization efficacy, and electrical trade-offs of **Bayesian Optimization (BO)** against **Random Search (RS)** in the automated transistor sizing of a 5-stage CMOS ring oscillator using physical transient simulations in **LTspice**. The optimization space spans NMOS width $W_n \in [0.12, 1.20]\ \mu\text{m}$ and PMOS width $W_p \in [0.24, 2.80]\ \mu\text{m}$ mapped to a discrete 10 nm Design Rule Check (DRC) manufacturing grid (28,013 valid candidate pairs).

Two distinct objective formulations were investigated under identical physical simulation harnesses:
- **Scenario A (Balanced Objective: $w_f = 0.5, w_p = 0.5$):** Places equal weight on normalized frequency maximization and normalized power minimization.
- **Scenario B (Frequency-Priority Objective: $w_f = 0.7, w_p = 0.3$):** Prioritizes switching frequency while imposing a moderate power penalty.

```
Key Experimental Findings at a Glance:
┌───────────────────────────┬───────────────────────────┬───────────────────────────┐
│ Metric / Observation      │ Scenario A (Balanced)     │ Scenario B (High-Speed)   │
├───────────────────────────┼───────────────────────────┼───────────────────────────┤
│ Best Candidate Sizing     │ Wn = 0.12 µm, Wp = 2.80 µm│ Wn = 1.20 µm, Wp = 2.80 µm│
│ Sizing Ratio (Wp / Wn)    │ 23.3333 (Asymmetric)      │ 2.3333 (Balanced)         │
│ Oscillation Frequency (f) │ 27.571 GHz (-32.87%)      │ 105.656 GHz (+157.26%)    │
│ Average Power (P)         │ 88.319 µW  (-36.99%)      │ 360.891 µW (+157.47%)     │
│ Stage Delay (t_pd)        │ 3.627 ps   (+48.96%)      │ 0.9465 ps  (-61.13%)      │
│ Power-Delay Product (PDP) │ 0.3203 fJ  (-6.14%)       │ 0.3416 fJ  (+0.08%)       │
│ Discovery Evaluation      │ Iteration 12 (Phase 2)    │ Iteration 11 (Phase 2)    │
│ Equal-Budget vs. RS-50    │ +0.020616 vs. +0.004793   │ N/A (RS re-score: +0.781) │
│ Full-Budget vs. RS-100    │ +0.020616 vs. +0.010923   │ N/A (RS re-score: +0.909) │
└───────────────────────────┴───────────────────────────┴───────────────────────────┘
```

### Primary Research Findings
1. **High Sample Efficiency:** Bayesian Optimization discovered its campaign-best feasible candidate in the first two adaptive iterations (Evaluation 12 in Scenario A; Evaluation 11 in Scenario B), consistently locating high-utility boundary basins within $24\%$ of the allotted 50-evaluation budget.
2. **Superiority Over Random Search in Tested Runs:** Under Scenario A, BO-50 achieved an objective score of $+0.020616$, outperforming equal-budget Random Search (RS-50: $+0.004793$, discovered at Eval 28) by **$>4.3\times$** in net improvement, and surpassing the full 100-evaluation Random Search campaign (RS-100: $+0.010923$, discovered at Eval 62) while using only half the simulation budget.
3. **Objective-Driven Pareto Frontier Shift:** Shifting objective weights fundamentally redirected optimizer convergence. Rewarding power reduction (Scenario A) drove $W_n$ to its absolute minimum bound ($0.12\ \mu\text{m}$) to minimize dynamic capacitive switching losses, whereas prioritizing speed (Scenario B) drove $W_n$ to its maximum bound ($1.20\ \mu\text{m}$) to maximize saturation drive current, achieving sub-picosecond stage delay ($0.9465\text{ ps}$).
4. **Physical Boundary Realities:** Both campaigns identified the identical non-oscillating boundary failure at $W_n = 0.12\ \mu\text{m}, W_p = 0.24\ \mu\text{m}$ (Iteration 17 in both runs). Furthermore, both scenario optima landed on the search-space boundaries, demonstrating that within the specified bounds, optimal trade-offs lie at geometric extremes.

---

## 2. Research Objectives and Questions

This research investigates the following core questions:

1. **Sample Efficiency Question:** Can Gaussian Process surrogate modeling with Expected Improvement acquisition locate optimal or near-optimal ring oscillator transistor sizings with substantially fewer physical SPICE simulations than unbiased Random Search?
2. **Benchmark Comparison Question:** How does 50-evaluation Bayesian Optimization compare against Random Search under an equal evaluation budget (50 evaluations) and under an extended full budget (100 evaluations)?
3. **Objective Weight Sensitivity Question:** How do multi-metric objective formulations redirect the surrogate model across the transistor sizing landscape, and what physical circuit trade-offs emerge between switching speed and power consumption?
4. **Feasibility and Modeling Boundary Question:** What fraction of the discrete sizing grid sustains physical oscillation, where do oscillation failure boundaries occur, and how robust is the optimization algorithm against non-convergent or non-oscillating circuit states?

---

## 3. Experimental Setup and Methodology

### 3.1 Circuit Under Test
The target circuit is a 5-stage CMOS ring oscillator parameterized at the transistor level:
- **Topology:** Five inverter stages in an odd closed loop ($N = 5$).
- **Technology Assumptions:** Generic Level-1 MOSFET model parameterized for $40\text{ nm}$ nominal channel length ($L_n = L_p = 40\text{ nm} = 0.04\ \mu\text{m}$).
- **Nominal Supply Voltage ($V_{DD}$):** $1.1\text{ V}$ fixed.
- **Operating Temperature:** $25^\circ\text{C}$ (nominal).
- **Interconnect Stage Capacitance ($C_{load}$):** Lumped $0.5\text{ fF}$ per inverter output node ($C_1 = \dots = C_5 = 0.5\text{ fF}$).
- **Simulation Harness:** Headless batch execution via `LTspice.exe` with command line `-b -Run` flags; transient stop time $t_{stop} = 1.0\text{ ns}$, saving waveforms from $0.2\text{ ns}$ to $1.0\text{ ns}$ to bypass initial startup transients.

Detailed circuit and simulation specifications are governed by [`SRS.md`](SRS.md) and [`configs/bayesian_optimization_config.yaml`](configs/bayesian_optimization_config.yaml).

### 3.2 Transistor Sizing Design Space
Optimization variables are restricted strictly to channel widths:
$$\mathcal{X} = \left\{ (W_n, W_p) \;\middle|\; W_n \in [0.12, 1.20]\ \mu\text{m}, \; W_p \in [0.24, 2.80]\ \mu\text{m}, \; \Delta W = 10\text{ nm} \right\}$$
- **Total Discrete Valid Candidates:** Exactly 28,013 valid grid points (109 discrete values of $W_n \times 257$ discrete values of $W_p$).
- **Manufacturing Constraint:** All proposed candidates must snap strictly to the 10 nm grid resolution ($0.01\ \mu\text{m}$).

### 3.3 Baseline Circuit Reference Normalization
All objective metrics are normalized against the fixed physical baseline circuit configuration:
- **Baseline Sizing:** $W_n = 0.50\ \mu\text{m}$, $W_p = 1.00\ \mu\text{m}$ (nominal ratio $W_p / W_n = 2.0000$).
- **Baseline Frequency ($f_0$):** $41,069,756,649.1\text{ Hz} \approx 41.069757\text{ GHz}$.
- **Baseline Average Power ($P_0$):** $0.000140169553568\text{ W} \approx 140.169554\ \mu\text{W}$.
- **Baseline Propagation Delay ($t_{pd0}$):** $2.434882\text{ ps}$ (per-stage delay, satisfying $t_{pd} = T / (2N) = T / 10$).
- **Baseline Power-Delay Product ($\text{PDP}_0$):** $0.341296\text{ fJ}$ ($P_{avg} \times t_{pd}$).

### 3.4 Mathematical Formulation of Objectives
The scalar objective function $\mathcal{F}(W_n, W_p)$ rewards higher oscillation frequency and penalizes average power dissipation:
$$\mathcal{F} = w_f \cdot \left(\frac{f}{f_0}\right) - w_p \cdot \left(\frac{P}{P_0}\right)$$

1. **Scenario A (Balanced Objective):**
   $$\mathcal{F}_A = 0.5 \cdot \left(\frac{f}{f_0}\right) - 0.5 \cdot \left(\frac{P}{P_0}\right)$$
   $$\mathcal{F}_A(\text{Baseline}) = 0.5(1.0) - 0.5(1.0) = 0.000000$$

2. **Scenario B (Frequency-Priority Objective):**
   $$\mathcal{F}_B = 0.7 \cdot \left(\frac{f}{f_0}\right) - 0.3 \cdot \left(\frac{P}{P_0}\right)$$
   $$\mathcal{F}_B(\text{Baseline}) = 0.7(1.0) - 0.3(1.0) = 0.400000$$

*Methodological Note:* Raw numerical scores from Scenario A and Scenario B are **not directly comparable** because Scenario B intrinsically shifts the baseline score from $0.000$ to $0.400$. Meaningful comparisons must assess the net improvement over baseline ($\Delta \mathcal{F} = \mathcal{F} - \mathcal{F}_{baseline}$) or re-evaluate both candidates under a common objective formula.

3. **Conditioned Penalty for Non-Oscillating Candidates:**
   Circuits failing to oscillate (or failing electrical consistency checks) are classified as non-feasible and assigned an invariant penalty score:
   $$\mathcal{F}_{\text{penalty}} = -1.0 \times 10^9$$
   This severe penalty ensures that non-feasible candidates are strictly excluded from the feasible best-so-far set and prevents the Gaussian Process from recommending regions of non-oscillation.

### 3.5 Bayesian Optimization Architecture
Implemented in [`src/optimization/bayesian.py`](src/optimization/bayesian.py):
- **Surrogate Model:** Gaussian Process Regression with Matérn 5/2 kernel and Automatic Relevance Determination (ARD) separate lengthscales:
  $$k(x, x') = \sigma_f^2 \left(1 + \sqrt{5}r + \frac{5}{3}r^2\right) \exp(-\sqrt{5}r), \quad r = \sqrt{\sum_{i=1}^2 \frac{(x_i - x_i')^2}{\ell_i^2}}$$
- **Input Space Transformation:** Min-max normalization of $(W_n, W_p)$ to $[0, 1]^2$.
- **Target Transformation:** Standardization of valid objective scores ($\mu = 0, \sigma = 1$).
- **Numerical Regularization (Nugget):** $\sigma_n^2 = 1.0 \times 10^{-6}$ added to covariance diagonal for numerical stability.
- **Acquisition Function:** Expected Improvement ($\alpha_{\text{EI}}$) evaluated over standardized space with exploration parameter $\xi = 0.01$:
  $$\alpha_{\text{EI}}(x) = (\mu(x) - f^* - \xi)\Phi(Z) + \sigma(x)\phi(Z), \quad Z = \frac{\mu(x) - f^* - \xi}{\sigma(x)}$$
- **Budget Partitioning (50 Total Evaluations):**
  - **Phase 1 (Space-Filling LHS):** 10 initial evaluations sampled via Latin Hypercube Sampling.
  - **Phase 2 (Adaptive BO):** 40 evaluations chosen adaptively by maximizing Expected Improvement over the discrete 28,013 candidate grid with strict duplicate exclusion.
- **Deterministic Random Seeds:** Seed 2026 for Scenario A; Seed 3031 for Scenario B.

---

## 4. Experimental Datasets and Data Quality Validation

The physical datasets analyzed in this document are stored in the following authoritative directories:
- **Formal Random Search (100 physical runs):** [`experiments/random_search/formal_100/results.csv`](experiments/random_search/formal_100/results.csv)
- **Bayesian Optimization Scenario A (50 physical runs):** [`experiments/bayesian_optimization/scenario_05_05/results.csv`](experiments/bayesian_optimization/scenario_05_05/results.csv)
- **Bayesian Optimization Scenario B (50 physical runs):** [`experiments/bayesian_optimization/scenario_07_03/results.csv`](experiments/bayesian_optimization/scenario_07_03/results.csv)

### Data Quality & Integrity Audit
Every candidate across all campaigns was checked for numerical validity and physical consistency:

```
Data Quality Verification Ledger:
┌──────────────────────────────┬──────────────┬──────────────┬──────────────┐
│ Verification Criteria        │ RS-100       │ BO Scenario A│ BO Scenario B│
├──────────────────────────────┼──────────────┼──────────────┼──────────────┤
│ Total Evaluations Logged     │ 100          │ 50           │ 50           │
│ Physical Simulation Flag     │ is_phys=True │ is_phys=True │ is_phys=True │
│ Wn in [0.12, 1.20] µm        │ 100 / 100    │ 50 / 50      │ 50 / 50      │
│ Wp in [0.24, 2.80] µm        │ 100 / 100    │ 50 / 50      │ 50 / 50      │
│ 10 nm Grid Alignment         │ 100 / 100    │ 50 / 50      │ 50 / 50      │
│ Duplicate Proposals          │ 1 duplicate  │ 0 duplicates │ 0 duplicates │
│ Unique Sizing Pairs          │ 99 / 100     │ 50 / 50      │ 50 / 50      │
│ Valid Sustained Oscillations │ 100 / 100    │ 49 / 50      │ 49 / 50      │
│ Feasibility Rate             │ 100.0%       │ 98.0%        │ 98.0%        │
│ Reciprocity (|f·T - 1| < 1%) │ 100 / 100    │ 49 / 49      │ 49 / 49      │
│ Delay Consistency (t_pd=T/10)│ 100 / 100    │ 49 / 49      │ 49 / 49      │
│ Non-Oscillation Failures     │ 0 failures   │ 1 failure    │ 1 failure    │
│ Failure Sizing Coordinates   │ None         │ (0.12, 0.24) │ (0.12, 0.24) │
└──────────────────────────────┴──────────────┴──────────────┴──────────────┘
```

The data confirm that the experimental datasets are authentic physical SPICE simulations free of NaN/Inf corruptions, off-grid proposals, or synthetic placeholders.

---

## 5. Scenario A Results — Balanced Objective (0.5 / 0.5)

In Scenario A, the optimizer was tasked with maximizing frequency and minimizing power with equal weight ($w_f = 0.5, w_p = 0.5$).

### 5.1 Best Candidate Metrics
The best feasible candidate was discovered at **Evaluation 12** (Adaptive BO Iteration 2):

| Metric Parameter | Baseline Circuit | Best Scenario A Candidate (Iter 12) | Absolute Delta | Percentage Change |
| :--- | :--- | :--- | :--- | :--- |
| **NMOS Width ($W_n$)** | $0.5000\ \mu\text{m}$ | **$0.1200\ \mu\text{m}$** | $-0.3800\ \mu\text{m}$ | $-76.00\%$ (Min Bound) |
| **PMOS Width ($W_p$)** | $1.0000\ \mu\text{m}$ | **$2.8000\ \mu\text{m}$** | $+1.8000\ \mu\text{m}$ | $+180.00\%$ (Max Bound) |
| **Sizing Ratio ($W_p / W_n$)**| $2.0000$ | **$23.3333$** | $+21.3333$ | High Asymmetry |
| **Oscillation Frequency ($f$)**| $41.069757\text{ GHz}$ | **$27.570924\text{ GHz}$** | $-13.498833\text{ GHz}$ | **$-32.87\%$** |
| **Average Power ($P_{avg}$)** | $140.169554\ \mu\text{W}$ | **$88.319000\ \mu\text{W}$** | $-51.850554\ \mu\text{W}$ | **$-36.99\%$ (Power Savings)** |
| **Stage Delay ($t_{pd}$)** | $2.434882\text{ ps}$ | **$3.627000\text{ ps}$** | $+1.192118\text{ ps}$ | $+48.96\%$ |
| **Period ($T = 10 \times t_{pd}$)**| $24.348820\text{ ps}$ | **$36.270100\text{ ps}$** | $+11.921280\text{ ps}$ | $+48.96\%$ |
| **Power-Delay Product (PDP)** | $0.341296\text{ fJ}$ | **$0.320334\text{ fJ}$** | $-0.020962\text{ fJ}$ | **$-6.14\%$ (Better Efficiency)** |
| **Objective Score ($\mathcal{F}_A$)** | $0.000000$ | **$+0.020616$** | $+0.020616$ | **$+0.020616$ Net Gain** |

### 5.2 Sizing and Electrical Trade-Off Analysis
Under equal weighting, Candidate 12 achieves a net positive score because the **$36.99\%$ reduction in power dissipation** outweighs the **$32.87\%$ reduction in oscillation frequency**:
$$\Delta \mathcal{F}_A = 0.5 \cdot (-0.3287) - 0.5 \cdot (-0.3699) = -0.16435 + 0.18495 = +0.02060 \approx +0.020616$$

Furthermore, the Power-Delay Product (energy per switching event) improved by **$6.14\%$** ($0.3413\text{ fJ} \to 0.3203\text{ fJ}$). The circuit is genuinely more energy-efficient per cycle. However, this optimization sacrificed speed: stage delay increased from $2.43\text{ ps}$ to $3.63\text{ ps}$.

### 5.3 Optimization Trajectory & Adaptive Sampling
- **Evaluations 1–10 (LHS):** Best candidate found was Iteration 8 ($W_n = 0.17\ \mu\text{m}, W_p = 1.56\ \mu\text{m}$, score $+0.002822$).
- **Evaluation 11 (Adaptive BO Step 1):** Probed $W_n = 0.12\ \mu\text{m}, W_p = 1.30\ \mu\text{m}$ (score $+0.003436$).
- **Evaluation 12 (Adaptive BO Step 2):** Probed the upper-left boundary $W_n = 0.12\ \mu\text{m}, W_p = 2.80\ \mu\text{m}$, establishing the campaign optimum ($+0.020616$).
- **Later Probes:** Subsequent adaptive iterations clustered heavily along the $W_n = 0.12\ \mu\text{m}$ boundary (e.g. Iter 13: $W_p = 2.64\ \mu\text{m}$, score $+0.0192$; Iter 37: $W_p = 2.75\ \mu\text{m}$, score $+0.02056$).

*Authoritative Artifacts:*
- Results Ledger: [`experiments/bayesian_optimization/scenario_05_05/results.csv`](experiments/bayesian_optimization/scenario_05_05/results.csv)
- Checkpoint: [`experiments/bayesian_optimization/scenario_05_05/checkpoint.json`](experiments/bayesian_optimization/scenario_05_05/checkpoint.json)
- Summary: [`experiments/bayesian_optimization/scenario_05_05/summary.md`](experiments/bayesian_optimization/scenario_05_05/summary.md)
- Standalone Convergence Plot: [`experiments/bayesian_optimization/scenario_05_05/analysis/convergence_campaign_a.png`](experiments/bayesian_optimization/scenario_05_05/analysis/convergence_campaign_a.png)
- Detailed Scenario A Report: [`experiments/bayesian_optimization/scenario_05_05/analysis/campaign_a_analysis.md`](experiments/bayesian_optimization/scenario_05_05/analysis/campaign_a_analysis.md)

---

## 6. Scenario B Results — Frequency-Priority Objective (0.7 / 0.3)

In Scenario B, the objective placed strong emphasis on frequency maximization ($w_f = 0.7$) with a reduced power penalty weight ($w_p = 0.3$).

### 6.1 Best Candidate Metrics
The best feasible candidate was discovered at **Evaluation 11** (Adaptive BO Iteration 1):

| Metric Parameter | Baseline Circuit | Best Scenario B Candidate (Iter 11) | Absolute Delta | Percentage Change |
| :--- | :--- | :--- | :--- | :--- |
| **NMOS Width ($W_n$)** | $0.5000\ \mu\text{m}$ | **$1.2000\ \mu\text{m}$** | $+0.7000\ \mu\text{m}$ | $+140.00\%$ (Max Bound) |
| **PMOS Width ($W_p$)** | $1.0000\ \mu\text{m}$ | **$2.8000\ \mu\text{m}$** | $+1.8000\ \mu\text{m}$ | $+180.00\%$ (Max Bound) |
| **Sizing Ratio ($W_p / W_n$)**| $2.0000$ | **$2.3333$** | $+0.3333$ | Balanced Pull-up/down |
| **Oscillation Frequency ($f$)**| $41.069757\text{ GHz}$ | **$105.655828\text{ GHz}$** | $+64.586071\text{ GHz}$ | **$+157.26\%$ (2.57× Speedup)** |
| **Average Power ($P_{avg}$)** | $140.169554\ \mu\text{W}$ | **$360.891000\ \mu\text{W}$** | $+220.721446\ \mu\text{W}$ | $+157.47\%$ (Higher Power) |
| **Stage Delay ($t_{pd}$)** | $2.434882\text{ ps}$ | **$0.946500\text{ ps}$** | $-1.488382\text{ ps}$ | **$-61.13\%$ (Sub-ps Delay)** |
| **Period ($T = 10 \times t_{pd}$)**| $24.348820\text{ ps}$ | **$9.464700\text{ ps}$** | $-14.884120\text{ ps}$ | $-61.13\%$ |
| **Power-Delay Product (PDP)** | $0.341296\text{ fJ}$ | **$0.341572\text{ fJ}$** | $+0.000276\text{ fJ}$ | $+0.08\%$ (Invariant) |
| **Objective Score ($\mathcal{F}_B$)** | $0.400000$ | **$1.028414$** | $+0.628414$ | **$+0.628414$ Net Gain** |

### 6.2 Sizing and Electrical Trade-Off Analysis
Under Scenario B weighting, the candidate delivered a massive **$+157.26\%$ increase in operating frequency** ($41.07\text{ GHz} \to 105.66\text{ GHz}$), driving per-stage delay down to **$0.9465\text{ ps}$** (a $61.13\%$ reduction).

This extreme speed required a **$+157.47\%$ increase in average power** ($140.17\ \mu\text{W} \to 360.89\ \mu\text{W}$). Because the frequency weight is $0.7$ and power weight is only $0.3$, the net utility gain was substantial:
$$\Delta \mathcal{F}_B = 0.7 \cdot (+1.5726) - 0.3 \cdot (+1.5747) = +1.1008 - 0.4724 = +0.6284$$
$$\mathcal{F}_B = 0.400000 + 0.628414 = 1.028414$$

Notice that the Power-Delay Product remained essentially constant ($0.3413\text{ fJ} \to 0.3416\text{ fJ}$, a $+0.08\%$ change). In a generic Level-1 MOS model at constant $V_{DD}$, dynamic power scales directly with frequency ($P \propto C V_{DD}^2 f$). The increased channel widths elevated charging currents proportionally to the capacitive load, leaving switching energy unchanged while dramatically accelerating cycle time.

### 6.3 Boundary Optimum Observation
Candidate 11 sits at the simultaneous upper bounds of both transistor widths ($W_n = 1.20\ \mu\text{m}, W_p = 2.80\ \mu\text{m}$). This is an **observed boundary optimum** within the defined search envelope, rather than a proven unconstrained global optimum.

*Authoritative Artifacts:*
- Results Ledger: [`experiments/bayesian_optimization/scenario_07_03/results.csv`](experiments/bayesian_optimization/scenario_07_03/results.csv)
- Checkpoint: [`experiments/bayesian_optimization/scenario_07_03/checkpoint.json`](experiments/bayesian_optimization/scenario_07_03/checkpoint.json)
- Summary: [`experiments/bayesian_optimization/scenario_07_03/summary.md`](experiments/bayesian_optimization/scenario_07_03/summary.md)
- Convergence Plot: [`experiments/bayesian_optimization/scenario_07_03/analysis/convergence_scenario_b.png`](experiments/bayesian_optimization/scenario_07_03/analysis/convergence_scenario_b.png)
- Design-Space Plot: [`experiments/bayesian_optimization/scenario_07_03/analysis/design_space_scenario_b.png`](experiments/bayesian_optimization/scenario_07_03/analysis/design_space_scenario_b.png)
- Detailed Scenario B Report: [`experiments/bayesian_optimization/scenario_07_03/analysis/campaign_b_analysis.md`](experiments/bayesian_optimization/scenario_07_03/analysis/campaign_b_analysis.md)

---

## 7. Random Search Versus Bayesian Optimization

This section presents the primary method comparison between Bayesian Optimization and Random Search on Scenario A ($w_f = 0.5, w_p = 0.5$).

### 7.1 Comparison Protocols
Per Section 16 of [`SRS.md`](SRS.md), two distinct comparison protocols were applied:
1. **Equal-Budget Comparison:** The first 50 chronological evaluations of the formal Random Search dataset (RS-50) vs. all 50 evaluations of Campaign A (BO-50).
2. **Full-Budget Comparison:** All 100 evaluations of the formal Random Search dataset (RS-100) vs. all 50 evaluations of Campaign A (BO-50).

### 7.2 Method Comparison Table

| Metric | Baseline | Random Search (RS-50) | Bayesian Optimization (BO-50) | Random Search (RS-100) |
| :--- | :--- | :--- | :--- | :--- |
| **Evaluation Budget** | Reference | 50 physical evals | **50 physical evals** | 100 physical evals |
| **Best NMOS Width ($W_n$)** | $0.50\ \mu\text{m}$ | $0.17\ \mu\text{m}$ | **$0.12\ \mu\text{m}$** (Min Bound) | $0.19\ \mu\text{m}$ |
| **Best PMOS Width ($W_p$)** | $1.00\ \mu\text{m}$ | $1.91\ \mu\text{m}$ | **$2.80\ \mu\text{m}$** (Max Bound) | $2.66\ \mu\text{m}$ |
| **Sizing Ratio ($W_p/W_n$)** | $2.0000$ | $11.2353$ | **$23.3333$** | $14.0000$ |
| **Oscillation Frequency** | $41.0698\text{ GHz}$ | $28.9302\text{ GHz}$ | **$27.5709\text{ GHz}$** | $35.3689\text{ GHz}$ |
| **Average Power** | $140.1696\ \mu\text{W}$| $97.3940\ \mu\text{W}$ | **$88.3190\ \mu\text{W}$** | $117.6510\ \mu\text{W}$ |
| **Stage Propagation Delay**| $2.4349\text{ ps}$ | $3.4566\text{ ps}$ | **$3.6270\text{ ps}$** | $2.8273\text{ ps}$ |
| **Power-Delay Product** | $0.3413\text{ fJ}$ | $0.3367\text{ fJ}$ | **$0.3203\text{ fJ}$** | $0.3326\text{ fJ}$ |
| **Objective Score ($\mathcal{F}_A$)**| $0.000000$ | **$+0.004793$** | **$+0.020616$** | **$+0.010923$** |
| **Net Gain Over Baseline**| $0.000000$ | $+0.004793$ | **$+0.020616$ ($>4.3\times$ RS-50)** | $+0.010923$ ($1.89\times$ in half budget) |
| **Evaluation Discovered** | — | **Evaluation 28** | **Evaluation 12** | **Evaluation 62** |
| **Feasible Simulations** | $1 / 1$ ($100\%$) | $50 / 50$ ($100.0\%$) | $49 / 50$ ($98.0\%$) | $100 / 100$ ($100.0\%$) |

*Persisted Data File:* [`experiments/bayesian_optimization/scenario_05_05/analysis/comparison_rs_vs_bo.csv`](experiments/bayesian_optimization/scenario_05_05/analysis/comparison_rs_vs_bo.csv)

### 7.3 Visual Convergence & Design-Space Observations

1. **Equal-Budget Convergence ([`convergence_equal_budget.png`](experiments/bayesian_optimization/scenario_05_05/analysis/convergence_equal_budget.png)):**
   During the initial 10 space-filling evaluations, BO reached a score of $+0.002822$, comparable to Random Search at evaluation 10 ($+0.002156$). At Evaluation 11, BO initiated adaptive GP/EI modeling. At Evaluation 12, BO leapt to $+0.020616$. Random Search progressed slowly, discovering its 50-evaluation best at Evaluation 28 ($+0.004793$) and plateauing thereafter.
2. **Full-Budget Convergence ([`convergence_full_budget.png`](experiments/bayesian_optimization/scenario_05_05/analysis/convergence_full_budget.png)):**
   Random Search required 62 physical simulations to locate its campaign-best candidate ($W_n = 0.19\ \mu\text{m}, W_p = 2.66\ \mu\text{m}$, score $+0.010923$). BO reached a superior design ($+0.020616$) in **12 evaluations** — less than one-fifth the evaluation count of RS-100.
3. **Design-Space Coverage ([`design_space_comparison.png`](experiments/bayesian_optimization/scenario_05_05/analysis/design_space_comparison.png)):**
   Random Search distributed candidates uniformly across the box $[0.12, 1.20] \times [0.24, 2.80]\ \mu\text{m}$. In contrast, BO rapidly identified the high-utility low-power basin near the boundary corner $W_n \approx 0.12\ \mu\text{m}, W_p \approx 2.80\ \mu\text{m}$, evaluating multiple candidates in this zone while periodically sampling other areas to manage model uncertainty.
4. **Frequency-Power Trade-Off ([`frequency_power_comparison.png`](experiments/bayesian_optimization/scenario_05_05/analysis/frequency_power_comparison.png)):**
   Visualizes how BO candidates trace the lower boundary of the power-frequency envelope, successfully finding the design with the lowest average power dissipation ($88.32\ \mu\text{W}$).

---

## 8. Cross-Scenario Analysis: Impact of Objective Weights on Sizing

The contrast between Scenario A and Scenario B reveals how numerical objective weighting dictates the converged circuit geometry.

### 8.1 Sizing Shift and Trade-Off Table

| Parameter / Metric | Baseline Reference | Scenario A (Balanced 0.5/0.5) | Scenario B (Speed-Priority 0.7/0.3) | Physical Sizing Shift |
| :--- | :--- | :--- | :--- | :--- |
| **NMOS Width ($W_n$)** | $0.50\ \mu\text{m}$ | **$0.12\ \mu\text{m}$** (Minimum Bound) | **$1.20\ \mu\text{m}$** (Maximum Bound) | **10.0× NMOS width increase** |
| **PMOS Width ($W_p$)** | $1.00\ \mu\text{m}$ | **$2.80\ \mu\text{m}$** (Maximum Bound) | **$2.80\ \mu\text{m}$** (Maximum Bound) | Both pin PMOS to upper bound |
| **Sizing Ratio ($W_p/W_n$)** | $2.0000$ | **$23.3333$** | **$2.3333$** | High asymmetry $\to$ balanced pull |
| **Oscillation Frequency** | $41.0698\text{ GHz}$ | **$27.5709\text{ GHz}$** ($-32.87\%$) | **$105.6558\text{ GHz}$** (**$+157.26\%$**) | **3.83× frequency span** |
| **Average Power Dissipation** | $140.1696\ \mu\text{W}$| **$88.3190\ \mu\text{W}$** (**$-36.99\%$**) | **$360.8910\ \mu\text{W}$** ($+157.47\%$) | **4.09× power span** |
| **Stage Propagation Delay** | $2.4349\text{ ps}$ | **$3.6270\text{ ps}$** ($+48.96\%$) | **$0.9465\text{ ps}$** (**$-61.13\%$**) | Low-power $\to$ Sub-picosecond |
| **Power-Delay Product** | $0.3413\text{ fJ}$ | **$0.3203\text{ fJ}$** (**$-6.14\%$**) | **$0.3416\text{ fJ}$** ($+0.08\%$) | Power savings $\to$ energy parity |
| **Native Scenario Score** | $F_A=0.000 / F_B=0.400$| **$\mathcal{F}_A = +0.020616$** | **$\mathcal{F}_B = +1.028414$** | Evaluated under native formula |
| **Cross-Evaluated Score** | — | $\mathcal{F}_B = +0.280898$ | $\mathcal{F}_A = -0.001040$ | Both penalized under opposite target |
| **Net Gain Over Baseline** | $0.000000$ | **$+0.020616$** | **$+0.628414$** | Verified positive improvement |
| **Discovery Evaluation** | — | **Evaluation 12** | **Evaluation 11** | Early discovery in both campaigns |

*Persisted Data File:* [`experiments/bayesian_optimization/scenario_07_03/analysis/comparison_scenario_a_vs_scenario_b.csv`](experiments/bayesian_optimization/scenario_07_03/analysis/comparison_scenario_a_vs_scenario_b.csv)

### 8.2 Cross-Evaluation Demonstrates Optimization Specialization
To confirm that each candidate is genuinely specialized for its respective objective, each candidate was cross-evaluated under the opposing formula:

1. **Candidate A Scored Under Scenario B:**
   $$\mathcal{F}_B(\text{Candidate A}) = 0.7 \left(\frac{27.570924}{41.069757}\right) - 0.3 \left(\frac{88.319000}{140.169554}\right) = 0.469924 - 0.189026 = \mathbf{+0.280898}$$
   Baseline under Scenario B is $0.400000$. Candidate A incurs a net loss of **$-0.119102$** relative to baseline because its frequency drop is heavily penalized under $w_f = 0.7$.
2. **Candidate B Scored Under Scenario A:**
   $$\mathcal{F}_A(\text{Candidate B}) = 0.5 \left(\frac{105.655828}{41.069757}\right) - 0.5 \left(\frac{360.891000}{140.169554}\right) = 1.286298 - 1.287338 = \mathbf{-0.001040}$$
   Baseline under Scenario A is $0.000000$. Candidate B incurs a net loss of **$-0.001040$** because its power dissipation ($+157.47\%$) marginally outstrips its frequency gain ($+157.26\%$).

This cross-evaluation confirms that the Bayesian Optimization algorithm navigated to genuinely different regions of the Pareto frontier in response to the scalar weights.

### 8.3 Comparative Visualizations
- **Cross-Scenario Design Space ([`cross_scenario_design_space.png`](experiments/bayesian_optimization/scenario_07_03/analysis/cross_scenario_design_space.png)):** Illustrates the bipolar clustering: Scenario A points gather at the minimum-$W_n$ boundary ($0.12\ \mu\text{m}$), whereas Scenario B points gather at the maximum-$W_n$ boundary ($1.20\ \mu\text{m}$).
- **Cross-Scenario Frequency vs. Power ([`cross_scenario_frequency_power.png`](experiments/bayesian_optimization/scenario_07_03/analysis/cross_scenario_frequency_power.png)):** Displays the two candidates anchoring opposite ends of the operational trade-off curve spanning $27.6\text{ GHz}$ to $105.7\text{ GHz}$ and $88.3\ \mu\text{W}$ to $360.9\ \mu\text{W}$.

---

## 9. Consolidated Results Matrix

The table below unifies all experimental campaigns into a single reference matrix:

| Campaign / Configuration | Method & Seed | Budget Used | Best $W_n$ ($\mu\text{m}$) | Best $W_p$ ($\mu\text{m}$) | Sizing Ratio | Frequency ($\text{GHz}$) | Power ($\mu\text{W}$) | Delay ($\text{ps}$) | PDP ($\text{fJ}$) | Native Score $\mathcal{F}$ | Net Gain $\Delta \mathcal{F}$ | Eval Found | Feasible / Total |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline Circuit** | Reference | 1 | 0.50 | 1.00 | 2.0000 | 41.070 | 140.170 | 2.435 | 0.3413 | $F_A=0.000$ / $F_B=0.400$ | 0.000000 | Baseline | 1 / 1 (100%) |
| **RS-50 (Scenario A)** | RS (Seed 2026) | 50 | 0.17 | 1.91 | 11.2353 | 28.930 | 97.394 | 3.457 | 0.3367 | $\mathcal{F}_A = +0.004793$ | $+0.004793$ | Eval 28 | 50 / 50 (100%) |
| **RS-100 (Scenario A)** | RS (Seed 2026) | 100 | 0.19 | 2.66 | 14.0000 | 35.369 | 117.651 | 2.827 | 0.3326 | $\mathcal{F}_A = +0.010923$ | $+0.010923$ | Eval 62 | 100 / 100 (100%) |
| **BO-50 Scenario A** | BO (Seed 2026) | 50 | **0.12** | **2.80** | 23.3333 | 27.571 | **88.319** | 3.627 | **0.3203** | $\mathcal{F}_A = \mathbf{+0.020616}$ | $\mathbf{+0.020616}$ | **Eval 12** | 49 / 50 (98%) |
| **BO-50 Scenario B** | BO (Seed 3031) | 50 | **1.20** | **2.80** | 2.3333 | **105.656** | 360.891 | **0.9465** | 0.3416 | $\mathcal{F}_B = \mathbf{+1.028414}$ | $\mathbf{+0.628414}$ | **Eval 11** | 49 / 50 (98%) |

---

## 10. Main Research Findings

The empirical evidence supports the following findings:

1. **Early Convergence in Adaptive Optimization:** In both 50-evaluation campaigns, the Gaussian Process surrogate located its campaign-best candidate on either the first (Scenario B, Eval 11) or second (Scenario A, Eval 12) adaptive query following the 10-point LHS initialization.
2. **Quantitative Outperformance vs. Random Search:** For Scenario A, BO-50 achieved an objective improvement $+0.020616$, exceeding equal-budget Random Search ($+0.004793$) by $>4.3\times$, and full-budget Random Search ($+0.010923$) by $1.89\times$ in half the total simulation count.
3. **Objective Weights Dictate Inverter Geometry:** Transitioning from balanced weights ($0.5/0.5$) to speed priority ($0.7/0.3$) triggered a $10\times$ increase in optimal NMOS width ($0.12\ \mu\text{m} \to 1.20\ \mu\text{m}$) and collapsed the width ratio from $23.33$ to $2.33$.
4. **Sub-Picosecond Delay Realized at Boundary:** Scenario B demonstrated that at maximum width ($1.20\ \mu\text{m} / 2.80\ \mu\text{m}$), 5-stage ring oscillator propagation delay reaches $0.9465\text{ ps}$ ($105.66\text{ GHz}$ oscillation), confirming that current drive scaling outpaces inverter self-loading up to the tested upper bounds.
5. **Dynamic Power vs. Sizing Scaling:** Scenario A achieved a $36.99\%$ power reduction ($140.17\ \mu\text{W} \to 88.32\ \mu\text{W}$) and improved energy-per-cycle (PDP) by $6.14\%$ ($0.3203\text{ fJ}$).
6. **Consistent Oscillation Failure Boundary:** Across two independent campaigns totaling 100 simulations, the only observed failure occurred at $W_n = 0.12\ \mu\text{m}, W_p = 0.24\ \mu\text{m}$ (Iteration 17 in both runs), empirically establishing that simultaneous minimum channel widths fail to sustain oscillation under a $0.5\text{ fF}$ stage load.

---

## 11. Engineering Interpretation and Circuit Physics

### 11.1 Drive Current vs. Capacitive Self-Loading
Ring oscillator propagation delay per inverter stage is approximated by:
$$t_{pd} \approx \frac{C_{load} + C_{self}}{2} \cdot \left(\frac{V_{DD}}{I_{dsat,n}} + \frac{V_{DD}}{I_{dsat,p}}\right)$$
where $I_{dsat} \propto (W/L)(V_{DD} - V_{th})^\alpha$.
- In **Scenario B**, scaling $W_n$ to $1.20\ \mu\text{m}$ and $W_p$ to $2.80\ \mu\text{m}$ maximized $I_{dsat,n}$ and $I_{dsat,p}$. Because the fixed load capacitance ($C_{load} = 0.5\text{ fF}$) represents a significant portion of the total nodal capacitance, increasing transistor widths delivered substantial net gains in charging speed before self-capacitance ($C_{self} \propto W_n + W_p$) dominated.
- In **Scenario A**, reducing $W_n$ to $0.12\ \mu\text{m}$ minimized input gate capacitance $C_{gg,n} \approx W_n L C_{ox}$, suppressing the switching charge $Q = C_{node} V_{DD}$ required each half-cycle. Although discharge current was constrained (increasing delay to $3.63\text{ ps}$), dynamic power dissipation dropped precipitously to $88.32\ \mu\text{W}$.

### 11.2 PMOS Sizing Convergence at Maximum Bound
In both Scenario A and Scenario B, $W_p$ converged to the upper boundary ($2.80\ \mu\text{m}$). In CMOS technology, hole mobility $\mu_p$ is roughly half that of electron mobility $\mu_n$ ($\mu_n / \mu_p \approx 2\text{--}3$).
- In Scenario B, large $W_p$ is required to match NMOS pull-down strength and maximize total loop gain.
- In Scenario A, maintaining $W_p = 2.80\ \mu\text{m}$ while reducing $W_n$ to $0.12\ \mu\text{m}$ created an asymmetrical inverter where PMOS strongly charges the node while NMOS slowly discharges it, sustaining oscillation at low switching current.

### 11.3 Oscillation Failure Criterion
At $W_n = 0.12\ \mu\text{m}$ and $W_p = 0.24\ \mu\text{m}$, the inverter's small-signal transconductance $g_m$ falls below the critical threshold required to satisfy Barkhausen's criterion for a 5-stage ring ($|A_v(j\omega_0)| \ge \sec(\pi/5) \approx 1.236$). The inverters cannot charge and discharge the $0.5\text{ fF}$ load rapidly enough to establish regenerative feedback.

---

## 12. Limitations and Threats to Validity

To preserve scientific rigor, the conclusions of this study are scoped within the following explicit limitations:

1. **Single Fixed Seed per Method:** Campaign A used Seed 2026; Campaign B used Seed 3031; Random Search used Seed 2026. While fully reproducible, single-seed runs do not quantify stochastic performance distributions. True statistical superiority requires multi-seed ensemble trials (e.g., 5–10 independent seeds).
2. **Boundary Solutions:** Both scenario optima lie on search space boundaries ($W_n = 0.12\ \mu\text{m}$ in Scenario A; $W_n = 1.20\ \mu\text{m}, W_p = 2.80\ \mu\text{m}$ in Scenario B). These points represent the best designs *within the evaluated bounding box*, not unconstrained global optima. Expanding bounds beyond $1.20\ \mu\text{m}$ or below $0.12\ \mu\text{m}$ could yield different optima.
3. **Model Simplification:** The Level-1 SPICE model does not include short-channel effects present in sub-100nm physical silicon (velocity saturation, DIBL, gate leakage, source/drain resistance). These results represent behavior of the specified simulation model, not fabricated silicon.
4. **Idealized Interconnects:** Interconnect loading was modeled as lumped $0.5\text{ fF}$ capacitors without distributed $RC$ wiring parasitics or layout extraction (PEX).

---

## 13. Defensible Research Conclusions

Within the evaluated simulation framework, the following conclusions are justified:

1. **Sample Efficiency:** In the evaluated fixed-seed trials, Bayesian Optimization demonstrated higher sample efficiency than Random Search, discovering superior designs within 12 evaluations compared to 62 evaluations required by Random Search.
2. **Optimization Versatility:** Gaussian Process surrogate modeling effectively navigated the smooth trade-off surface of CMOS inverter sizing, responding to objective weighting by discovering distinct operating modes (low-power vs. high-speed).
3. **Electrical Trade-Off Reality:** Transistor sizing in a 5-stage CMOS ring oscillator exhibits clear trade-offs: speed can be expanded up to $105.7\text{ GHz}$ ($0.95\text{ ps}$ delay) by maximizing widths at the cost of a $2.57\times$ power increase, whereas power can be reduced to $88.3\ \mu\text{W}$ by minimizing NMOS width at the expense of a $32.9\%$ frequency drop.
4. **Scope of Claim:** These findings demonstrate the utility of Bayesian Optimization for simulation-in-the-loop analog/custom digital sizing within a bounded search space, but do not imply universal superiority across all circuits or fabrication readiness without calibrated PDK models.

---

## 14. Prioritized Future Work

### High Priority (Scientific Rigor & Generalization)
1. **Multi-Seed Statistical Replication:** Run 5–10 independent seeds for both BO and Random Search to compute mean convergence rates, variance, and confidence intervals.
2. **Search-Space Boundary Expansion:** Broaden $W_n$ to $[0.10, 2.50]\ \mu\text{m}$ and $W_p$ to $[0.20, 5.00]\ \mu\text{m}$ to determine if Candidate B's speed peak plateaus due to self-loading.
3. **Multi-Objective Bayesian Optimization (MOBO):** Implement Pareto-frontier exploration using algorithms such as qEHVI (Expected Hypervolume Improvement) to generate the complete continuous Pareto front without scalar weight selection.

### Medium Priority (Physical Realism)
4. **Foundry PDK Validation:** Port netlists to BSIM4 or BSIM-CMG models from open-source PDKs (e.g., SkyWater 130nm or IHP 130nm) to assess behavior under calibrated short-channel physics.
5. **PVT Operating Corners:** Execute sensitivity sweeps over $V_{DD}$ ($\pm 10\%$) and temperature ($-40^\circ\text{C}$ to $125^\circ\text{C}$) to assess candidate sizing stability across environmental variations.

---

## 15. Reproducibility and Artifact Index

All source code, configuration files, raw simulation data, and analysis plots are version-controlled and reproducible from the paths below:

| Artifact Description | Purpose | Relative Repository Path |
| :--- | :--- | :--- |
| **System Requirements (SRS)** | Single Source of Truth for methodology | [`SRS.md`](SRS.md) |
| **Project Context & History** | Chronological record of design decisions | [`CONTEXT.md`](CONTEXT.md) |
| **Formal BO Configuration** | Frozen parameters, bounds, seeds | [`configs/bayesian_optimization_config.yaml`](configs/bayesian_optimization_config.yaml) |
| **Scenario A Campaign Runner** | Physical & dry-run runner for Scenario A | [`experiments/run_bayesian_opt_scenario_a.py`](experiments/run_bayesian_opt_scenario_a.py) |
| **Scenario B Campaign Runner** | Physical & dry-run runner for Scenario B | [`experiments/run_bayesian_opt_scenario_b.py`](experiments/run_bayesian_opt_scenario_b.py) |
| **Formal RS Campaign Runner** | 100-evaluation Random Search runner | [`experiments/run_formal_random_search_100.py`](experiments/run_formal_random_search_100.py) |
| **Random Search 100 Results** | Authoritative 100-eval RS physical ledger | [`experiments/random_search/formal_100/results.csv`](experiments/random_search/formal_100/results.csv) |
| **Random Search 100 Summary** | Report on formal Random Search campaign | [`RANDOM_SEARCH_FORMAL_100.md`](RANDOM_SEARCH_FORMAL_100.md) |
| **Scenario A Results Ledger** | Authoritative 50-eval BO physical ledger | [`experiments/bayesian_optimization/scenario_05_05/results.csv`](experiments/bayesian_optimization/scenario_05_05/results.csv) |
| **Scenario A Checkpoint** | Checkpoint state & best candidate | [`experiments/bayesian_optimization/scenario_05_05/checkpoint.json`](experiments/bayesian_optimization/scenario_05_05/checkpoint.json) |
| **Scenario A Analysis Report** | Comprehensive Scenario A analysis | [`experiments/bayesian_optimization/scenario_05_05/analysis/campaign_a_analysis.md`](experiments/bayesian_optimization/scenario_05_05/analysis/campaign_a_analysis.md) |
| **RS vs. BO Comparison CSV** | Tabular comparison (Baseline, RS, BO) | [`experiments/bayesian_optimization/scenario_05_05/analysis/comparison_rs_vs_bo.csv`](experiments/bayesian_optimization/scenario_05_05/analysis/comparison_rs_vs_bo.csv) |
| **Equal-Budget Plot** | Convergence comparison (50 vs. 50 evals) | [`experiments/bayesian_optimization/scenario_05_05/analysis/convergence_equal_budget.png`](experiments/bayesian_optimization/scenario_05_05/analysis/convergence_equal_budget.png) |
| **Full-Budget Plot** | Convergence comparison (50 BO vs. 100 RS) | [`experiments/bayesian_optimization/scenario_05_05/analysis/convergence_full_budget.png`](experiments/bayesian_optimization/scenario_05_05/analysis/convergence_full_budget.png) |
| **Design-Space Comparison Plot** | Sampling distribution (BO vs. RS) | [`experiments/bayesian_optimization/scenario_05_05/analysis/design_space_comparison.png`](experiments/bayesian_optimization/scenario_05_05/analysis/design_space_comparison.png) |
| **Scenario B Results Ledger** | Authoritative 50-eval BO physical ledger | [`experiments/bayesian_optimization/scenario_07_03/results.csv`](experiments/bayesian_optimization/scenario_07_03/results.csv) |
| **Scenario B Checkpoint** | Checkpoint state & best candidate | [`experiments/bayesian_optimization/scenario_07_03/checkpoint.json`](experiments/bayesian_optimization/scenario_07_03/checkpoint.json) |
| **Scenario B Analysis Report** | Comprehensive Scenario B analysis | [`experiments/bayesian_optimization/scenario_07_03/analysis/campaign_b_analysis.md`](experiments/bayesian_optimization/scenario_07_03/analysis/campaign_b_analysis.md) |
| **Scenario A vs. B Comparison CSV**| Tabular cross-scenario comparison | [`experiments/bayesian_optimization/scenario_07_03/analysis/comparison_scenario_a_vs_scenario_b.csv`](experiments/bayesian_optimization/scenario_07_03/analysis/comparison_scenario_a_vs_scenario_b.csv) |
| **Scenario B Convergence Plot** | Best-so-far objective trajectory | [`experiments/bayesian_optimization/scenario_07_03/analysis/convergence_scenario_b.png`](experiments/bayesian_optimization/scenario_07_03/analysis/convergence_scenario_b.png) |
| **Scenario B Design-Space Plot** | Sampling distribution across grid | [`experiments/bayesian_optimization/scenario_07_03/analysis/design_space_scenario_b.png`](experiments/bayesian_optimization/scenario_07_03/analysis/design_space_scenario_b.png) |
| **Cross-Scenario Design Space** | Dual convergence map (Scenario A vs. B) | [`experiments/bayesian_optimization/scenario_07_03/analysis/cross_scenario_design_space.png`](experiments/bayesian_optimization/scenario_07_03/analysis/cross_scenario_design_space.png) |
| **Cross-Scenario Pareto Plot** | Frequency vs. Power trade-off landscape | [`experiments/bayesian_optimization/scenario_07_03/analysis/cross_scenario_frequency_power.png`](experiments/bayesian_optimization/scenario_07_03/analysis/cross_scenario_frequency_power.png) |

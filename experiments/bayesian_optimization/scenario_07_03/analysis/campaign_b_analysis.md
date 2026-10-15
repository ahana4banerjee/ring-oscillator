# Bayesian Optimization Campaign B: Analysis & Cross-Scenario Comparison Report

**Document ID:** `BO-CAMPAIGN-B-ANALYSIS-01`  
**Scenario:** Scenario B (Frequency-Priority: $w_f = 0.7$, $w_p = 0.3$)  
**Status:** COMPLETE & VERIFIED  
**Campaign ID:** `bo_scenario_b_3031_physical_20261015_081542`  
**Authoritative Dataset:** [`experiments/bayesian_optimization/scenario_07_03/results.csv`](../results.csv)  
**Cross-Scenario Reference Dataset:** [`experiments/bayesian_optimization/scenario_05_05/results.csv`](../../scenario_05_05/results.csv)  
**Date:** October 2026  

---

## 1. Executive Summary

Bayesian Optimization (BO) Campaign B was successfully executed as an end-to-end physical simulation study using LTspice on the 5-stage CMOS ring oscillator across the frozen design space ($W_n \in [0.12, 1.20]\ \mu\text{m}$, $W_p \in [0.24, 2.80]\ \mu\text{m}$, 10 nm grid resolution, 28,013 valid points).

Key findings:
1. **Physical Simulation Execution:** All 50 physical evaluations completed via headless LTspice (`is_synthetic = False`), consuming 163.72 seconds total runtime. 49 of 50 candidates (98.0%) oscillated with valid metrics. Exactly one non-oscillating failure occurred at the extreme lower boundary ($W_n = 0.12\ \mu\text{m}, W_p = 0.24\ \mu\text{m}$, Iteration 17), identical to Campaign A.
2. **Best Feasible Candidate Discovery:** Discovered at **Evaluation 11** (Adaptive BO Iteration 1) with maximum transistor widths $W_n = 1.2000\ \mu\text{m}$, $W_p = 2.8000\ \mu\text{m}$ ($W_p/W_n = 2.3333$), achieving an objective score of $\mathcal{F}_{0.7/0.3} = \mathbf{1.028414}$ ($\Delta \mathcal{F} = \mathbf{+0.628414}$ above baseline $0.400000$).
3. **Extreme High-Speed Performance:** Candidate 11 achieved an oscillation frequency of **$105.656\text{ GHz}$** (+157.26% speedup relative to baseline $41.07\text{ GHz}$), with a sub-picosecond per-stage propagation delay of **$0.9465\text{ ps}$** ($-61.13\%$ delay reduction).
4. **Dramatic Design-Space Shift:** By changing objective weights from Balanced ($0.5/0.5$) to Frequency-Priority ($0.7/0.3$), the optimizer fundamentally shifted its preference from the minimum-$W_n$ boundary ($W_n = 0.12\ \mu\text{m}, W_p = 2.80\ \mu\text{m}$, $27.57\text{ GHz}, 88.32\ \mu\text{W}$) to the maximum-$W_n$ boundary ($W_n = 1.20\ \mu\text{m}, W_p = 2.80\ \mu\text{m}$, $105.66\text{ GHz}, 360.89\ \mu\text{W}$).

---

## 2. Dataset Validation & Execution Telemetry

| Parameter | Frozen Specification | Observed Value | Status |
| :--- | :--- | :--- | :--- |
| **Total Evaluations** | 50 physical simulations | 50 rows in `results.csv` | **VALIDATED** |
| **Initial Design Budget** | 10 LHS evaluations (Seed 3031) | Iterations 1–10 logged as LHS | **VALIDATED** |
| **Adaptive BO Budget** | 40 GP/EI evaluations | Iterations 11–50 logged as ADAPTIVE_BO | **VALIDATED** |
| **Feasible Simulations** | Sustainable steady-state oscillation | 49 / 50 (98.0%) | **VALIDATED** |
| **Non-Oscillating Failures**| Conditioned penalty assignment | 1 / 50 (Iteration 17, $F = -1.0\times 10^9$) | **VALIDATED** |
| **Manufacturing Grid** | Discrete 10 nm DRC grid step | All candidates integer multiples of 10 nm | **VALIDATED** |
| **Campaign Output Directory**| Dedicated `scenario_07_03/` | Isolated; no overwriting of Campaign A | **VALIDATED** |
| **Total Physical Runtime** | Batch execution watchdog | 163.72 seconds (~3.27 s/evaluation) | **VALIDATED** |

---

## 3. Campaign B Optimization Trajectory & Best-Candidate Discovery

### 3.1 Objective Trajectory Milestones
- **Eval 10 (LHS Phase Complete):** Best-so-far = **$+0.953184$** (Discovered at Eval 9: $W_n = 1.18\ \mu\text{m}, W_p = 2.41\ \mu\text{m}$, $f = 97.852\text{ GHz}$).
- **Eval 11 (Adaptive BO Step 1):** Best-so-far = **$+1.028414$** (Discovered at Eval 11: $W_n = 1.20\ \mu\text{m}, W_p = 2.80\ \mu\text{m}$, $f = 105.656\text{ GHz}$).
- **Eval 20:** Best-so-far = **$+1.028414$** (Candidate 11 holding).
- **Eval 30:** Best-so-far = **$+1.028414$** (Candidate 11 holding).
- **Eval 40:** Best-so-far = **$+1.028414$** (Candidate 11 holding).
- **Eval 50 (Campaign Complete):** Best-so-far = **$+1.028414$** (Final Best).

### 3.2 Adaptive Sampling Dynamics
Upon completing the 10-point LHS initialization, the Gaussian Process surrogate immediately recognized the strong gradient favoring maximum current drive ($W_n \to 1.20\ \mu\text{m}, W_p \to 2.80\ \mu\text{m}$). On its very first adaptive query (Evaluation 11), the Expected Improvement acquisition function selected the extreme boundary corner ($W_n = 1.20\ \mu\text{m}, W_p = 2.80\ \mu\text{m}$), establishing the global maximum of the campaign.

Subsequent adaptive queries heavily exploited this high-speed boundary zone while validating fine 10 nm grid neighbors:
- Iteration 12: $W_n = 1.15\ \mu\text{m}, W_p = 2.80\ \mu\text{m} \implies f = 103.190\text{ GHz}, F = 1.0044$
- Iteration 13: $W_n = 1.20\ \mu\text{m}, W_p = 2.79\ \mu\text{m} \implies f = 105.487\text{ GHz}, F = 1.0270$
- Iteration 14: $W_n = 1.20\ \mu\text{m}, W_p = 2.73\ \mu\text{m} \implies f = 104.467\text{ GHz}, F = 1.0172$
- Iteration 31: $W_n = 1.20\ \mu\text{m}, W_p = 2.78\ \mu\text{m} \implies f = 105.318\text{ GHz}, F = 1.0252$
- Iterations 34–50: Exhaustively mapped the upper corner $[1.17, 1.20]\ \mu\text{m} \times [2.72, 2.80]\ \mu\text{m}$ with 17 consecutive evaluations confirming the smoothness and convex plateau of the frequency maximum.

---

## 4. Electrical Metric Analysis: Baseline vs. Best Scenario B Candidate

| Electrical Metric | Baseline Reference ($0.5\mu\text{m} / 1.0\mu\text{m}$) | Best Scenario B Candidate (Iter 11) | Absolute Change | Percentage Change |
| :--- | :--- | :--- | :--- | :--- |
| **NMOS Width ($W_n$)** | $0.5000\ \mu\text{m}$ | **$1.2000\ \mu\text{m}$** | $+0.7000\ \mu\text{m}$ | $+140.00\%$ (Max Bound) |
| **PMOS Width ($W_p$)** | $1.0000\ \mu\text{m}$ | **$2.8000\ \mu\text{m}$** | $+1.8000\ \mu\text{m}$ | $+180.00\%$ (Max Bound) |
| **Width Sizing Ratio ($W_p/W_n$)**| $2.0000$ | **$2.3333$** | $+0.3333$ | $+16.67\%$ (Balanced Drive) |
| **Oscillation Frequency ($f$)**| $41.069757\text{ GHz}$ | **$105.655828\text{ GHz}$** | $+64.586071\text{ GHz}$ | **$+157.26\%$ (2.57× Speedup)** |
| **Average Power Dissipation ($P$)**| $140.169554\ \mu\text{W}$ | **$360.891000\ \mu\text{W}$** | $+220.721446\ \mu\text{W}$ | $+157.47\%$ (Higher Dissipation) |
| **Stage Propagation Delay ($t_{pd}$)**| $2.434882\text{ ps}$ | **$0.946500\text{ ps}$** | $-1.488382\text{ ps}$ | **$-61.13\%$ (Sub-ps Delay)** |
| **Oscillation Period ($T$)** | $24.348820\text{ ps}$ | **$9.464700\text{ ps}$** | $-14.884120\text{ ps}$ | Matches $10 \times t_{pd}$ |
| **Power-Delay Product (PDP)** | $0.341296\text{ fJ}$ | **$0.341572\text{ fJ}$** | $+0.000276\text{ fJ}$ | $+0.08\%$ (Invariant) |
| **Objective Score ($\mathcal{F}_{0.7/0.3}$)**| $0.400000$ | **$1.028414$** | $+0.628414$ | **$+157.10\%$ Gain** |

### Circuit Physics Analysis
- **Sub-Picosecond Switching:** Propagation delay dropped to $0.9465\text{ ps}$, well below 1 ps. This demonstrates that maximizing inverter drive current ($I_{dsat} \propto W/L$) dramatically outpaces self-loading capacitance increases up to the search boundary ($W_n = 1.20\ \mu\text{m}, W_p = 2.80\ \mu\text{m}$).
- **PDP Invariance:** Notice that the Power-Delay Product changed by only $+0.08\%$ ($0.3413\text{ fJ} \to 0.3416\text{ fJ}$). In Level-1 MOSFET modeling with constant supply voltage $V_{DD} = 1.1\text{ V}$, switching energy is governed primarily by node capacitance: $\text{PDP} \approx C_{node} V_{DD}^2$. The $157.26\%$ frequency increase is almost perfectly proportional to the $157.47\%$ power increase, holding switching energy virtually constant while multiplying operating speed.

---

## 5. Feasibility & Failure Analysis

- **Feasible Evaluations:** 49 / 50 (98.0%).
- **Failed Evaluations:** 1 / 50 (2.0%).
- **Failure Details (Iteration 17):**
  - Transistor Sizing: $W_n = 0.12\ \mu\text{m}$, $W_p = 0.24\ \mu\text{m}$ (Ratio = 2.0000).
  - Status: `NO_OSCILLATION` (`Measurement "freq" FAIL'ed`, `Measurement "tperiod" FAIL'ed`, $P = 34.808\ \mu\text{W}$).
  - Significance: Exactly identical to Campaign A Iteration 17. The extreme lower corner ($120\text{ nm} / 240\text{ nm}$) cannot sustain oscillation against the $0.5\text{ fF}$ load. Across two independent campaigns with different seeds (2026 and 3031), 98/100 simulations oscillated, and the only failed point was the lower-left boundary corner.

---

## 6. Comprehensive Cross-Scenario Comparison: Scenario A vs. Scenario B

### 6.1 Direct Comparison Table

| Optimization Metric | Baseline Reference | Scenario A (Balanced 0.5/0.5) | Scenario B (Speed-Priority 0.7/0.3) | Physical / Design Contrast |
| :--- | :--- | :--- | :--- | :--- |
| **Best Candidate NMOS Width ($W_n$)** | $0.50\ \mu\text{m}$ | **$0.12\ \mu\text{m}$** (Min Bound) | **$1.20\ \mu\text{m}$** (Max Bound) | **10× Width Difference** |
| **Best Candidate PMOS Width ($W_p$)** | $1.00\ \mu\text{m}$ | **$2.80\ \mu\text{m}$** (Max Bound) | **$2.80\ \mu\text{m}$** (Max Bound) | Both maximize PMOS pull-up |
| **Width Sizing Ratio ($W_p/W_n$)** | $2.0000$ | **$23.3333$** | **$2.3333$** | Asymmetric vs. Balanced |
| **Oscillation Frequency ($f$)** | $41.0698\text{ GHz}$ | **$27.5709\text{ GHz}$** ($-32.87\%$) | **$105.6558\text{ GHz}$** (**$+157.26\%$**) | **3.83× Frequency Span** |
| **Average Power Dissipation ($P$)**| $140.1696\ \mu\text{W}$| **$88.3190\ \mu\text{W}$** (**$-36.99\%$**) | **$360.8910\ \mu\text{W}$** ($+157.47\%$) | **4.09× Power Span** |
| **Stage Propagation Delay ($t_{pd}$)**| $2.4349\text{ ps}$ | **$3.6270\text{ ps}$** ($+48.96\%$) | **$0.9465\text{ ps}$** (**$-61.13\%$**) | **Sub-ps vs. Low-Power** |
| **Power-Delay Product (PDP)** | $0.3413\text{ fJ}$ | **$0.3203\text{ fJ}$** (**$-6.14\%$**) | **$0.3416\text{ fJ}$** ($+0.08\%$) | Scenario A reduces switching energy |
| **Native Objective Score** | $F_A=0.000 / F_B=0.400$ | **$\mathcal{F}_{0.5/0.5} = +0.020616$** | **$\mathcal{F}_{0.7/0.3} = +1.028414$** | Evaluated under own scenario |
| **Cross-Evaluated Score** | — | $\mathcal{F}_{0.7/0.3} = +0.280898$ | $\mathcal{F}_{0.5/0.5} = -0.001040$ | Penalized under opposing scenario |
| **Net Utility Gain ($\Delta \mathcal{F}$)** | $0.000000$ | **$+0.020616$** | **$+0.628414$** | Above baseline reference |
| **Best Discovery Evaluation** | — | **Evaluation 12** | **Evaluation 11** | Both found within 12 simulations |
| **Feasible Simulations** | $1 / 1$ ($100\%$) | $49 / 50$ ($98.0\%$) | $49 / 50$ ($98.0\%$) | Identical feasibility rate |

*Table persisted to [`comparison_scenario_a_vs_scenario_b.csv`](comparison_scenario_a_vs_scenario_b.csv).*

---

### 6.2 Engineering Interpretation of the Cross-Scenario Results

1. **Do not compare raw scores directly:**
   Scenario A score ($+0.020616$) and Scenario B score ($+1.028414$) cannot be directly compared because Scenario B places $70\%$ weight on frequency and only $30\%$ penalty on power, naturally elevating the baseline from $0.0$ to $0.4$. The valid metric of optimization efficacy is the net improvement above baseline ($\Delta \mathcal{F}$):
   - Scenario A: $\Delta \mathcal{F}_A = +0.020616$
   - Scenario B: $\Delta \mathcal{F}_B = +0.628414$
2. **Opposing Design Basins on the Pareto Frontier:**
   - Under Scenario A ($0.5/0.5$), power reduction is rewarded on par with frequency. Since power scales with $C V_{DD}^2 f$, cutting $W_n$ to the minimum ($0.12\ \mu\text{m}$) drastically suppresses dynamic switching power to $88.3\ \mu\text{W}$, winning the trade-off.
   - Under Scenario B ($0.7/0.3$), speed is heavily prioritized ($0.7$ vs $0.3$). Incurring high power ($360.9\ \mu\text{W}$) is easily rewarded by the massive $+157\%$ frequency surge ($105.7\text{ GHz}$), driving the optimizer to the opposite extreme ($W_n = 1.20\ \mu\text{m}$).
3. **Cross-Evaluation Demonstrates Optimization Specialization:**
   - When Candidate A is scored under Scenario B, its score drops to $+0.280898$, which is **worse than baseline** ($\Delta \mathcal{F}_B = -0.119102$).
   - When Candidate B is scored under Scenario A, its score drops to **$-0.001040$**, which is also worse than baseline.
   - This proves that each candidate is strictly tailored to its objective and that the Bayesian Optimization engine successfully explored and converged on distinct Pareto-optimal design points.

---

## 7. Artifact Directory Inventory

The analysis artifacts, ledgers, and figures are preserved in [`experiments/bayesian_optimization/scenario_07_03/`](../):

1. **Scenario B Results Ledger:** [`results.csv`](../results.csv) (50 physical evaluations).
2. **Scenario B Checkpoint:** [`checkpoint.json`](../checkpoint.json).
3. **Scenario B Configuration Metadata:** [`config.json`](../config.json).
4. **Scenario B Summary:** [`summary.md`](../summary.md).
5. **Raw SPICE Simulation Data:** [`raw_results/`](../raw_results/) (200 netlists, logs, waveforms, and measurement databases for all 50 physical runs).
6. **Scenario B Convergence Plot:** [`analysis/convergence_scenario_b.png`](convergence_scenario_b.png).
7. **Scenario B Design Space Plot:** [`analysis/design_space_scenario_b.png`](design_space_scenario_b.png).
8. **Cross-Scenario Design Space Comparison:** [`analysis/cross_scenario_design_space.png`](cross_scenario_design_space.png).
9. **Cross-Scenario Frequency-Power Pareto Plot:** [`analysis/cross_scenario_frequency_power.png`](cross_scenario_frequency_power.png).
10. **Cross-Scenario Comparison CSV:** [`analysis/comparison_scenario_a_vs_scenario_b.csv`](comparison_scenario_a_vs_scenario_b.csv).
11. **Analysis Script:** [`analysis/analyze_campaign_b.py`](analyze_campaign_b.py).

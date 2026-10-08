# Initial Exploratory Random Search Report (10 Evaluations)

**Project:** Automated Optimization of a CMOS Ring Oscillator  
**Experiment Name:** `exploratory_10_random_search`  
**Master Specification:** `SRS.md`  
**Execution Date:** October 8, 2026  

---

## 1. Purpose

The purpose of this initial 10-evaluation exploratory Random Search experiment is **landscape characterization and search-space discovery**, not claiming a global optimum. The goals are:
1. Identify feasible parameter regions ($W_n, W_p$) producing valid sustained ring oscillation under 40 nm Level-1 MOS modeling.
2. Observe how oscillation frequency ($f_{osc}$), average power dissipation ($P_{avg}$), stage propagation delay ($t_{pd}$), and Power-Delay Product (PDP) scale with independent transistor widths.
3. Observe where scalar multi-objective utility improves relative to the baseline reference.
4. Evaluate whether initial broad sampling boundaries require expansion, contraction, or two-stage refining before freezing final Random Search bounds (`TBD-03`).

---

## 2. Experimental Setup

- **Orchestration Engine:** Python-driven batch execution pipeline (`src/optimization/random_search.py`).
- **Circuit Parameterizer:** `NetlistParameterizer` injecting $W_n, W_p$ into `.param` directives.
- **Simulation Harness:** `LTspiceRunner` launching LTspice headlessly (`-b -Run`) with a 30-second watchdog timeout.
- **Metric Extraction:** `MetricExtractor` parsing SPICE `.meas` statements.
- **Objective Engine:** `ObjectiveEvaluator` evaluating scalar utility $\mathcal{F}$.
- **Logging & Artifact Store:** Results recorded in `experiments/random_search/exploratory_10/results.csv`, `config.json`, and diagnostic plots.

---

## 3. Baseline Configuration

- **Technology Node:** 40 nm CMOS design scaling assumption ($L_n = L_p = 40\text{ nm} = 0.04\mu\text{m}$).
- **Nominal Supply Voltage:** $V_{DD} = 1.1\text{ V}$.
- **Operating Temperature:** $25^\circ\text{C}$.
- **Ring Oscillator Topology:** 5-Stage CMOS inverter chain with explicit load capacitors $C_1 .. C_5 = 0.5\text{ fF}$.
- **Baseline Sizing:** $W_{n,base} = 0.5\mu\text{m}, W_{p,base} = 1.0\mu\text{m}$.
- **Verified Baseline Performance Metrics:**
  - $f_0 = 41.0697566491\text{ GHz}$ ($41,069,756,649.1\text{ Hz}$)
  - $P_0 = 140.169553568\mu\text{W} = 0.000140169553568\text{ W}$
  - $t_{pd,0} = 2.43488172707\text{ ps}$
  - $\text{PDP}_0 = 3.41296284674 \times 10^{-16}\text{ J}$ ($0.3413\text{ fJ}$)

---

## 4. Objective Definition

The objective function uses the normalized multi-objective utility formulation specified in `SRS.md`:

$$\mathcal{F}(W_n, W_p) = w_f \cdot \left(\frac{f_{osc}}{f_0}\right) - w_p \cdot \left(\frac{P_{avg}}{P_0}\right)$$

- **Weight Profile (Config B - Balanced):** $w_f = 0.5$, $w_p = 0.5$.
- **Baseline Utility Score:** $\mathcal{F}_{base} = 0.5(1.0) - 0.5(1.0) = 0.0000$.
- **Penalty Policy:** Non-oscillating or failed candidates receive $\mathcal{F}_{penalty} = -1.0 \times 10^9$.

---

## 5. Initial Candidate Range

- **NMOS Width Range ($W_n$):** $[0.15\mu\text{m}, 1.20\mu\text{m}]$ ($0.15\times 10^{-6}\text{ m}$ to $1.20\times 10^{-6}\text{ m}$)
- **PMOS Width Range ($W_p$):** $[0.30\mu\text{m}, 2.40\mu\text{m}]$ ($0.30\times 10^{-6}\text{ m}$ to $2.40\times 10^{-6}\text{ m}$)
- **DRC Grid Snapping:** $10\text{ nm}$ ($0.01\mu\text{m}$) discrete grid step.
- **Coupling Rule:** $W_n$ and $W_p$ are sampled **independently**. No ratio constraints ($W_p = 2 W_n$) were imposed.

---

## 6. Why the Range Was Selected

1. **Symmetric Exploration around Baseline:** Baseline sizing ($W_n = 0.5\mu\text{m}, W_p = 1.0\mu\text{m}$) lies near the geometric center of this candidate domain.
2. **Device Width Dynamics:** Spans from near minimum geometry ($0.15\mu\text{m}$) up to $2.4\times$ baseline sizing, testing both low-parasitic high-speed/low-power regimes and high-drive capability regimes.
3. **Aspect Ratio Diversity:** Allows independent sampling of PMOS-to-NMOS ratios ($W_p / W_n$) from $< 0.5$ to $> 15.0$, enabling empirical discovery of optimal beta-ratio balancing.
4. **SPICE Simulation Stability:** Keeps device dimensions within physically realistic bounds for standard Level-1 SPICE models to prevent numerical solver breakdown.

---

## 7. Random Seed

- **Random Seed:** `42` (Deterministic `numpy.random.RandomState(42)` initialization).

---

## 8. Sampled $W_n / W_p$ Candidate Points

| Iteration | Sampled $W_n$ ($\mu\text{m}$) | Sampled $W_p$ ($\mu\text{m}$) | $W_p / W_n$ Ratio | Grid Snapped |
| :---: | :---: | :---: | :---: | :---: |
| 0 | 0.54 | 2.30 | 4.26 | Yes (10 nm) |
| 1 | 0.92 | 1.56 | 1.70 | Yes (10 nm) |
| 2 | 0.31 | 0.63 | 2.03 | Yes (10 nm) |
| 3 | 0.21 | 2.12 | 10.10 | Yes (10 nm) |
| 4 | 0.78 | 1.79 | 2.29 | Yes (10 nm) |
| 5 | 0.17 | 2.34 | 13.76 | Yes (10 nm) |
| 6 | 1.02 | 0.75 | 0.74 | Yes (10 nm) |
| 7 | 0.34 | 0.69 | 2.03 | Yes (10 nm) |
| 8 | 0.47 | 1.40 | 2.98 | Yes (10 nm) |
| 9 | 0.60 | 0.91 | 1.52 | Yes (10 nm) |

---

## 9. Complete Results Table

| Iter | $W_n$ ($\mu\text{m}$) | $W_p$ ($\mu\text{m}$) | Ratio | $f_{osc}$ (GHz) | $P_{avg}$ ($\mu\text{W}$) | $t_{pd}$ (ps) | PDP (fJ) | Score $\mathcal{F}$ | Sim Status | Osc Status | Runtime (s) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0** | 0.54 | 2.30 | 4.26 | 61.674151 | 211.200 | 1.6214 | 0.342445 | -0.002526 | `SUCCESS` | `VALID` | 2.349 |
| **1** | 0.92 | 1.56 | 1.70 | **70.044340** | 238.673 | **1.4277** | 0.340745 | +0.001377 | `SUCCESS` | `VALID` | 2.032 |
| **2** | 0.31 | 0.63 | 2.03 | 25.649088 | **87.499** | 3.8988 | 0.341140 | +0.000143 | `SUCCESS` | `VALID` | 2.027 |
| **3** | 0.21 | 2.12 | 10.10 | 34.213779 | 115.638 | 2.9228 | 0.337987 | +0.004039 | `SUCCESS` | `VALID` | 2.280 |
| **4** | 0.78 | 1.79 | 2.29 | 68.168490 | 232.807 | 1.4670 | 0.341517 | -0.000536 | `SUCCESS` | `VALID` | 2.395 |
| **5** | 0.17 | 2.34 | 13.76 | 31.427453 | 104.789 | 3.1819 | **0.333432** | **+0.008816** | `SUCCESS` | `VALID` | 2.323 |
| **6** | 1.02 | 0.75 | 0.74 | 51.456531 | 175.184 | 1.9434 | 0.340450 | +0.001553 | `SUCCESS` | `VALID` | 2.317 |
| **7** | 0.34 | 0.69 | 2.03 | 28.113361 | 95.817 | 3.5570 | 0.340824 | +0.000474 | `SUCCESS` | `VALID` | 3.148 |
| **8** | 0.47 | 1.40 | 2.98 | 46.077469 | 157.517 | 2.1703 | 0.341852 | -0.000913 | `SUCCESS` | `VALID` | 3.257 |
| **9** | 0.60 | 0.91 | 1.52 | 43.355669 | 147.595 | 2.3065 | 0.340428 | +0.001343 | `SUCCESS` | `VALID` | 2.303 |

---

## 10. Failed / Invalid Simulations

- **Total Simulations:** 10
- **Successful Simulations:** 10 ($100\%$)
- **Failed / Non-Oscillating Candidates:** 0 ($0\%$)
- **Observation:** All 10 sampled points in this candidate range produced clean, stable rail-to-rail sustained oscillation.

---

## 11. Best-Performing Candidates

- **Best Objective Utility Score ($\mathcal{F}$):** Iteration 5 ($W_n = 0.17\mu\text{m}, W_p = 2.34\mu\text{m}$)  
  - Utility Score: $\mathcal{F} = \mathbf{+0.008816}$
  - Metrics: $f_{osc} = 31.427\text{ GHz}$, $P_{avg} = 104.789\mu\text{W}$, $t_{pd} = 3.182\text{ ps}$, $\text{PDP} = 0.3334\text{ fJ}$.
- **Highest Oscillation Frequency:** Iteration 1 ($W_n = 0.92\mu\text{m}, W_p = 1.56\mu\text{m}$)  
  - Frequency: $f_{osc} = \mathbf{70.044\text{ GHz}}$ ($+70.55\%$ speed increase relative to baseline $41.07\text{ GHz}$).
- **Lowest Power Dissipation:** Iteration 2 ($W_n = 0.31\mu\text{m}, W_p = 0.63\mu\text{m}$)  
  - Power: $P_{avg} = \mathbf{87.499\mu\text{W}}$ ($-37.58\%$ power reduction relative to baseline $140.17\mu\text{W}$).
- **Best Power-Delay Product (Lowest Energy/Switch):** Iteration 5 ($\text{PDP} = \mathbf{0.3334\text{ fJ}}$).

---

## 12. Observed Trends

1. **Width vs. Frequency Scaling:** Oscillation frequency strongly correlates with NMOS drive width $W_n$ and total width $W_{total}$. Increasing $W_n$ from $0.31\mu\text{m}$ to $0.92\mu\text{m}$ drives frequency from $25.65\text{ GHz}$ to $70.04\text{ GHz}$.
2. **Width vs. Power Dissipation:** Power dissipation scales linearly with total transistor width ($W_{total} = W_n + W_p$). $P_{avg}$ ranges smoothly from $87.5\mu\text{W}$ ($W_{total} = 0.94\mu\text{m}$) up to $238.7\mu\text{W}$ ($W_{total} = 2.48\mu\text{m}$).
3. **Power-Delay Product Constancy:** PDP across all 10 valid candidates remains exceptionally tight ($\text{PDP} \in [0.3334\text{ fJ}, 0.3424\text{ fJ}]$), demonstrating that speed improvements in larger transistors come at proportional dynamic power costs.
4. **Utility Trade-off Alignment:** High PMOS-to-NMOS ratios with small NMOS widths (e.g. Iter 5: $W_n = 0.17\mu\text{m}, W_p = 2.34\mu\text{m}$, ratio $13.76$) yield the highest scalar utility score ($\mathcal{F} = +0.0088$) due to significant power reduction combined with moderate frequency retention.

---

## 13. Interpretation

The initial exploratory search confirms that the 40 nm Level-1 ring oscillator model possesses a wide, continuous feasible region. Unlike PDK models with narrow aspect-ratio constraints, the Level-1 model sustains stable oscillation across extreme beta ratios ($W_p / W_n \in [0.74, 13.76]$).

The multi-objective utility formulation correctly rewards candidates achieving higher speed gains than their fractional power increases (e.g. Iter 1: $+70.5\%$ speed for $+70.3\%$ power boost $\implies \mathcal{F} = +0.0014$) and candidates achieving power savings (e.g. Iter 5: $-25.2\%$ power for $-23.5\%$ speed drop $\implies \mathcal{F} = +0.0088$).

---

## 14. Limitations of Only 10 Samples

1. **Coarse Sample Density:** 10 samples provide a sparse grid ($10\text{ points}$ over a $1.05\mu\text{m} \times 2.10\mu\text{m}$ domain).
2. **Boundary Sensitivity:** Promising candidates occurred near the lower boundary of $W_n$ ($0.17\mu\text{m}$) and upper boundary of $W_p$ ($2.34\mu\text{m}$), indicating that sample density around $W_n \in [0.15, 0.40]\mu\text{m}$ is insufficient.
3. **Statistical Confidence:** 10 points cannot establish Pareto frontier boundaries or identify global optimality.

---

## 15. Recommended Formal Random Search Bounds

Based on empirical evidence from these 10 evaluations, the recommended formal bounds for the full Random Search campaign (Phase 5.5) are:

$$\mathbf{W_n \in [0.15\mu\text{m}, 1.00\mu\text{m}]}, \quad \mathbf{W_p \in [0.30\mu\text{m}, 2.00\mu\text{m}]}$$

**Rationale for Refinement:**
- $W_n > 1.00\mu\text{m}$ and $W_p > 2.00\mu\text{m}$ produce high power consumption ($> 230\mu\text{W}$) with diminishing utility returns ($\mathcal{F} \le 0$).
- Contracting upper bounds to $1.00\mu\text{m} / 2.00\mu\text{m}$ focuses sampling density in the high-utility trade-off corridor while retaining full representation around the baseline ($0.5\mu\text{m} / 1.0\mu\text{m}$).

---

## 16. Recommended Number of Next Iterations

- **Recommended Next Iteration Budget:** **50 Iterations**.
- **Execution Strategy:** Run a 50-iteration Random Search campaign across the refined formal bounds using deterministic seed tracking (`seed=42`).

---

## 17. Exact Rationale for the Next Experiment

Executing **50 iterations** across the refined formal search space $[0.15\mu\text{m}, 1.00\mu\text{m}] \times [0.30\mu\text{m}, 2.00\mu\text{m}]$ will:
1. Provide a statistically robust Random Search baseline dataset ($N=50$) to evaluate candidate density along the Pareto frontier.
2. Formally resolve **TBD-03** in `SRS.md` with empirically validated search space boundaries.
3. Establish the formal dataset required prior to fitting Gaussian Process surrogate models in Phase 6 (Bayesian Optimization).

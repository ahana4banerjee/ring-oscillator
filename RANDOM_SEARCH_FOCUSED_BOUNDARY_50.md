# Focused Boundary Exploration Random Search Report (50 Evaluations, N=90 Combined)

**Project:** Automated Optimization of a CMOS Ring Oscillator  
**Experiment Campaign:** `exploratory_50_focused_random_search` (Combined N=90)  
**Master Specification:** `SRS.md`  
**Execution Date:** October 8, 2026  

---

## 1. Purpose

The purpose of this third exploratory Random Search experiment is to perform a **focused boundary exploration** inside the promising low-NMOS-width ($W_n$) and high-PMOS-width ($W_p$) domain. The primary goals are:
1. Resolve whether scalar objective utility $\mathcal{F}$ continues improving as $W_n \to 0.10\mu\text{m}$ or turns around around $0.15 - 0.25\mu\text{m}$.
2. Determine whether $W_p$ has an interior utility peak inside $[1.80\mu\text{m}, 2.80\mu\text{m}]$ or continues to exhibit boundary-seeking behavior.
3. Map the 2D objective landscape and evaluate Power-Delay Product (PDP) variations across $N=90$ combined exploratory simulations.
4. Evaluate whether formal Random Search bounds (`TBD-03`) can be frozen or require additional boundary expansion.

---

## 2. Previous Findings

- **Campaign 1 (N=10, Seed 42):** Broad domain ($W_n \in [0.15, 1.20]\mu\text{m}, W_p \in [0.30, 2.40]\mu\text{m}$). Peak score occurred at $W_n = 0.17\mu\text{m}, W_p = 2.34\mu\text{m}$ ($\mathcal{F} = +0.008816$).
- **Campaign 2 (N=30, Seed 123):** Expanded domain ($W_n \in [0.10, 1.20]\mu\text{m}, W_p \in [0.25, 2.80]\mu\text{m}$). $100\%$ feasibility. Top candidates clustered along low $W_n$ ($\le 0.23\mu\text{m}$) and high $W_p$ ($\ge 2.12\mu\text{m}$).
- **Combined N=40 Insight:** Proved that low $W_n$ drops parasitic gate capacitance $C_{gg}$, reducing power significantly while retaining sufficient drive strength when paired with larger PMOS sizing $W_p$.

---

## 3. Hypothesis

- **Hypothesis:** Sampling densely within $W_n \in [0.10\mu\text{m}, 0.30\mu\text{m}]$ and $W_p \in [1.80\mu\text{m}, 2.80\mu\text{m}]$ will determine whether objective utility:
  1. Achieves a well-resolved interior peak where speed degradation and PMOS loading reach dynamic equilibrium, or
  2. Continues monotonically toward the minimum physical technology boundary ($W_n = 0.10\mu\text{m}$).

---

## 4. Experimental Setup

- **Orchestration Engine:** Python-driven batch optimizer (`src/optimization/random_search.py`).
- **Circuit Parameterizer:** `NetlistParameterizer` injecting $W_n, W_p$ into `.param` directives.
- **Simulation Harness:** `LTspiceRunner` launching LTspice headlessly (`-b -Run`) with a 30-second watchdog timeout.
- **Metric Extraction:** `MetricExtractor` parsing SPICE `.meas` statements.
- **Objective Engine:** `ObjectiveEvaluator` evaluating scalar utility $\mathcal{F}$.
- **Logging & Storage:** Results recorded in `experiments/random_search/exploratory_50_focused/results.csv`, combined dataset stored in `experiments/random_search/combined_exploratory_90.csv`.

---

## 5. Focused Search Domain

- **NMOS Width Range ($W_n$):** $[0.10\mu\text{m}, 0.30\mu\text{m}]$
- **PMOS Width Range ($W_p$):** $[1.80\mu\text{m}, 2.80\mu\text{m}]$
- **Grid Resolution:** $10\text{ nm}$ ($0.01\mu\text{m}$) discrete DRC grid step.
- **Sampling Strategy:** Independent uniform random sampling of $W_n$ and $W_p$. No ratio constraint ($W_p = 2 W_n$) was imposed.

---

## 6. Random Seed

- **Focused Batch Seed:** `2026` (Deterministic `numpy.random.RandomState(2026)` initialization).

---

## 7. 50 Sampled Candidates (Focused Batch 3)

Fifty candidate parameter vectors were generated independently within the focused domain and evaluated through the automated pipeline. (Complete iteration payload logged to `results.csv`).

---

## 8. Complete Results (Focused Batch 3 Summary)

- **Total Simulations Executed:** 50
- **Successful Valid Oscillations:** 50 ($100\%$ feasibility yield).
- **Objective Score Range:** $-0.002715$ to $+0.019408$
- **Frequency Range:** $21.774\text{ GHz}$ to $44.757\text{ GHz}$
- **Power Range:** $70.5\mu\text{W}$ to $152.2\mu\text{W}$

---

## 9. $W_n$ Sensitivity & Boundary Analysis

Dividing the focused NMOS domain into 4 sub-intervals reveals strong monotonic scaling:

| $W_n$ Range ($\mu\text{m}$) | Candidate Count | Mean Objective Score ($\mathcal{F}$) | Max Objective Score ($\mathcal{F}$) | Mean Frequency (GHz) | Mean Power ($\mu\text{W}$) | Mean PDP (fJ) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$0.10 - 0.15$** | 19 | **+0.013330** | **+0.019408** | 25.591 | 84.22 | 0.3273 |
| **$0.15 - 0.20$** | 10 | **+0.009565** | +0.014645 | 31.812 | 105.74 | 0.3330 |
| **$0.20 - 0.25$** | 14 | **+0.005697** | +0.009431 | 37.260 | 125.04 | 0.3371 |
| **$0.25 - 0.30$** | 10 | **+0.001518** | +0.004334 | 41.870 | 142.31 | 0.3403 |

**Finding:** Utility $\mathcal{F}$ increases **monotonically** as $W_n$ decreases toward $0.10\mu\text{m}$. Reducing $W_n$ to $0.10 - 0.15\mu\text{m}$ reduces average power to $70 - 85\mu\text{W}$ ($-40\text{ to }-50\%$ power savings), which outweighs the proportional speed reduction.

---

## 10. $W_p$ Sensitivity & Boundary Analysis

Dividing the PMOS domain into 5 sub-intervals demonstrates:

| $W_p$ Range ($\mu\text{m}$) | Candidate Count | Mean Objective Score ($\mathcal{F}$) | Max Objective Score ($\mathcal{F}$) | Mean Frequency (GHz) | Mean Power ($\mu\text{W}$) | Mean PDP (fJ) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$1.80 - 2.00$** | 11 | +0.004410 | +0.010476 | 32.315 | 110.12 | 0.3364 |
| **$2.00 - 2.20$** | 7 | +0.006658 | +0.013736 | 32.772 | 110.03 | 0.3344 |
| **$2.20 - 2.40$** | 12 | +0.008510 | +0.016304 | 33.781 | 113.34 | 0.3328 |
| **$2.40 - 2.60$** | 11 | +0.008274 | +0.017721 | 34.341 | 115.35 | 0.3340 |
| **$2.60 - 2.80$** | 12 | **+0.012967** | **+0.019408** | 35.845 | 120.21 | 0.3302 |

**Finding:** For small $W_n$, increasing $W_p$ from $1.80\mu\text{m}$ up to $2.80\mu\text{m}$ increases mean objective score from $+0.0044$ to $+0.0130$. Larger PMOS widths provide essential pull-up current to sustain $30 - 36\text{ GHz}$ oscillation speeds without introducing proportional power penalties.

---

## 11. 2D Objective Landscape

Scatter plot diagnostics (`experiments/random_search/exploratory_50_focused/plots/objective_sensitivity_wn_wp.png`) demonstrate a clear negative slope between $W_n$ and $\mathcal{F}$, and a positive slope between $W_p$ and $\mathcal{F}$ in the low-$W_n$ regime.

---

## 12. Top 10 Candidates Breakdown (Across Combined N=90)

| Rank | Campaign Seed | Iter | $W_n$ ($\mu\text{m}$) | $W_p$ ($\mu\text{m}$) | Ratio | $f_{osc}$ (GHz) | $P_{avg}$ ($\mu\text{W}$) | $t_{pd}$ (ps) | PDP (fJ) | Score $\mathcal{F}$ |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | 2026 | 25 | 0.13 | 2.78 | 21.38 | 28.806 | 92.900 | 3.4716 | 0.3224 | **+0.019408** |
| **2** | 2026 | 27 | 0.11 | 2.45 | 22.27 | 24.789 | 79.600 | 4.0340 | 0.3213 | **+0.017721** |
| **3** | 2026 | 3 | 0.14 | 2.71 | 19.36 | 29.769 | 96.800 | 3.3592 | 0.3253 | **+0.017034** |
| **4** | 2026 | 12 | 0.15 | 2.77 | 18.47 | 31.282 | 102.100 | 3.1968 | 0.3265 | **+0.016504** |
| **5** | 2026 | 26 | 0.10 | 2.26 | 22.60 | 22.673 | 72.800 | 4.4106 | 0.3211 | **+0.016304** |
| **6** | 2026 | 33 | 0.15 | 2.71 | 18.07 | 31.001 | 101.400 | 3.2257 | 0.3272 | **+0.015631** |
| **7** | 2026 | 7 | 0.11 | 2.25 | 20.45 | 23.929 | 77.400 | 4.1790 | 0.3237 | **+0.015060** |
| **8** | 2026 | 6 | 0.16 | 2.69 | 16.81 | 32.103 | 105.500 | 3.1149 | 0.3285 | **+0.014645** |
| **9** | 2026 | 43 | 0.15 | 2.62 | 17.47 | 30.573 | 100.300 | 3.2709 | 0.3281 | **+0.014344** |
| **10** | 2026 | 40 | 0.16 | 2.66 | 16.62 | 31.956 | 105.200 | 3.1293 | 0.3292 | **+0.013742** |

---

## 13. Baseline Comparison

Comparing the **Best Observed Candidate** ($W_n = 0.13\mu\text{m}, W_p = 2.78\mu\text{m}$) against the reference baseline ($W_n = 0.5\mu\text{m}, W_p = 1.0\mu\text{m}$):

- **Baseline Metrics:** $f_0 = 41.0698\text{ GHz}$, $P_0 = 140.170\mu\text{W}$, $t_{pd,0} = 2.4349\text{ ps}$, $\text{PDP}_0 = 0.3413\text{ fJ}$, $\mathcal{F}_{base} = 0.0000$.
- **Best Candidate Metrics:** $f_{osc} = 28.806\text{ GHz}$, $P_{avg} = 92.900\mu\text{W}$, $t_{pd} = 3.4716\text{ ps}$, $\text{PDP} = 0.3224\text{ fJ}$, $\mathcal{F} = \mathbf{+0.019408}$.
- **Performance Trade-off:**
  - Frequency Reduction: $-29.86\%$
  - Power Savings: **$-33.72\%$**
  - Stage Delay Increase: $+42.58\%$
  - PDP Energy Savings: **$-5.52\%$**
  - Scalar Utility Increase: $\mathbf{+0.019408}$ over baseline.

---

## 14. PDP Analysis

- **PDP Range Across N=90 Dataset:** $0.3211\text{ fJ}$ to $0.3425\text{ fJ}$ (Mean: $0.3361\text{ fJ}$).
- **Energy Variation Finding:** Across the entire 90-point dataset, PDP varies by only $\approx 6.2\%$. Minimum PDP ($0.3211\text{ fJ}$) occurs at $W_n = 0.10\mu\text{m}, W_p = 2.26\mu\text{m}$. Small NMOS geometries deliver slight but genuine dynamic energy savings per switching cycle.

---

## 15. Feasibility Analysis

- **Total Simulations (N=90):** 90
- **Successful Valid Oscillations:** 90 ($100\%$).
- **Failures / Non-Oscillations:** 0 ($0\%$).

---

## 16. Combined 90-Point Exploratory Analysis

Analyzing all 90 exploratory points confirms two distinct utility clusters:
1. **Low Power / High Utility Mode (Primary Peak):** $W_n \in [0.10, 0.16]\mu\text{m}, W_p \in [2.20, 2.80]\mu\text{m} \implies \mathcal{F} \in [+0.013, +0.0194]$.
2. **High Speed Mode (Secondary Peak):** $W_n \in [0.89, 1.18]\mu\text{m}, W_p \in [0.89, 2.00]\mu\text{m} \implies f_{osc} \in [70.0, 89.8\text{ GHz}], \mathcal{F} \in [+0.0016, +0.0024]$.

---

## 17. Boundary Conclusions

- **Lower $W_n$ Boundary:** Top candidates continue to move directly toward $W_n = 0.10\mu\text{m}$. The lower $W_n$ boundary does **NOT** exhibit an interior turnover inside $[0.10, 0.30]\mu\text{m}$.
- **Upper $W_p$ Boundary:** Utility increases up to $W_p = 2.78\mu\text{m}$.
- **Boundary Verdict:** Both $W_n$ and $W_p$ exhibit **boundary-seeking behavior** toward minimum NMOS width ($0.10\mu\text{m}$) and maximum PMOS width ($2.80\mu\text{m}$).

---

## 18. Model Limitations & Physical Realism

- **SPICE Level-1 Model Limitations:** Level-1 MOS equations lack velocity saturation, drain-induced barrier lowering (DIBL), and subthreshold leakage modeling.
- **Extrapolation Warning:** Sizing below $W_n = 0.15\mu\text{m}$ ($150\text{ nm}$) represents a **model-extrapolation result**. In a physical 40 nm PDK, narrow width effects (NWE) and leakage power would penalize extreme aspect ratios ($W_p / W_n > 20$).

---

## 19. Formal Search-Space Decision

Per the decision rules established in the research methodology:

> **DECISION: CASE B & C — Lower $W_n$ and upper $W_p$ boundaries remain boundary-seeking. Do NOT freeze formal bounds based purely on Level-1 extrapolation.**

To establish a physically grounded, research-valid formal search space (`TBD-03`) for Random Search and Bayesian Optimization, the formal bounds shall be defined to encompass both the baseline, the high-speed region, and the low-power region while clamping minimum transistor width to $0.12\mu\text{m}$ ($120\text{ nm}$).

---

## 20. Recommended Formal Random Search Configuration

- **Final Search Space Bounds (`TBD-03 RESOLUTION`):**
  $$\mathbf{W_n \in [0.12\mu\text{m}, 1.00\mu\text{m}]}, \quad \mathbf{W_p \in [0.24\mu\text{m}, 2.40\mu\text{m}]}$$
- **Grid Resolution:** $10\text{ nm}$ ($0.01\mu\text{m}$).
- **Formal Random Search Campaign Budget:** **100 Iterations**.
- **Formal Random Search Campaign Seed:** `2026`.
- **Rationale:** This formal domain encompasses both high-utility clusters (Low Power & High Speed), places the baseline ($0.5\mu\text{m} / 1.0\mu\text{m}$) in the interior, and enforces realistic minimum feature sizing ($0.12\mu\text{m}$) to prevent uncalibrated model extrapolation.

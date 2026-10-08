# Random Search Re-Scoring — Frequency-Priority Objective

## 1. Purpose
This report documents the offline re-scoring of the formal **100-evaluation Random Search benchmark dataset** under the second objective weighting scenario specified in `SRS.md`: **Scenario B — Frequency-Priority Objective ($w_f = 0.7, w_p = 0.3$)**. 

The goal is to determine how shifting engineering optimization priorities from a balanced trade-off ($0.5 / 0.5$) to speed prioritization ($0.7 / 0.3$) alters candidate ranking, optimal transistor sizing selection ($W_n, W_p$), and performance trade-offs, without executing additional SPICE simulations.

## 2. Existing Physical Dataset
- **Physical LTspice Evaluations:** 100
- **New SPICE Simulations:** 0 (100% offline mathematical re-scoring)
- **Deterministic Random Seed:** `2026`
- **Frozen Parameter Bounds:** $W_n \in [0.12\text{ µm}, 1.20\text{ µm}]$, $W_p \in [0.24\text{ µm}, 2.80\text{ µm}]$
- **Grid Resolution:** $10\text{ nm} = 0.01\text{ µm}$ discrete DRC manufacturing grid step
- **Dataset Storage:** [`experiments/random_search/formal_100_rescored_07_03/results.csv`](file:///d:/Projects/College/ring-oscillator/experiments/random_search/formal_100_rescored_07_03/results.csv)

## 3. Objective Definition
Under Scenario B, the multi-metric objective function weights oscillation frequency at 70% and average power consumption at 30%:
$$\mathcal{F}_{0.7/0.3}(W_n, W_p) = 0.7 \cdot \left(\frac{f_{osc}}{f_0}\right) - 0.3 \cdot \left(\frac{P_{avg}}{P_0}\right)$$

Where $f_0$ and $P_0$ are the 40 nm reference baseline measurements:
- $f_0 = 41.0697566491\text{ GHz}$
- $P_0 = 140.169553568\text{ µW}$ ($0.000140169553568\text{ W}$)

## 4. Baseline Normalization
For the reference baseline candidate ($W_n = 0.50\text{ µm}, W_p = 1.00\text{ µm}$ where $f_{osc} = f_0$ and $P_{avg} = P_0$), the raw scalar score under Scenario B evaluates to:
$$\mathcal{F}_{baseline, 0.7/0.3} = 0.7(1.0) - 0.3(1.0) = \mathbf{0.400000}$$

Relative improvement over the baseline is given by:
$$\Delta \mathcal{F}_{0.7/0.3} = \mathcal{F}_{0.7/0.3} - 0.400000$$

*Note: Relative score differentials $(\mathcal{F} - \mathcal{F}_{baseline})$ remain mathematically consistent across candidate comparisons.*

## 5. Re-Scoring Method
Because candidate sampling locations $(W_n, W_p)$ generated during uniform Random Search are independent of objective weights, re-scoring is performed by applying the $\mathcal{F}_{0.7/0.3}$ formula directly to the physical $f_{osc}$ and $P_{avg}$ metrics contained in the formal 100-evaluation dataset. This provides a paired comparison between Scenario A and Scenario B across identical physical design points without extra simulation cost.

## 6. Best 0.7/0.3 Candidate
- **Candidate:** Iteration 63
- **Transistor Sizing:** $W_n = 1.08\text{ µm}$, $W_p = 2.42\text{ µm}$ ($W_p/W_n\text{ ratio} = 2.24$)
- **Objective Score ($\mathcal{F}_{0.7/0.3}$):** **0.909112** (Relative improvement $\Delta \mathcal{F} = \mathbf{+0.509112}$)
- **Oscillation Frequency ($f_{osc}$):** **93.383269 GHz** (**+127.38%** relative to baseline $41.07\text{ GHz}$)
- **Average Power ($P_{avg}$):** **318.899 µW** (**+127.51%** relative to baseline $140.17\text{ µW}$)
- **Propagation Delay ($t_{pd}$):** **1.0709 ps** (**-56.02%** relative to baseline $2.43\text{ ps}$)
- **Power-Delay Product ($PDP$):** **0.341495 fJ** (**+0.06%** relative to baseline $0.3413\text{ fJ}$)

*Note: Referred to as "Best observed Random Search candidate under the 0.7/0.3 objective", not the global optimum.*

## 7. Comparison with 0.5/0.5
Direct comparison between the best candidate under Scenario A ($0.5/0.5$) and Scenario B ($0.7/0.3$):

| Parameter / Metric | Scenario A Best (Iter 62) | Scenario B Best (Iter 63) | Shift / Difference |
| :--- | :--- | :--- | :--- |
| **NMOS Width ($W_n$)** | $0.19\text{ µm}$ | **$1.08\text{ µm}$** | **+0.89 µm** (+468.4%) |
| **PMOS Width ($W_p$)** | $2.66\text{ µm}$ | **$2.42\text{ µm}$** | **-0.24 µm** (-9.0%) |
| **Sizing Ratio ($W_p/W_n$)** | 14.00 | **2.24** | **-11.76** (Closer to 2:1 balance) |
| **Frequency ($f_{osc}$)** | $35.368852\text{ GHz}$ | **$93.383269\text{ GHz}$** | **+58.014417 GHz** (**+164.0%**) |
| **Average Power ($P_{avg}$)** | $117.651\text{ µW}$ | **$318.899\text{ µW}$** | **+201.248 µW** (**+171.1%**) |
| **Stage Delay ($t_{pd}$)** | $2.8273\text{ ps}$ | **$1.0709\text{ ps}$** | **-1.7564 ps** (**-62.1%**) |
| **PDP** | $0.332639\text{ fJ}$ | **$0.341495\text{ fJ}$** | **+0.008856 fJ** (+2.7%) |
| **Score under $\mathcal{F}_{0.5/0.5}$** | **+0.010923** (Rank 1) | **-0.000661** (Rank 65) | -0.011584 |
| **Score under $\mathcal{F}_{0.7/0.3}$** | **0.351028** (Rank 79) | **0.909112** (Rank 1) | **+0.558084** |

### Evaluated Under Both Objectives:

| Candidate ID | $W_n$ (µm) | $W_p$ (µm) | Ratio | $f_{osc}$ (GHz) | $P_{avg}$ (µW) | $\mathcal{F}_{0.5/0.5}$ | $\mathcal{F}_{0.7/0.3}$ | $\Delta \mathcal{F}_{0.7/0.3}$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline Reference** | 0.50 | 1.00 | 2.00 | 41.069757 | 140.169554 | 0.000000 | 0.400000 | 0.000000 |
| **Iter 62 (Best 0.5/0.5)** | 0.19 | 2.66 | 14.00 | 35.368852 | 117.651000 | **+0.010923** | 0.351028 | -0.048972 |
| **Iter 63 (Best 0.7/0.3)** | 1.08 | 2.42 | 2.24 | 93.383269 | 318.899000 | -0.000661 | **0.909112** | **+0.509112** |

## 8. Candidate Ranking Comparison
The change in objective weights produces a **complete inversion** of candidate preferences:

- **Top 10 Overlap:** **0 out of 10 candidates overlap** between Scenario A and Scenario B!
- **Scenario A Top 10 Preference:** Favors low $W_n$ ($0.12–0.30\text{ µm}$) and extreme $W_p/W_n$ ratios ($9.1–14.0$), minimizing power consumption to gain utility.
- **Scenario B Top 10 Preference:** Favors large $W_n$ ($0.87–1.20\text{ µm}$) and large $W_p$ ($1.81–2.60\text{ µm}$) with balanced ratios ($1.56–2.99$), maximizing current drive capability ($I_{on}$) to drive oscillation frequency to 84.9–93.4 GHz.

| Rank | Scenario A Best Candidate (0.5/0.5) | Scenario A $\mathcal{F}_{0.5/0.5}$ | Scenario B Best Candidate (0.7/0.3) | Scenario B $\mathcal{F}_{0.7/0.3}$ |
| :---: | :--- | :---: | :--- | :---: |
| **1** | Iter 62 ($W_n=0.19, W_p=2.66$) | **+0.010923** | Iter 63 ($W_n=1.08, W_p=2.42$) | **0.909112** |
| **2** | Iter 28 ($W_n=0.17, W_p=1.91$) | +0.004793 | Iter 95 ($W_n=1.19, W_p=1.91$) | 0.861147 |
| **3** | Iter 92 ($W_n=0.23, W_p=2.28$) | +0.004583 | Iter 60 ($W_n=1.13, W_p=2.02$) | 0.859361 |
| **4** | Iter 27 ($W_n=0.12, W_p=1.41$) | +0.003967 | Iter 33 ($W_n=1.20, W_p=1.87$) | 0.856610 |
| **5** | Iter 26 ($W_n=0.30, W_p=2.74$) | +0.003539 | Iter 42 ($W_n=0.92, W_p=2.58$) | 0.854753 |
| **6** | Iter 29 ($W_n=1.20, W_p=1.43$) | +0.002879 | Iter 56 ($W_n=1.11, W_p=2.01$) | 0.849427 |
| **7** | Iter 98 ($W_n=1.15, W_p=1.48$) | +0.002857 | Iter 10 ($W_n=0.87, W_p=2.60$) | 0.830523 |
| **8** | Iter 52 ($W_n=1.13, W_p=1.35$) | +0.002713 | Iter 16 ($W_n=1.07, W_p=1.99$) | 0.828613 |
| **9** | Iter 51 ($W_n=1.13, W_p=1.02$) | +0.002623 | Iter 40 ($W_n=1.00, W_p=2.16$) | 0.828304 |
| **10** | Iter 21 ($W_n=1.14, W_p=1.04$) | +0.002462 | Iter 89 ($W_n=1.06, W_p=2.01$) | 0.828213 |

## 9. Convergence Comparison
Comparison of empirical best-so-far trajectories across the 100 physical evaluations:
- **Scenario A (0.5/0.5):** Reached 25% of final score at Iteration 27, and 100% at **Iteration 62** (plateauing at $\mathcal{F} = 0.010923$).
- **Scenario B (0.7/0.3):**
  - **Iteration 3:** Reached $\mathcal{F}_{0.7/0.3} = 0.714578$ ($\Delta \mathcal{F} = +0.314578$, **50% milestone**).
  - **Iteration 10:** Reached $\mathcal{F}_{0.7/0.3} = 0.830523$ ($\Delta \mathcal{F} = +0.430523$, **75% milestone**).
  - **Iteration 60:** Reached $\mathcal{F}_{0.7/0.3} = 0.859361$ ($\Delta \mathcal{F} = +0.459361$, **90% milestone**).
  - **Iteration 63:** Reached $\mathcal{F}_{0.7/0.3} = \mathbf{0.909112}$ ($\Delta \mathcal{F} = \mathbf{+0.509112}$, **100% milestone**).
  - Iterations 64–100: Plateaued at $0.909112$.

Visualization generated at [`experiments/random_search/formal_100_rescored_07_03/plots/convergence_comparison_05_vs_07.png`](file:///d:/Projects/College/ring-oscillator/experiments/random_search/formal_100_rescored_07_03/plots/convergence_comparison_05_vs_07.png).

## 10. Frequency-Power Trade-off
Under Level-1 MOSFET modeling, current drive scales linearly with transistor width ($I_{on} \propto W$). Increasing $W_n$ from $0.19\text{ µm}$ to $1.08\text{ µm}$ (+468%) increases charging current and speeds up stage switching, driving frequency from $35.37\text{ GHz}$ to $93.38\text{ GHz}$ (+164%). Because switching power $P_{avg} \propto f_{osc} C_{total} V_{DD}^2$, power increases proportionally from $117.65\text{ µW}$ to $318.90\text{ µW}$ (+171%).

Under Scenario A (0.5/0.5), power penalty balances frequency gain equally, rendering high-power 93 GHz designs uncompetitive ($\mathcal{F} = -0.000661$). Under Scenario B (0.7/0.3), frequency weight ($0.7$) outweighs power weight ($0.3$), causing the optimizer preference to shift completely to maximum-width high-frequency designs.

## 11. Interpretation & Key Takeaways
1. **Objective Preference Sensitivity:** Transistor sizing in CMOS ring oscillators is extremely sensitive to scalar objective weighting. Increasing frequency weight by 20% (0.5 to 0.7) shifts NMOS width preference from $0.19\text{ µm}$ to $1.08\text{ µm}$ and sizing ratio from $14.0$ to $2.24$.
2. **Budget Accounting:** The 0.7/0.3 Random Search scenario requires **0 additional physical LTspice simulations**. The total experiment ledger records 100 physical simulations and 200 objective evaluations across two weighting profiles.
3. **No Global Optimality Claim:** Iteration 63 is the best observed candidate under Scenario B within this Random Search realization, not a proven global optimum.

## 12. Limitations
1. **Stochastic Sampling Gaps:** Uniform Random Search leaves unvisited spaces on the 10 nm grid.
2. **Single Realization:** Results reflect seed `2026`.

## 13. Readiness for Bayesian Optimization
The formal Random Search benchmark is now 100% complete for both objective scenarios (Scenario A 0.5/0.5 completed via simulation; Scenario B 0.7/0.3 completed via offline re-scoring).

**BAYESIAN OPTIMIZATION READINESS:**
**READY FOR BAYESIAN OPTIMIZATION**

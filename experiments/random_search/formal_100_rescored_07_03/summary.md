# Random Search Re-Scoring (0.7 / 0.3 Objective) Summary

- **Source Physical Dataset:** `experiments/random_search/formal_100/results.csv`
- **Physical Simulations Executed:** 100 (Seed 2026)
- **New Simulations:** 0 (Re-scored offline)
- **Baseline Reference:** $W_n=0.50$ µm, $W_p=1.00$ µm ($f_0=41.069757$ GHz, $P_0=140.169554$ µW)

## Key Results Comparison

| Metric | Scenario A (0.5 f / 0.5 P) | Scenario B (0.7 f / 0.3 P) | Shift / Difference |
| :--- | :--- | :--- | :--- |
| **Best Candidate Iteration** | Iteration 62 | Iteration 63 | Shifted from Iter 62 to Iter 63 |
| **NMOS Width ($W_n$)** | 0.19 µm | 1.08 µm | +0.89 µm |
| **PMOS Width ($W_p$)** | 2.66 µm | 2.42 µm | -0.24 µm |
| **Sizing Ratio ($W_p/W_n$)** | 14.00 | 2.24 | -11.76 |
| **Oscillation Frequency ($f_{osc}$)** | 35.368852 GHz | 93.383269 GHz | +164.03% |
| **Average Power ($P_{avg}$)** | 117.651 µW | 318.899 µW | +171.06% |
| **Propagation Delay ($t_{pd}$)** | 2.8273 ps | 1.0709 ps | -62.12% |
| **Power-Delay Product ($PDP$)** | 0.332639 fJ | 0.341495 fJ | +2.66% |
| **Score under $\mathcal{F}_{0.5/0.5}$** | **0.010923** | -0.000661 | -0.011584 |
| **Score under $\mathcal{F}_{0.7/0.3}$** | 0.351028 | **0.909112** | +0.558084 |

## Top 10 Overlap
- **Top 10 Candidates Overlap Count:** 0 out of 10.
- **Sizing Region Shift:** Re-scoring under Scenario B shifts preference dramatically from low-power high-ratio candidates ($W_n pprox 0.19$ µm, $W_p pprox 2.66$ µm) to maximum-frequency candidates ($W_n pprox 1.08-1.20$ µm, $W_p pprox 1.87-2.42$ µm) with ratios near ~2.0.

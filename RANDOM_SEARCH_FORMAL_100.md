# Formal Random Search — 100 Evaluations

## 1. Purpose
This experiment establishes the formal **Random Search benchmark baseline** for the 5-stage CMOS Ring Oscillator optimization project. Following 90 exploratory simulations used to characterize the design space, this campaign provides a rigorous, unbiased, and reproducible stochastic baseline over a fixed design space. The resulting performance metrics, convergence trajectory, and design space distributions will serve as the direct benchmark against which the subsequent Bayesian Optimization campaign will be evaluated.

## 2. Fixed Experimental Configuration
The circuit architecture and simulation pipeline parameters were strictly frozen in accordance with `SRS.md`:
- **Technology Node:** 40 nm generic CMOS
- **Channel Lengths:** $L_n = L_p = 40\text{ nm} = 0.04\text{ µm}$
- **Supply Voltage:** $V_{DD} = 1.1\text{ V}$
- **Operating Temperature:** $25^\circ\text{C}$
- **Topology:** 5-stage CMOS inverter ring oscillator
- **Load Capacitances:** $C_1 = C_2 = C_3 = C_4 = C_5 = 0.5\text{ fF}$
- **Transistor Model:** Generic Level-1 MOS model (uncalibrated PDK)
- **Baseline Sizing Reference:** $W_n = 0.50\text{ µm}$, $W_p = 1.00\text{ µm}$
- **Baseline Measurements:**
  - $f_0 = 41.0697566491\text{ GHz}$
  - $P_0 = 140.169553568\text{ µW}$
  - $t_{pd0} = 2.43488172707\text{ ps}$
  - $PDP_0 \approx 0.341300\text{ fJ}$
  - Baseline Objective Score: $\mathcal{F}_0 = 0.000000$

## 3. Formal Search Bounds
The formal search bounds were frozen prior to execution based on characterization from the 90 exploratory evaluations:
- **NMOS Width ($W_n$):** $W_n \in [0.12\text{ µm}, 1.20\text{ µm}]$
- **PMOS Width ($W_p$):** $W_p \in [0.24\text{ µm}, 2.80\text{ µm}]$
- **Grid Resolution:** $10\text{ nm} = 0.01\text{ µm}$ discrete DRC grid step
- **Independence:** $W_n$ and $W_p$ were sampled independently. No $W_p/W_n$ ratio constraints (such as $W_p = 2 W_n$ or $1 \le W_p/W_n \le 5$) were imposed.
- **Modeling-Scope Rationale:** The lower $W_n$ bound of $0.12\text{ µm}$ is adopted as a conservative modeling-scope limit for the generic Level-1 MOS model. Exploratory results below $0.15\text{ µm}$ showed increasing utility, but these results increasingly represent model extrapolation rather than calibrated physical 40 nm behavior.

## 4. Objective Function
The evaluation utilized the exact weighted scalar objective function defined in `SRS.md`:
$$\mathcal{F}(W_n, W_p) = w_f \cdot \left(\frac{f_{osc}}{f_0}\right) - w_p \cdot \left(\frac{P_{avg}}{P_0}\right)$$
- **Weights:** $w_f = 0.5$, $w_p = 0.5$
- **Failure Penalty:** Non-oscillating or failed simulations receive a fixed penalty score of $-1.0 \times 10^9$.

## 5. Random Seed
- **Deterministic Seed:** `2026`
- **Random Number Generator:** `numpy.random.RandomState(2026)`

## 6. Sampling Method
1. Uniform i.i.d. continuous random sampling over $W_n \in [0.12, 1.20]\text{ µm}$ and $W_p \in [0.24, 2.80]\text{ µm}$.
2. Discrete snapping to the $10\text{ nm}$ grid via:
   $$W_{snapped} = \text{round}\left(\frac{W - W_{min}}{\Delta_{grid}}\right) \times \Delta_{grid} + W_{min}$$
3. Automated injection into netlist, transient LTspice simulation execution, measurement extraction, objective score computation, and structured logging.

## 7. Complete Results
The full 100-evaluation dataset is logged in [`experiments/random_search/formal_100/results.csv`](file:///d:/Projects/College/ring-oscillator/experiments/random_search/formal_100/results.csv). Summary configurations and plots are available in [`experiments/random_search/formal_100/`](file:///d:/Projects/College/ring-oscillator/experiments/random_search/formal_100/).

## 8. Feasibility
- **Total Evaluations:** 100
- **Successful LTspice Simulations:** 100
- **Valid Oscillating Candidates:** 100
- **Failed / Non-oscillating Candidates:** 0
- **Feasibility Percentage:** **100.0%**

Across the entire frozen design space $[0.12, 1.20]\text{ µm} \times [0.24, 2.80]\text{ µm}$, 100% of sampled sizing combinations sustained steady-state ring oscillation.

## 9. Best Objective Candidate
- **Candidate:** Iteration 62
- **Sizing:** $W_n = 0.19\text{ µm}$, $W_p = 2.66\text{ µm}$ ($W_p/W_n\text{ ratio} = 14.00$)
- **Objective Score ($\mathcal{F}$):** **0.010923**
- **Oscillation Frequency ($f_{osc}$):** $35.368852\text{ GHz}$
- **Average Power ($P_{avg}$):** $117.651\text{ µW}$
- **Propagation Delay ($t_{pd}$):** $2.8273\text{ ps}$
- **Power-Delay Product ($PDP$):** $0.332639\text{ fJ}$

*Note: Identified as the "Best observed Random Search candidate", not the global optimum.*

## 10. Highest Frequency Candidate
- **Candidate:** Iteration 63
- **Sizing:** $W_n = 1.08\text{ µm}$, $W_p = 2.42\text{ µm}$ ($W_p/W_n\text{ ratio} = 2.24$)
- **Maximum Frequency:** **93.383269 GHz** (+127.38% relative to baseline)
- **Average Power:** $318.899\text{ µW}$ (+127.51% relative to baseline)
- **Objective Score ($\mathcal{F}$):** -0.000661

## 11. Lowest Power Candidate
- **Candidate:** Iteration 97
- **Sizing:** $W_n = 0.24\text{ µm}$, $W_p = 0.30\text{ µm}$ ($W_p/W_n\text{ ratio} = 1.25$)
- **Minimum Power:** **53.856 µW** (-61.58% relative to baseline)
- **Oscillation Frequency:** $15.810236\text{ GHz}$ (-61.50% relative to baseline)
- **Objective Score ($\mathcal{F}$):** +0.000372

## 12. Lowest PDP Candidate
- **Candidate:** Iteration 62
- **Sizing:** $W_n = 0.19\text{ µm}$, $W_p = 2.66\text{ µm}$
- **Minimum PDP:** **0.332639 fJ** (-2.54% relative to baseline)
- **Oscillation Frequency:** $35.368852\text{ GHz}$
- **Average Power:** $117.651\text{ µW}$

## 13. Baseline Comparison
Comparison of the best observed Random Search candidate (Iteration 62) against the baseline reference ($W_n = 0.50\text{ µm}, W_p = 1.00\text{ µm}$):

| Metric | Baseline Reference | Best RS Candidate (Iter 62) | Relative Change (%) |
| :--- | :--- | :--- | :--- |
| **NMOS Width ($W_n$)** | $0.50\text{ µm}$ | $0.19\text{ µm}$ | -62.00% |
| **PMOS Width ($W_p$)** | $1.00\text{ µm}$ | $2.66\text{ µm}$ | +166.00% |
| **Sizing Ratio ($W_p/W_n$)** | 2.00 | 14.00 | +600.00% |
| **Frequency ($f_{osc}$)** | $41.069757\text{ GHz}$ | $35.368852\text{ GHz}$ | **-13.88%** |
| **Average Power ($P_{avg}$)** | $140.169554\text{ µW}$ | $117.651\text{ µW}$ | **-16.07%** |
| **Propagation Delay ($t_{pd}$)** | $2.434882\text{ ps}$ | $2.8273\text{ ps}$ | **+16.12%** |
| **Power-Delay Product ($PDP$)** | $0.341300\text{ fJ}$ | $0.332639\text{ fJ}$ | **-2.54%** |
| **Objective Score ($\mathcal{F}$)** | $0.000000$ | **0.010923** | **+0.010923** |

*Key Takeaway:* The best objective score improvement (+0.010923) is achieved primarily by reducing power consumption by 16.07% while suffering only a 13.88% reduction in frequency, exploiting the asymmetric weight ratio in the utility landscape at low $W_n$ and high $W_p$.

## 14. Top 10 Candidates
The top 10 candidates ranked by scalar objective score $\mathcal{F}$:

| Rank | Iteration | $W_n$ (µm) | $W_p$ (µm) | Ratio | Frequency (GHz) | Power (µW) | Delay (ps) | PDP (fJ) | Objective Score ($\mathcal{F}$) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | 62 | 0.19 | 2.66 | 14.00 | 35.368852 | 117.651 | 2.8273 | 0.332639 | **0.010923** |
| **2** | 28 | 0.17 | 1.91 | 11.24 | 28.930225 | 97.394 | 3.4566 | 0.336652 | **0.004793** |
| **3** | 92 | 0.23 | 2.28 | 9.91 | 37.195388 | 125.662 | 2.6885 | 0.337842 | **0.004583** |
| **4** | 27 | 0.12 | 1.41 | 11.75 | 20.797379 | 69.869 | 4.8083 | 0.335949 | **0.003967** |
| **5** | 26 | 0.30 | 2.74 | 9.13 | 46.923793 | 159.157 | 2.1311 | 0.339182 | **0.003539** |
| **6** | 29 | 1.20 | 1.43 | 1.19 | 77.234628 | 262.792 | 1.2948 | 0.340251 | **0.002879** |
| **7** | 98 | 1.15 | 1.48 | 1.29 | 76.832504 | 261.426 | 1.3015 | 0.340254 | **0.002857** |
| **8** | 52 | 1.13 | 1.35 | 1.19 | 72.819298 | 247.769 | 1.3733 | 0.340252 | **0.002713** |
| **9** | 51 | 1.13 | 1.02 | 0.90 | 63.342480 | 215.450 | 1.5787 | 0.340135 | **0.002623** |
| **10** | 21 | 1.14 | 1.04 | 0.91 | 64.247379 | 218.584 | 1.5565 | 0.340222 | **0.002462** |

## 15. Frequency-Power Trade-off
Across all 100 evaluated points:
- Oscillation frequency ranges from **15.81 GHz** ($W_n=0.24\text{ µm}, W_p=0.30\text{ µm}$) to **93.38 GHz** ($W_n=1.08\text{ µm}, W_p=2.42\text{ µm}$).
- Average power consumption ranges from **53.86 µW** to **318.90 µW**.
- Frequency and power exhibit a strong linear correlation coefficient ($r \approx 0.999$), demonstrating that under Level-1 MOS modeling without self-loading limits, power scales directly with switching frequency.

## 16. Pareto Analysis
A non-dominated sorting with respect to maximizing frequency and minimizing power identified **93 Pareto-optimal candidates** out of 100 evaluations.
- High-frequency Pareto extremum: Iteration 63 ($93.38\text{ GHz}, 318.90\text{ µW}$)
- Low-power Pareto extremum: Iteration 97 ($15.81\text{ GHz}, 53.86\text{ µW}$)
- Best objective Pareto candidate: Iteration 62 ($35.37\text{ GHz}, 117.65\text{ µW}$)

The Pareto front spans the entire frequency-power continuum smoothly, indicating a dense trade-off curve across the frozen bounds.

## 17. Convergence Analysis
Empirical convergence behavior of this 100-evaluation Random Search realization:
- **Evaluation 1:** Best $\mathcal{F} = -0.000962$
- **Evaluation 4:** Best $\mathcal{F} = +0.002156$
- **Evaluation 27 (reaching ~36% of final best score):** Best $\mathcal{F} = +0.003967$
- **Evaluation 28 (reaching ~44% of final best score):** Best $\mathcal{F} = +0.004793$
- **Evaluation 62 (reaching 100% of final best score):** Best $\mathcal{F} = **+0.010923**$
- **Evaluations 63–100:** Plateau at $\mathcal{F} = 0.010923$.

*Milestone Summary:*
- 25% of final best score reached at **Iteration 27**
- 50%, 75%, 90%, and 100% of final best score reached at **Iteration 62**
- The empirical best-so-far curve plateaued after evaluation 62, as no subsequent sample in iterations 63–100 surpassed Iteration 62's score of $0.010923$.

## 18. Objective Landscape
Visualizations generated in [`experiments/random_search/formal_100/plots/`](file:///d:/Projects/College/ring-oscillator/experiments/random_search/formal_100/plots/):
1. **[`wn_vs_wp_scatter.png`](file:///d:/Projects/College/ring-oscillator/experiments/random_search/formal_100/plots/wn_vs_wp_scatter.png):** 2D scatter map showing candidates colored by objective score. Highlights two prominent high-scoring design clusters:
   - Primary Region: Low $W_n$ ($0.12–0.30\text{ µm}$) and high $W_p$ ($1.80–2.74\text{ µm}$) with large $W_p/W_n$ ratios ($9.0–14.0$).
   - Secondary Region: High $W_n$ ($1.00–1.20\text{ µm}$) and moderate $W_p$ ($1.00–1.50\text{ µm}$) with near-unity ratios ($0.9–1.3$).
2. **[`objective_vs_wn.png`](file:///d:/Projects/College/ring-oscillator/experiments/random_search/formal_100/plots/objective_vs_wn.png):** Objective score distribution versus $W_n$.
3. **[`objective_vs_wp.png`](file:///d:/Projects/College/ring-oscillator/experiments/random_search/formal_100/plots/objective_vs_wp.png):** Objective score distribution versus $W_p$.
4. **[`convergence_best_so_far.png`](file:///d:/Projects/College/ring-oscillator/experiments/random_search/formal_100/plots/convergence_best_so_far.png):** Best-so-far objective trajectory over 100 evaluations.
5. **[`frequency_vs_power.png`](file:///d:/Projects/College/ring-oscillator/experiments/random_search/formal_100/plots/frequency_vs_power.png):** Frequency vs. Power trade-off landscape.
6. **[`pdp_vs_sizing.png`](file:///d:/Projects/College/ring-oscillator/experiments/random_search/formal_100/plots/pdp_vs_sizing.png):** Power-Delay Product vs. Sizing Ratio ($W_p/W_n$).

## 19. PDP Analysis
- **Minimum PDP:** $0.332639\text{ fJ}$
- **Maximum PDP:** $0.342880\text{ fJ}$
- **Mean PDP:** $0.341065\text{ fJ}$
- **Standard Deviation:** $0.001476\text{ fJ}$
- **Percentage Variation Range:** **3.08%** across the entire 100-sample dataset.
- **Baseline PDP:** $0.341300\text{ fJ}$

*Finding:* PDP remains remarkably invariant (~3% total variation) across a 6x frequency variation (15.8 GHz to 93.4 GHz). This empirical finding confirms that energy per oscillation cycle in Level-1 MOS modeling is governed predominantly by dynamic switching capacitance $E_{cycle} \approx C_{total} V_{DD}^2$.

## 20. Observations
1. Uniform Random Search sampled the search space evenly, discovering candidates in both the low-power high-ratio regime and the high-speed moderate-ratio regime.
2. The top candidate (Iteration 62, $\mathcal{F} = 0.010923$) lies near the upper $W_p$ boundary ($2.66\text{ µm}$) and lower $W_n$ region ($0.19\text{ µm}$).
3. Random Search required 62 evaluations to uncover its best candidate, remaining stochastic and inefficient compared to guided optimization.

## 21. Limitations
1. **Sample Inefficiency:** 100 uniform random evaluations leave significant unvisited gaps on the $10\text{ nm}$ grid.
2. **Lack of Exploitation:** Random Search does not utilize past evaluation scores to guide subsequent sampling toward promising high-score gradient directions.
3. **Single Realization:** These results represent a single stochastic realization using seed `2026`.

## 22. Random Search Benchmark Summary & Readiness for Bayesian Optimization
The formal 100-evaluation Random Search campaign has been completed in full compliance with `SRS.md`. 

### Verification Checklist:
- [x] Frozen bounds strictly enforced ($W_n \in [0.12, 1.20]\text{ µm}$, $W_p \in [0.24, 2.80]\text{ µm}$)
- [x] $10\text{ nm}$ grid snapping verified for all 100 candidates
- [x] Deterministic seed = 2026 recorded and verified
- [x] Independent $W_n / W_p$ sampling without ratio constraints verified
- [x] Objective function, baseline constants, and weights unchanged
- [x] Test suite passing 20/20 tests cleanly
- [x] Reproducibility and output artifact logging complete

**BAYESIAN OPTIMIZATION READINESS:**
**READY FOR BAYESIAN OPTIMIZATION**

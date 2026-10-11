# Bayesian Optimization Campaign A Summary (Scenario A: Balanced 0.5/0.5)

> [!NOTE]
> **THIS IS A DRY-RUN VALIDATION DATASET GENERATED USING A DETERMINISTIC SYNTHETIC EVALUATOR.**
> Zero LTspice simulations were executed. Physical simulation execution remains pending separate authorization.

- **Campaign Mode:** DRY-RUN (SYNTHETIC EVALUATOR)
- **Total Evaluations:** 50 / 50
- **Initial LHS Design:** 10 evaluations
- **Adaptive BO Iterations:** 40 evaluations
- **Feasible / Valid Simulations:** 48 / 50 (96.0%)
- **Deterministic Seed:** 2026
- **Total Duration:** 19.47 s
- **Acquisition Policy:** Expected Improvement (xi = 0.01 in standardized objective domain)
- **Search Space:** Wn in [0.12, 1.20] µm, Wp in [0.24, 2.80] µm (10 nm grid, 28,013 valid points)

## Best Feasible Candidate
- **Iteration:** 41 (ADAPTIVE_BO)
- **Transistor Sizing:** Wn = 0.2200 µm, Wp = 0.2800 µm (Ratio = 1.2727)
- **Objective Score F:** 0.137069
- **Oscillation Frequency:** 30.207729 GHz
- **Average Power:** 64.672 µW
- **Stage Propagation Delay:** 3.3104 ps
- **Power-Delay Product:** 0.214091 fJ

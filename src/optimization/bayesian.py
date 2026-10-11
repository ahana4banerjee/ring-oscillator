"""
Bayesian Optimization Engine Module.

Implements sample-efficient surrogate-model-guided optimization for CMOS Ring Oscillator
transistor sizing (Wn, Wp), adhering strictly to the SRS.md and README.md specifications:
- Space-filling Latin Hypercube Sampling (LHS) for the initial N_init = 10 evaluations (Phase 1).
- Gaussian Process Regression with Matérn 5/2 covariance kernel and ARD lengthscales (Phase 2).
- Expected Improvement (EI) acquisition function with exploration parameter xi = 0.01.
- Discrete 10 nm DRC grid snapping across frozen bounds [0.12, 1.20] µm x [0.24, 2.80] µm.
- Strict duplicate mitigation rejecting previously evaluated coordinates.
- Isolation from Random Search benchmark dataset (no prior data leakage).
"""

from typing import Dict, List, Tuple, Any, Optional, Set, Union
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from scipy.linalg import cholesky, cho_solve, solve_triangular
from scipy.stats import norm
from scipy.stats.qmc import LatinHypercube

from src.optimization.base import BaseOptimizer


class GaussianProcessMatern52:
    """
    Gaussian Process Regression with Matérn 5/2 covariance kernel and ARD lengthscales.
    
    Implements input normalization to [0, 1]^2, target standardization, numerical nugget
    handling on the covariance diagonal for Cholesky stability, and Maximum Log Marginal
    Likelihood estimation of kernel hyperparameters via L-BFGS-B.
    """

    def __init__(self, nugget: float = 1e-6, n_restarts: int = 3, random_state: Optional[np.random.RandomState] = None):
        """
        Args:
            nugget: Constant variance added to covariance diagonal for numerical stability (default: 1e-6).
            n_restarts: Number of random restarts for Log Marginal Likelihood optimization.
            random_state: NumPy RandomState instance for reproducible restarts.
        """
        self.nugget = nugget
        self.n_restarts = n_restarts
        self.rng = random_state if random_state is not None else np.random.RandomState(42)

        # Fitted attributes
        self.X_train: Optional[np.ndarray] = None
        self.y_train: Optional[np.ndarray] = None
        self.y_mean: float = 0.0
        self.y_std: float = 1.0
        self.lengthscales: np.ndarray = np.array([0.3, 0.3])
        self.signal_variance: float = 1.0
        self.L: Optional[np.ndarray] = None
        self.alpha: Optional[np.ndarray] = None

    @staticmethod
    def _matern52_kernel(X1: np.ndarray, X2: np.ndarray, lengthscales: np.ndarray, variance: float) -> np.ndarray:
        """Compute Matérn 5/2 kernel covariance matrix between X1 and X2 with ARD lengthscales."""
        # Scale differences by lengthscales: shape (N1, N2, D)
        scaled_diff = (X1[:, None, :] - X2[None, :, :]) / lengthscales
        r = np.sqrt(np.sum(scaled_diff ** 2, axis=-1))
        sqrt5_r = np.sqrt(5.0) * r
        return variance * (1.0 + sqrt5_r + (5.0 / 3.0) * (r ** 2)) * np.exp(-sqrt5_r)

    def _neg_log_marginal_likelihood(self, params: np.ndarray, X: np.ndarray, y: np.ndarray) -> float:
        """Negative log marginal likelihood objective function for L-BFGS-B minimization."""
        log_l1, log_l2, log_var = params
        lengthscales = np.exp([log_l1, log_l2])
        variance = np.exp(log_var)

        K = self._matern52_kernel(X, X, lengthscales, variance)
        K += self.nugget * np.eye(len(X))

        try:
            L = cholesky(K, lower=True)
        except np.linalg.LinAlgError:
            return 1e12

        alpha = cho_solve((L, True), y)
        n = len(y)
        data_fit = 0.5 * np.dot(y, alpha)
        complexity_penalty = np.sum(np.log(np.diag(L)))
        constant = 0.5 * n * np.log(2.0 * np.pi)

        return float(data_fit + complexity_penalty + constant)

    def fit(self, X: np.ndarray, y: np.ndarray) -> "GaussianProcessMatern52":
        """
        Fit the Gaussian Process model on training data.
        
        Args:
            X: Input array of shape (N, 2), normalized to [0, 1]^2.
            y: Target 1-D array of scalar objective scores.
        """
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)

        self.X_train = X.copy()
        self.y_mean = float(np.mean(y))
        self.y_std = float(np.std(y))
        if self.y_std < 1e-9:
            self.y_std = 1.0

        y_standardized = (y - self.y_mean) / self.y_std
        self.y_train = y_standardized

        # Optimize hyperparameters: [log_l1, log_l2, log_var]
        # Bounds: lengthscales in [0.05, 3.0], signal variance in [0.05, 20.0]
        bounds = [
            (np.log(0.05), np.log(3.0)),
            (np.log(0.05), np.log(3.0)),
            (np.log(0.05), np.log(20.0))
        ]

        best_loss = float("inf")
        best_params = np.array([np.log(0.3), np.log(0.3), np.log(1.0)])

        init_candidates = [
            np.array([np.log(0.3), np.log(0.3), np.log(1.0)]),
            np.array([np.log(0.15), np.log(0.15), np.log(2.0)]),
            np.array([np.log(0.6), np.log(0.6), np.log(0.5)])
        ]
        for _ in range(max(0, self.n_restarts - len(init_candidates))):
            rand_p = np.array([
                self.rng.uniform(bounds[0][0], bounds[0][1]),
                self.rng.uniform(bounds[1][0], bounds[1][1]),
                self.rng.uniform(bounds[2][0], bounds[2][1])
            ])
            init_candidates.append(rand_p)

        for init_p in init_candidates[:self.n_restarts]:
            res = minimize(
                self._neg_log_marginal_likelihood,
                init_p,
                args=(self.X_train, self.y_train),
                method="L-BFGS-B",
                bounds=bounds
            )
            if res.success and res.fun < best_loss:
                best_loss = res.fun
                best_params = res.x

        self.lengthscales = np.exp(best_params[:2])
        self.signal_variance = float(np.exp(best_params[2]))

        # Final factorizations
        K = self._matern52_kernel(self.X_train, self.X_train, self.lengthscales, self.signal_variance)
        K += self.nugget * np.eye(len(self.X_train))
        self.L = cholesky(K, lower=True)
        self.alpha = cho_solve((self.L, True), self.y_train)

        return self

    def predict(self, X_new: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict posterior mean and standard deviation at new candidate locations.
        
        Args:
            X_new: Array of shape (M, 2), normalized to [0, 1]^2.
            
        Returns:
            Tuple of (mean, std) in unstandardized (original) target units.
        """
        if self.X_train is None or self.L is None or self.alpha is None:
            raise RuntimeError("Gaussian Process must be fitted before calling predict.")

        X_new = np.asarray(X_new, dtype=float)
        K_star = self._matern52_kernel(self.X_train, X_new, self.lengthscales, self.signal_variance)

        # Posterior mean in standardized space
        mu_std = np.dot(K_star.T, self.alpha)

        # Posterior variance: k(x*, x*) - v^T v
        v = solve_triangular(self.L, K_star, lower=True)
        var_std = self.signal_variance - np.sum(v ** 2, axis=0)
        var_std = np.maximum(var_std, 1e-12)
        sigma_std = np.sqrt(var_std)

        # Transform back to original target units
        mu = mu_std * self.y_std + self.y_mean
        sigma = sigma_std * self.y_std

        return mu, sigma


class BayesianOptimizer(BaseOptimizer):
    """
    Bayesian Optimizer for CMOS Ring Oscillator transistor sizing.
    
    Coordinates Latin Hypercube space-filling initialization, Gaussian Process regression
    with Matérn 5/2 kernel, Expected Improvement acquisition over discrete 10 nm DRC grid,
    and duplicate candidate mitigation.
    """

    def __init__(
        self,
        search_space: Dict[str, Any],
        seed: Optional[int] = None,
        n_initial_samples: int = 10,
        xi: float = 0.01,
        nugget: float = 1e-6
    ):
        """
        Args:
            search_space: Dictionary specifying parameter bounds and grid resolution:
                - wn_min: float (minimum NMOS width in meters)
                - wn_max: float (maximum NMOS width in meters)
                - wp_min: float (minimum PMOS width in meters)
                - wp_max: float (maximum PMOS width in meters)
                - step_size: float (DRC grid step size in meters, e.g. 10e-9)
            seed: Optional deterministic integer random seed for reproducibility.
            n_initial_samples: Number of initial space-filling LHS samples (default: 10).
            xi: Exploration jitter parameter for Expected Improvement (default: 0.01).
            nugget: Numerical nugget added to covariance diagonal (default: 1e-6).
        """
        super().__init__(search_space=search_space, seed=seed)

        self.wn_min = float(search_space["wn_min"])
        self.wn_max = float(search_space["wn_max"])
        self.wp_min = float(search_space["wp_min"])
        self.wp_max = float(search_space["wp_max"])

        if self.wn_min >= self.wn_max:
            raise ValueError(f"wn_min ({self.wn_min}) must be strictly less than wn_max ({self.wn_max})")
        if self.wp_min >= self.wp_max:
            raise ValueError(f"wp_min ({self.wp_min}) must be strictly less than wp_max ({self.wp_max})")

        self.step_size = float(search_space.get("step_size", 10e-9))
        if self.step_size <= 0:
            raise ValueError("step_size must be strictly positive")

        self.n_initial_samples = int(n_initial_samples)
        self.xi = float(xi)
        self.nugget = float(nugget)

        self.rng = np.random.RandomState(seed) if seed is not None else np.random.RandomState()
        self.evaluated_coords: Set[Tuple[float, float]] = set()

        # Build complete discrete 10 nm grid
        self.wn_grid_vals = self._generate_axis_grid(self.wn_min, self.wn_max, self.step_size)
        self.wp_grid_vals = self._generate_axis_grid(self.wp_min, self.wp_max, self.step_size)
        self.num_grid_points = len(self.wn_grid_vals) * len(self.wp_grid_vals)

        # Precompute grid mesh and normalized coordinates
        WN_mesh, WP_mesh = np.meshgrid(self.wn_grid_vals, self.wp_grid_vals, indexing="ij")
        self.grid_coords = np.column_stack([WN_mesh.ravel(), WP_mesh.ravel()])
        self.grid_norm = np.column_stack([
            (self.grid_coords[:, 0] - self.wn_min) / (self.wn_max - self.wn_min),
            (self.grid_coords[:, 1] - self.wp_min) / (self.wp_max - self.wp_min)
        ])

        # Generate Phase 1 space-filling LHS candidate schedule
        self.initial_candidates = self._generate_lhs_schedule(self.n_initial_samples)
        self.initial_index = 0

        # Gaussian Process model container
        self.gp: Optional[GaussianProcessMatern52] = None

    @staticmethod
    def _generate_axis_grid(min_val: float, max_val: float, step: float) -> np.ndarray:
        """Generate discrete grid coordinates along a 1-D axis."""
        n_steps = int(round((max_val - min_val) / step))
        vals = [min_val + i * step for i in range(n_steps + 1)]
        vals = [round(v, 12) for v in vals if v <= max_val + 1e-12]
        return np.array(vals)

    def _snap_to_grid(self, val: float, min_val: float, max_val: float) -> float:
        """Snap a continuous float to the nearest discrete DRC grid step within bounds."""
        snapped = round((val - min_val) / self.step_size) * self.step_size + min_val
        snapped = max(min_val, min(max_val, snapped))
        return round(snapped, 12)

    def _generate_lhs_schedule(self, n_samples: int) -> List[Dict[str, float]]:
        """Generate N_init space-filling candidate points using Latin Hypercube Sampling."""
        lhs_sampler = LatinHypercube(d=2, seed=self.seed)
        samples_norm = lhs_sampler.random(n=n_samples)

        candidates = []
        seen = set()
        for s in samples_norm:
            raw_wn = self.wn_min + s[0] * (self.wn_max - self.wn_min)
            raw_wp = self.wp_min + s[1] * (self.wp_max - self.wp_min)
            wn = self._snap_to_grid(raw_wn, self.wn_min, self.wn_max)
            wp = self._snap_to_grid(raw_wp, self.wp_min, self.wp_max)

            # If snapped candidate creates duplicate within LHS schedule, find nearest unpicked grid point
            coord = (wn, wp)
            if coord in seen:
                for alt_coord in self.grid_coords:
                    alt_tuple = (round(alt_coord[0], 12), round(alt_coord[1], 12))
                    if alt_tuple not in seen:
                        wn, wp = alt_tuple
                        coord = alt_tuple
                        break
            seen.add(coord)
            candidates.append({"wn": wn, "wp": wp})

        return candidates

    def _compute_expected_improvement(self, mu: np.ndarray, sigma: np.ndarray, best_y: float) -> np.ndarray:
        """Compute Expected Improvement vector across candidate predictions."""
        improvement = mu - best_y - self.xi
        ei = np.zeros_like(mu)

        mask_positive = sigma > 1e-9
        if np.any(mask_positive):
            z = improvement[mask_positive] / sigma[mask_positive]
            ei[mask_positive] = improvement[mask_positive] * norm.cdf(z) + sigma[mask_positive] * norm.pdf(z)

        # For zero-variance points, improvement is deterministic
        mask_zero = ~mask_positive
        if np.any(mask_zero):
            ei[mask_zero] = np.maximum(0.0, improvement[mask_zero])

        return ei

    def suggest(self) -> Dict[str, float]:
        """
        Suggest the next candidate transistor sizing pair [Wn, Wp].
        
        Returns:
            Dictionary with keys 'wn' and 'wp' (in meters).
        """
        # Phase 1: Space-filling initial design (LHS)
        if len(self.history) < self.n_initial_samples and self.initial_index < len(self.initial_candidates):
            candidate = self.initial_candidates[self.initial_index]
            self.initial_index += 1
            return candidate

        # Phase 2: Adaptive Bayesian Optimization
        # Extract evaluated feasible coordinates and target objective values
        X_obs_list = []
        y_obs_list = []
        for record in self.history:
            cand = record["candidate"]
            coord = (round(cand["wn"], 12), round(cand["wp"], 12))
            # Normalize to [0, 1]^2
            norm_x = [
                (coord[0] - self.wn_min) / (self.wn_max - self.wn_min),
                (coord[1] - self.wp_min) / (self.wp_max - self.wp_min)
            ]
            X_obs_list.append(norm_x)
            y_obs_list.append(record["objective_score"])

        X_obs = np.array(X_obs_list)
        y_obs = np.array(y_obs_list)

        # Fit Gaussian Process surrogate
        self.gp = GaussianProcessMatern52(nugget=self.nugget, random_state=self.rng)
        self.gp.fit(X_obs, y_obs)

        # Compute posterior predictive mean and std across all 28,013 grid points
        mu_grid, sigma_grid = self.gp.predict(self.grid_norm)

        # Determine current best feasible objective score (or mean if none feasible)
        feasible_scores = [r["objective_score"] for r in self.history if r.get("is_feasible", False)]
        current_best = max(feasible_scores) if len(feasible_scores) > 0 else np.max(y_obs)

        # Calculate Expected Improvement
        ei_values = self._compute_expected_improvement(mu_grid, sigma_grid, current_best)

        # Duplicate Mitigation: Strictly mask already evaluated coordinates
        for idx, coord in enumerate(self.grid_coords):
            coord_tuple = (round(coord[0], 12), round(coord[1], 12))
            if coord_tuple in self.evaluated_coords:
                ei_values[idx] = -1.0

        best_idx = int(np.argmax(ei_values))

        # Fallback if all valid points have non-positive EI
        if ei_values[best_idx] < 0:
            unvisited_indices = [
                i for i, c in enumerate(self.grid_coords)
                if (round(c[0], 12), round(c[1], 12)) not in self.evaluated_coords
            ]
            if len(unvisited_indices) > 0:
                # Pick unvisited point with highest posterior predictive mean
                best_idx = unvisited_indices[int(np.argmax(mu_grid[unvisited_indices]))]
            else:
                raise RuntimeError("All candidate points in the search space have already been evaluated.")

        selected_wn = float(self.grid_coords[best_idx, 0])
        selected_wp = float(self.grid_coords[best_idx, 1])

        return {"wn": selected_wn, "wp": selected_wp}

    def register(self, candidate: Dict[str, float], result: Dict[str, Any]) -> None:
        """
        Register evaluation output for a proposed candidate.
        
        Args:
            candidate: Dictionary containing 'wn' and 'wp'.
            result: Result dictionary containing status, metrics, objective_score, and feasibility flag.
        """
        score = float(result.get("objective_score", -float("inf")))
        is_feasible = bool(result.get("is_feasible", False))

        coord_tuple = (round(candidate["wn"], 12), round(candidate["wp"], 12))
        self.evaluated_coords.add(coord_tuple)

        record = {
            "iteration": len(self.history),
            "candidate": candidate,
            "result": result,
            "objective_score": score,
            "is_feasible": is_feasible,
            "status": result.get("status", "UNKNOWN"),
            "acquisition_phase": "LHS" if len(self.history) < self.n_initial_samples else "ADAPTIVE_BO"
        }

        self.history.append(record)

        if is_feasible and score > self.best_score:
            self.best_score = score
            self.best_candidate_record = record

    def evaluate_candidate(
        self,
        candidate: Dict[str, float],
        parameterizer: Any,
        runner: Any,
        extractor: Any,
        objective_evaluator: Any,
        work_dir: Union[str, Path],
        iteration_idx: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute end-to-end evaluation pipeline for a candidate parameter set.
        
        Args:
            candidate: Dictionary containing 'wn' and 'wp'.
            parameterizer: NetlistParameterizer instance.
            runner: LTspiceRunner instance.
            extractor: MetricExtractor instance.
            objective_evaluator: ObjectiveEvaluator instance.
            work_dir: Working directory for generated netlist and log files.
            iteration_idx: Optional evaluation iteration index.
            
        Returns:
            Dictionary containing evaluation breakdown, candidate parameters, and objective score.
        """
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

        iter_str = f"iter_{iteration_idx:04d}" if iteration_idx is not None else "iter_temp"
        netlist_path = work_dir / f"run_{iter_str}.net"

        # 1. Parameter Injection (Wn, Wp)
        params_map = {"Wn": candidate["wn"], "Wp": candidate["wp"]}
        parameterizer.generate_netlist(params_map, netlist_path)

        # 2. Simulation Execution
        sim_res = runner.run(netlist_path)

        # 3. Measurement Extraction & Oscillation Check
        metrics = extractor.extract(sim_res)

        # 4. Scalar Objective Calculation
        score, is_feasible, breakdown = objective_evaluator.evaluate(metrics)

        result_payload = {
            "status": metrics.get("status", "FAILED"),
            "is_feasible": is_feasible,
            "objective_score": score,
            "metrics": metrics,
            "breakdown": breakdown,
            "sim_time_sec": sim_res.elapsed_time
        }

        # 5. Register with optimizer
        self.register(candidate, result_payload)

        return result_payload

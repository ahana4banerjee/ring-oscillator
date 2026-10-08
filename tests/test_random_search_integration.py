"""
Integration tests for Phase 5.2: Random Search Smoke Test.
"""

import pytest
import yaml
from pathlib import Path
from src.ltspice.parameterizer import NetlistParameterizer
from src.simulation.runner import LTspiceRunner
from src.evaluation.extractor import MetricExtractor
from src.evaluation.objective import ObjectiveEvaluator
from src.optimization.random_search import RandomSearchOptimizer
from src.utils.logger import ExperimentLogger

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_random_search_5_iteration_smoke_loop(tmp_path):
    config_path = PROJECT_ROOT / "configs" / "optimization_config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    template_path = PROJECT_ROOT / config["circuit"]["template_netlist"]
    ltspice_exe = Path(config["simulation"]["ltspice_executable"])

    parameterizer = NetlistParameterizer(template_path)
    runner = LTspiceRunner(ltspice_exe, timeout_seconds=15.0)
    extractor = MetricExtractor(stages=5)

    norm_cfg = config["normalization"]
    opt_cfg = config["optimization"]
    weights = opt_cfg["profiles"]["balanced"]

    evaluator = ObjectiveEvaluator(
        baseline_freq_hz=float(norm_cfg["baseline_frequency_hz"]),
        baseline_power_w=float(norm_cfg["baseline_power_w"]),
        w_f=float(weights["w_f"]),
        w_p=float(weights["w_p"]),
        penalty_value=-1.0e9
    )

    search_space = config["search_space"]
    optimizer = RandomSearchOptimizer(search_space=search_space, seed=42)

    csv_path = tmp_path / "smoke_log.csv"
    summary_path = tmp_path / "smoke_summary.json"
    logger = ExperimentLogger(csv_path=csv_path, summary_path=summary_path, experiment_id="pytest_smoke")

    work_dir = tmp_path / "sim_runs"

    for i in range(5):
        candidate = optimizer.suggest()
        assert search_space["wn_min"] <= candidate["wn"] <= search_space["wn_max"]
        assert search_space["wp_min"] <= candidate["wp"] <= search_space["wp_max"]

        result = optimizer.evaluate_candidate(
            candidate=candidate,
            parameterizer=parameterizer,
            runner=runner,
            extractor=extractor,
            objective_evaluator=evaluator,
            work_dir=work_dir,
            iteration_idx=i
        )

        logger.log_iteration(iteration=i, candidate=candidate, result=result)

        assert "status" in result
        assert "objective_score" in result
        assert "is_feasible" in result

    history = optimizer.get_history()
    assert len(history) == 5

    best = optimizer.get_best_candidate()
    assert best is not None
    assert best["candidate"] == {"wn": 0.63e-6, "wp": 1.1e-6}
    assert best["status"] == "SUCCESS"

    summary_file = logger.write_summary(total_evaluations=5, best_candidate_record=best)
    assert summary_file.exists()
    assert csv_path.exists()

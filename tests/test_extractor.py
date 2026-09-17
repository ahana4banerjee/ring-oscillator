"""
Unit & Integration tests for Phase 3: Measurement Extraction Engine.
"""

from pathlib import Path
import pytest
from src.ltspice.parser import LTspiceLogParser
from src.evaluation.extractor import MetricExtractor

PHASE2_DEMO_DIR = Path("results/raw/phase2_demo")


def test_log_parser_success():
    log_path = PHASE2_DEMO_DIR / "candidate_2.log"
    assert log_path.exists(), "candidate_2.log does not exist from Phase 2 verification"

    parser = LTspiceLogParser(log_path)
    is_healthy, msg = parser.check_simulation_health()
    assert is_healthy is True
    assert msg == "OK"

    measurements = parser.parse_measurements()
    assert "tperiod" in measurements
    assert "freq" in measurements
    assert "avgpower" in measurements

    assert measurements["tperiod"] is not None
    assert measurements["tperiod"] > 0
    assert measurements["freq"] is not None
    assert measurements["freq"] > 20e9  # > 20 GHz for 0.5u/1.0u candidate
    assert measurements["avgpower"] is not None
    assert measurements["avgpower"] > 0


def test_log_parser_failed_measurement():
    log_path = PHASE2_DEMO_DIR / "candidate_1.log"
    assert log_path.exists(), "candidate_1.log does not exist from Phase 2 verification"

    parser = LTspiceLogParser(log_path)
    measurements = parser.parse_measurements()
    assert measurements["tperiod"] is None
    assert measurements["freq"] is None
    assert measurements["avgpower"] is not None


def test_metric_extractor_success():
    log_path = PHASE2_DEMO_DIR / "candidate_2.log"
    extractor = MetricExtractor(num_stages=5)
    metrics = extractor.extract_from_log(log_path)

    assert metrics["status"] == "SUCCESS"
    assert metrics["is_oscillating"] is True
    assert metrics["freq_hz"] > 20e9
    assert metrics["freq_ghz"] > 20.0
    assert metrics["period_s"] > 0
    assert metrics["power_mw"] > 0
    assert metrics["delay_ps"] > 0
    assert metrics["pdp_j"] > 0

    # Verify stage delay relationship: t_pd = T_period / (2 * N) = T_period / 10
    expected_delay = metrics["period_s"] / 10.0
    assert abs(metrics["delay_s"] - expected_delay) < 1e-18


def test_metric_extractor_non_oscillating():
    log_path = PHASE2_DEMO_DIR / "candidate_1.log"
    extractor = MetricExtractor(num_stages=5)
    metrics = extractor.extract_from_log(log_path)

    assert metrics["status"] == "NO_OSCILLATION"
    assert metrics["is_oscillating"] is False
    assert metrics["freq_hz"] is None
    assert metrics["delay_ps"] is None
    assert metrics["power_mw"] is not None  # Power is still measured even if not oscillating


if __name__ == "__main__":
    pytest.main(["-v", __file__])

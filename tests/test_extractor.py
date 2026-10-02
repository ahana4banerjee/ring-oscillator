"""
Unit & Integration tests for Oscillation Validity and Measurement Extraction Engine.
"""

from pathlib import Path
import pytest
from src.ltspice.parser import LTspiceLogParser
from src.evaluation.extractor import MetricExtractor

PHASE2_DEMO_DIR = Path("results/raw/phase2_demo")
SANITY_DIR = Path("results/raw")


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
    assert measurements["freq"] > 20e9
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
    assert metrics["power_mw"] is not None


def test_candidate_1_regression_behavior():
    """Candidate 1 (Wn=0.36u, Wp=0.72u) fails 0.9V threshold crossings and must remain NO_OSCILLATION."""
    log_path = SANITY_DIR / "sanity_candidate_1.log"
    if not log_path.exists():
        log_path = PHASE2_DEMO_DIR / "candidate_1.log"

    extractor = MetricExtractor(num_stages=5)
    metrics = extractor.extract_from_log(log_path)

    assert metrics["status"] == "NO_OSCILLATION"
    assert metrics["is_oscillating"] is False
    assert metrics["freq_hz"] is None


def test_candidate_3_regression_behavior():
    """Candidate 3 (Wn=0.18u, Wp=0.36u) produces ~50 GHz oscillation and must remain SUCCESS / oscillating."""
    log_path = SANITY_DIR / "sanity_candidate_3.log"
    assert log_path.exists(), "sanity_candidate_3.log missing"

    extractor = MetricExtractor(num_stages=5)
    metrics = extractor.extract_from_log(log_path)

    assert metrics["status"] == "SUCCESS"
    assert metrics["is_oscillating"] is True
    assert abs(metrics["freq_ghz"] - 50.0) < 0.1
    assert abs(metrics["delay_ps"] - 2.0) < 0.1
    assert abs(metrics["power_mw"] - 50.875) < 0.1


def test_invalid_non_positive_period_rejection(tmp_path):
    """Verify non-positive or NaN periods are rejected safely without crashing."""
    mock_log = tmp_path / "mock_fail.log"
    mock_log.write_text("tperiod=-1.0e-9\nfreq=-1e9\navgpower=0.05\n", encoding='utf-8')

    extractor = MetricExtractor(num_stages=5)
    metrics = extractor.extract_from_log(mock_log)

    assert metrics["status"] == "NO_OSCILLATION"
    assert metrics["is_oscillating"] is False
    assert metrics["freq_hz"] is None


if __name__ == "__main__":
    pytest.main(["-v", __file__])

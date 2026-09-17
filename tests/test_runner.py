"""
Integration test for Phase 2: Python <-> LTspice Automation.

Tests parameter injection via NetlistParameterizer and headless batch execution via LTspiceRunner.
"""

from pathlib import Path
import pytest
from src.ltspice.parameterizer import NetlistParameterizer, format_spice_engineering
from src.simulation.runner import LTspiceRunner

LTSPICE_EXE = r"C:\Users\Ahana Banerjee\AppData\Local\Programs\ADI\LTspice\LTspice.exe"
TEMPLATE_PATH = Path("circuits/templates/ring_oscillator.net")


def test_spice_engineering_formatting():
    assert format_spice_engineering(0.5e-6) == "0.5u"
    assert format_spice_engineering(180e-9) == "0.18u"
    assert format_spice_engineering(1.8) == "1.8"
    assert format_spice_engineering(0) == "0"


def test_parameterizer_generation(tmp_path):
    parameterizer = NetlistParameterizer(TEMPLATE_PATH)
    test_params = {'Wn': 0.6e-6, 'Wp': 1.2e-6, 'VDD_VAL': 1.8}
    out_netlist = tmp_path / "test_run.net"

    written_path = parameterizer.generate_netlist(test_params, out_netlist)
    assert written_path.exists()

    content = written_path.read_text(encoding='utf-8')
    assert ".param Wn = 0.6u" in content or ".param WN = 0.6u" in content
    assert ".param Wp = 1.2u" in content or ".param WP = 1.2u" in content


def test_headless_ltspice_runner(tmp_path):
    parameterizer = NetlistParameterizer(TEMPLATE_PATH)
    test_params = {'Wn': 0.5e-6, 'Wp': 1.0e-6, 'VDD_VAL': 1.8}
    out_netlist = tmp_path / "run_temp.net"
    parameterizer.generate_netlist(test_params, out_netlist)

    runner = LTspiceRunner(executable_path=LTSPICE_EXE, timeout_seconds=15.0)
    result = runner.run(out_netlist)

    assert result.success is True
    assert result.return_code == 0
    assert result.log_path is not None
    assert result.log_path.exists()
    assert result.elapsed_time > 0.0

    log_content = result.log_path.read_text(encoding='utf-8', errors='ignore')
    assert "LTspice" in log_content
    assert "tperiod" in log_content.lower() or "freq" in log_content.lower()


if __name__ == "__main__":
    pytest.main(["-v", __file__])

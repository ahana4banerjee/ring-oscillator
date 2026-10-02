"""
Electrical metric extractor module.

Processes raw parsed measurements from LTspice and computes derived electrical metrics:
- Fundamental Oscillation Frequency (f_osc in Hz / GHz)
- Total Average Power Consumption (P_avg in Watts / mW)
- Stage Propagation Delay (t_pd in seconds / ps)
- Power-Delay Product (PDP in Joules)

Oscillation Validity Rule:
A candidate circuit is classified as a VALID oscillating candidate if and only if:
1. Simulation Health: SPICE transient simulation completed without solver fatal errors.
2. Measurable Waveform: A valid steady-state period (tperiod) was extracted from SPICE .meas directives.
3. Positive & Finite Period: Measured period T_period > 0 and is not NaN/Inf.
4. Positive & Finite Frequency: Extracted frequency f_osc = 1 / T_period > 0 and is not NaN/Inf.
5. Internal Consistency: Derived stage delay t_pd = T_period / (2 * N) > 0.
"""

import math
from pathlib import Path
from typing import Dict, Any, Optional, Union
from src.ltspice.parser import LTspiceLogParser


class MetricExtractor:
    """Extracts raw electrical metrics and computes derived ring oscillator performance metrics."""

    def __init__(self, num_stages: int = 5):
        self.num_stages = num_stages

    def extract_from_log(self, log_path: Union[str, Path]) -> Dict[str, Any]:
        """Parse log file and return a dictionary of raw and derived metrics.

        Args:
            log_path: Path to LTspice .log file.

        Returns:
            Dictionary containing status, raw measurements, and derived metrics.
        """
        parser = LTspiceLogParser(log_path)
        is_healthy, health_msg = parser.check_simulation_health()

        if not is_healthy:
            return {
                "status": "SIMULATION_ERROR",
                "error_message": health_msg,
                "is_oscillating": False,
                "freq_hz": None,
                "freq_ghz": None,
                "period_s": None,
                "power_w": None,
                "power_mw": None,
                "delay_s": None,
                "delay_ps": None,
                "pdp_j": None
            }

        raw_meas = parser.parse_measurements()

        # Extract period, frequency, power
        period = raw_meas.get("tperiod")
        freq = raw_meas.get("freq")
        power = raw_meas.get("avgpower")

        # Fallback calculation if freq was not directly measured but period exists
        if freq is None and period is not None and period > 0:
            freq = 1.0 / period
        elif period is None and freq is not None and freq > 0:
            period = 1.0 / freq

        # Deterministic Oscillation Validity Rule Verification:
        # 1. period and freq must be non-None
        # 2. period and freq must be finite numbers (not NaN / Inf)
        # 3. period and freq must be strictly positive (> 0)
        is_valid_period = (
            period is not None and
            isinstance(period, (int, float)) and
            not math.isnan(period) and
            not math.isinf(period) and
            period > 0
        )

        is_valid_freq = (
            freq is not None and
            isinstance(freq, (int, float)) and
            not math.isnan(freq) and
            not math.isinf(freq) and
            freq > 0
        )

        is_oscillating = is_valid_period and is_valid_freq

        if not is_oscillating:
            return {
                "status": "NO_OSCILLATION",
                "error_message": "Circuit did not oscillate (measurement failed or non-positive frequency)",
                "is_oscillating": False,
                "raw_measurements": raw_meas,
                "freq_hz": None,
                "freq_ghz": None,
                "period_s": None,
                "power_w": power,
                "power_mw": power * 1e3 if power is not None else None,
                "delay_s": None,
                "delay_ps": None,
                "pdp_j": None
            }

        # Calculate derived metrics
        # Stage propagation delay: t_pd = T_period / (2 * N_stages)
        delay_s = period / (2.0 * self.num_stages)
        delay_ps = delay_s * 1e12
        freq_ghz = freq / 1e9
        power_mw = power * 1e3 if power is not None else None

        # Power-Delay Product (PDP): P_avg * t_pd
        pdp_j = (power * delay_s) if power is not None else None

        return {
            "status": "SUCCESS",
            "error_message": None,
            "is_oscillating": True,
            "raw_measurements": raw_meas,
            "period_s": period,
            "freq_hz": freq,
            "freq_ghz": freq_ghz,
            "power_w": power,
            "power_mw": power_mw,
            "delay_s": delay_s,
            "delay_ps": delay_ps,
            "pdp_j": pdp_j
        }

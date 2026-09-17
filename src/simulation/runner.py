"""
Simulation runner module for LTspice.

Executes LTspice in headless/batch mode (-b -Run) with timeout and watchdog management.
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional, Tuple, Union


class SimulationResult:
    """Represents the outcome of an LTspice simulation execution."""

    def __init__(self,
                 success: bool,
                 return_code: int,
                 elapsed_time: float,
                 netlist_path: Path,
                 log_path: Optional[Path] = None,
                 raw_path: Optional[Path] = None,
                 error_message: Optional[str] = None):
        self.success = success
        self.return_code = return_code
        self.elapsed_time = elapsed_time
        self.netlist_path = netlist_path
        self.log_path = log_path
        self.raw_path = raw_path
        self.error_message = error_message

    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else f"FAILED ({self.error_message})"
        return f"<SimulationResult [{status}] elapsed={self.elapsed_time:.2f}s log={self.log_path}>"


class LTspiceRunner:
    """Handles execution of LTspice CLI process in batch mode with watchdog timeouts."""

    def __init__(self, executable_path: Union[str, Path], timeout_seconds: float = 30.0):
        self.executable_path = Path(executable_path)
        self.timeout_seconds = timeout_seconds

        if not self.executable_path.exists():
            raise FileNotFoundError(
                f"LTspice executable not found at specified path: {self.executable_path}"
            )

    def run(self, netlist_path: Union[str, Path]) -> SimulationResult:
        """Run LTspice in batch mode on the provided netlist path.

        Args:
            netlist_path: Path to the .cir or .net file to simulate.

        Returns:
            SimulationResult containing status, execution time, and output paths.
        """
        netlist_path = Path(netlist_path).resolve()
        if not netlist_path.exists():
            return SimulationResult(
                success=False,
                return_code=-1,
                elapsed_time=0.0,
                netlist_path=netlist_path,
                error_message=f"Netlist file does not exist: {netlist_path}"
            )

        # Expected output files (LTspice creates .log and .raw alongside netlist)
        log_path = netlist_path.with_suffix('.log')
        raw_path = netlist_path.with_suffix('.raw')

        # Clean stale log/raw outputs prior to run
        if log_path.exists():
            try:
                log_path.unlink()
            except OSError:
                pass
        if raw_path.exists():
            try:
                raw_path.unlink()
            except OSError:
                pass

        # Build CLI command: LTspice.exe -b -Run <netlist>
        cmd = [
            str(self.executable_path),
            "-b",
            "-Run",
            str(netlist_path)
        ]

        start_time = time.time()
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(netlist_path.parent)
            )

            stdout, stderr = process.communicate(timeout=self.timeout_seconds)
            elapsed_time = time.time() - start_time
            return_code = process.returncode

            # Check if output files were generated
            log_exists = log_path.exists()
            raw_exists = raw_path.exists()

            if return_code == 0 and log_exists:
                return SimulationResult(
                    success=True,
                    return_code=return_code,
                    elapsed_time=elapsed_time,
                    netlist_path=netlist_path,
                    log_path=log_path,
                    raw_path=raw_path if raw_exists else None
                )
            else:
                err_msg = stderr.decode('utf-8', errors='ignore') or "Missing log file or non-zero exit code"
                return SimulationResult(
                    success=False,
                    return_code=return_code,
                    elapsed_time=elapsed_time,
                    netlist_path=netlist_path,
                    log_path=log_path if log_exists else None,
                    raw_path=raw_path if raw_exists else None,
                    error_message=err_msg
                )

        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            elapsed_time = time.time() - start_time
            return SimulationResult(
                success=False,
                return_code=-2,
                elapsed_time=elapsed_time,
                netlist_path=netlist_path,
                error_message=f"Simulation timed out after {self.timeout_seconds} seconds"
            )
        except Exception as e:
            elapsed_time = time.time() - start_time
            return SimulationResult(
                success=False,
                return_code=-3,
                elapsed_time=elapsed_time,
                netlist_path=netlist_path,
                error_message=str(e)
            )

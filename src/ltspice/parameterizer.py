"""
Parameterizer module for LTspice netlists.

Injects parameter values (e.g., Wn, Wp, L, VDD) into parameterized SPICE netlists.
"""

import re
from pathlib import Path
from typing import Dict, Union


def format_spice_engineering(value: float) -> str:
    """Format a floating-point number into SPICE engineering notation string.
    
    Examples:
        0.5e-6  -> "0.5u"
        180e-9  -> "180n"
        1.8     -> "1.8"
    """
    if value == 0:
        return "0"

    abs_val = abs(value)
    
    if abs_val >= 1.0:
        return f"{value:.4g}"
    elif abs_val >= 1e-3:
        return f"{value * 1e3:.4g}m"
    elif abs_val >= 1e-7:
        # Anything >= 0.1um (100nm) formatted in microns (u), e.g. 0.5e-6 -> 0.5u, 0.18e-6 -> 0.18u
        return f"{value * 1e6:.4g}u"
    elif abs_val >= 1e-10:
        return f"{value * 1e9:.4g}n"
    elif abs_val >= 1e-13:
        return f"{value * 1e12:.4g}p"
    else:
        return f"{value:.4e}"


class NetlistParameterizer:
    """Handles parameter substitution and injection for SPICE netlists."""

    def __init__(self, template_path: Union[str, Path]):
        self.template_path = Path(template_path)
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template netlist not found: {self.template_path}")
        
        with open(self.template_path, 'r', encoding='utf-8') as f:
            self.template_content = f.read()

    def generate_netlist(self, params: Dict[str, float], output_path: Union[str, Path]) -> Path:
        """Inject parameters into template netlist and write to output_path.
        
        Args:
            params: Dictionary mapping parameter names to float values (e.g. {'Wn': 0.5e-6, 'Wp': 1.0e-6})
            output_path: Path where the generated netlist should be saved.
            
        Returns:
            Path object pointing to written netlist.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        content = self.template_content
        for param_name, param_val in params.items():
            val_str = format_spice_engineering(param_val)
            pattern = re.compile(rf"(\.param\s+{re.escape(param_name)}\s*=\s*)([^\s]+)", re.IGNORECASE)
            content = pattern.sub(rf"\g<1>{val_str}", content)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return output_path

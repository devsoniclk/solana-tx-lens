"""
solana-tx-lens: Headless transaction simulation inspector, CPI tree visualizer,
and Anchor error decoder for Solana.
"""

from .cpi_parser import parse_cpi_tree
from .diff_engine import compute_account_diffs
from .error_decoder import decode_solana_error
from .models import AccountDiff, CPIInvocation, ErrorInfo, SimulationResult
from .simulator import SolanaSimulator
from .visualizer import render_cpi_tree

__version__ = "0.1.0"
__all__ = [
    "SolanaSimulator",
    "parse_cpi_tree",
    "render_cpi_tree",
    "decode_solana_error",
    "compute_account_diffs",
    "SimulationResult",
    "CPIInvocation",
    "AccountDiff",
    "ErrorInfo",
]

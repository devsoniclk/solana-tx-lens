from __future__ import annotations

"""
solana-tx-lens: Headless transaction simulation inspector, CPI tree visualizer,
pre-flight MEV safety guard, dynamic compute budget optimizer, and Anchor error decoder for Solana.
"""

from .contention import AccountAccess, ContentionReport, audit_account_contention
from .cpi_parser import parse_cpi_tree
from .diff_engine import compute_account_diffs, compute_token_diffs, parse_token_transfers_from_logs
from .error_decoder import decode_solana_error
from .guard import assess_simulation_health
from .html_report import render_html_report
from .instruction_decoder import extract_instruction_name, get_program_label
from .models import (
    AccountDiff,
    CPIInvocation,
    ErrorInfo,
    HealthIssue,
    SimulationHealth,
    SimulationResult,
    TokenBalanceDiff,
)
from .optimizer import ComputeBudgetOptimization, optimize_compute_budget
from .simulator import SolanaSimulator
from .visualizer import (
    render_cpi_mermaid_flowchart,
    render_cpi_mermaid_sequence,
    render_cpi_tree,
    render_simulation_report,
)

__version__ = "0.3.0"
__all__ = [
    "SolanaSimulator",
    "parse_cpi_tree",
    "render_cpi_tree",
    "render_cpi_mermaid_sequence",
    "render_cpi_mermaid_flowchart",
    "render_simulation_report",
    "render_html_report",
    "decode_solana_error",
    "compute_account_diffs",
    "compute_token_diffs",
    "parse_token_transfers_from_logs",
    "assess_simulation_health",
    "optimize_compute_budget",
    "audit_account_contention",
    "get_program_label",
    "extract_instruction_name",
    "SimulationResult",
    "CPIInvocation",
    "AccountDiff",
    "TokenBalanceDiff",
    "SimulationHealth",
    "HealthIssue",
    "ErrorInfo",
    "ComputeBudgetOptimization",
    "ContentionReport",
    "AccountAccess",
]

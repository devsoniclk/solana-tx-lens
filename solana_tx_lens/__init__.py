from __future__ import annotations

"""
solana-tx-lens: Headless transaction simulation inspector, CPI tree visualizer,
pre-flight MEV safety guard, dynamic compute budget optimizer, atomic Jito bundle simulator,
and Model Context Protocol (MCP) server for Solana.
"""

from .bundle import (
    JITO_TIP_ACCOUNTS,
    BundleSimulationResult,
    BundleSimulator,
    JitoTipAnalysis,
)
from .contention import AccountAccess, ContentionReport, audit_account_contention
from .cpi_parser import parse_cpi_tree
from .diff_engine import compute_account_diffs, compute_token_diffs, parse_token_transfers_from_logs
from .error_decoder import decode_solana_error
from .fee_guide import JitoTipTier, PriorityFeeTier, SolanaFeeGuide, generate_fee_guide
from .guard import assess_simulation_health
from .html_report import render_bundle_html_report, render_html_report
from .instruction_decoder import extract_instruction_name, get_program_label
from .mcp_server import SolanaLensMCPServer
from .mev_radar import MEVAttackVector, MEVVulnerabilityReport, scan_mev_vulnerabilities
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
from .route_analyzer import SwapHop, SwapRouteReport, analyze_swap_route, render_route_ascii, render_route_mermaid
from .simulator import SolanaSimulator
from .visualizer import (
    render_cpi_mermaid_flowchart,
    render_cpi_mermaid_sequence,
    render_cpi_tree,
    render_simulation_report,
)

__version__ = "0.5.0"
__all__ = [
    "SolanaSimulator",
    "BundleSimulator",
    "BundleSimulationResult",
    "JitoTipAnalysis",
    "JITO_TIP_ACCOUNTS",
    "SolanaLensMCPServer",
    "parse_cpi_tree",
    "render_cpi_tree",
    "render_cpi_mermaid_sequence",
    "render_cpi_mermaid_flowchart",
    "render_simulation_report",
    "render_html_report",
    "render_bundle_html_report",
    "decode_solana_error",
    "compute_account_diffs",
    "compute_token_diffs",
    "parse_token_transfers_from_logs",
    "assess_simulation_health",
    "optimize_compute_budget",
    "audit_account_contention",
    "scan_mev_vulnerabilities",
    "analyze_swap_route",
    "render_route_ascii",
    "render_route_mermaid",
    "generate_fee_guide",
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
    "MEVVulnerabilityReport",
    "MEVAttackVector",
    "SwapRouteReport",
    "SwapHop",
    "SolanaFeeGuide",
    "PriorityFeeTier",
    "JitoTipTier",
]

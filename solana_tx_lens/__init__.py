from __future__ import annotations

"""
solana-tx-lens: Headless transaction simulation inspector, CPI tree visualizer,
pre-flight MEV safety guard, dynamic compute budget optimizer, atomic Jito bundle simulator,
and Model Context Protocol (MCP) server for Solana.
"""

from .access_list import (
    AccessListOptimizationReport,
    AccountLockRole,
    LUTRecommendation,
    SerializationStats,
    analyze_access_list,
    estimate_tx_serialized_size,
)
from .bundle import (
    JITO_TIP_ACCOUNTS,
    BundleSimulationResult,
    BundleSimulator,
    JitoTipAnalysis,
)
from .compression import (
    CompressionTreeAuditReport,
    audit_compression_tree,
    calculate_tree_account_size,
)
from .contention import AccountAccess, ContentionReport, audit_account_contention
from .cpi_parser import parse_cpi_tree
from .diff_engine import compute_account_diffs, compute_token_diffs, parse_token_transfers_from_logs
from .error_decoder import decode_solana_error
from .events import (
    AnchorEventDecoder,
    DecodedAnchorEvent,
    ProgramEventsReport,
    ProgramReturnData,
    compute_anchor_event_discriminator,
    decode_program_events_and_returns,
)
from .fee_guide import JitoTipTier, PriorityFeeTier, SolanaFeeGuide, generate_fee_guide
from .flamegraph import (
    CUHotspot,
    FlamegraphNode,
    FlamegraphReport,
    build_flamegraph_from_logs,
    render_ascii_flamegraph,
    render_svg_flamegraph,
)
from .guard import assess_simulation_health
from .html_report import render_bundle_html_report, render_html_report
from .idl_decoder import (
    AnchorIDLRegistry,
    DecodedInstruction,
    DecodedInstructionAccount,
    compute_account_discriminator,
    compute_anchor_discriminator,
    compute_event_discriminator,
    compute_instruction_discriminator,
    get_default_idl_registry,
)
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
from .policy import (
    PolicyRule,
    PolicyVerificationReport,
    PolicyViolation,
    verify_simulation_policy,
)
from .route_analyzer import SwapHop, SwapRouteReport, analyze_swap_route, render_route_ascii, render_route_mermaid
from .simulator import SolanaSimulator
from .snapshot import (
    AccountSnapshotDelta,
    ShadowReplaySummary,
    ShadowStateReplayer,
    create_account_snapshot_delta,
)
from .stress_tester import (
    CUSensitivityResult,
    ExecutionSensitivityReport,
    FeeVolatilityScenario,
    SlippageSensitivityResult,
    SlippageStressTester,
    stress_test_simulation,
)
from .token_extensions import (
    ExtensionDetail,
    TokenExtensionAuditReport,
    TransferFeeConfig,
    TransferHookConfig,
    calculate_transfer_fee,
    inspect_token_extensions,
)
from .visualizer import (
    render_cpi_mermaid_flowchart,
    render_cpi_mermaid_sequence,
    render_cpi_tree,
    render_simulation_report,
)
from .zero_copy import (
    FieldLayout,
    FieldTypeSpec,
    ZeroCopyAuditReport,
    audit_zero_copy_layout,
    benchmark_zero_copy_cu,
)
from .witness_bridge import attest_simulation_result

__version__ = "0.9.0"
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
    "decode_program_events_and_returns",
    "compute_anchor_event_discriminator",
    "AnchorEventDecoder",
    "DecodedAnchorEvent",
    "ProgramReturnData",
    "ProgramEventsReport",
    "create_account_snapshot_delta",
    "ShadowStateReplayer",
    "AccountSnapshotDelta",
    "ShadowReplaySummary",
    "stress_test_simulation",
    "SlippageStressTester",
    "ExecutionSensitivityReport",
    "SlippageSensitivityResult",
    "CUSensitivityResult",
    "FeeVolatilityScenario",
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
    "analyze_access_list",
    "estimate_tx_serialized_size",
    "AccessListOptimizationReport",
    "AccountLockRole",
    "LUTRecommendation",
    "SerializationStats",
    "inspect_token_extensions",
    "calculate_transfer_fee",
    "TokenExtensionAuditReport",
    "TransferFeeConfig",
    "TransferHookConfig",
    "ExtensionDetail",
    "verify_simulation_policy",
    "PolicyRule",
    "PolicyViolation",
    "PolicyVerificationReport",
    "FieldLayout",
    "FieldTypeSpec",
    "ZeroCopyAuditReport",
    "audit_zero_copy_layout",
    "benchmark_zero_copy_cu",
    "AnchorIDLRegistry",
    "DecodedInstruction",
    "DecodedInstructionAccount",
    "compute_anchor_discriminator",
    "compute_instruction_discriminator",
    "compute_account_discriminator",
    "compute_event_discriminator",
    "get_default_idl_registry",
    "FlamegraphNode",
    "FlamegraphReport",
    "CUHotspot",
    "build_flamegraph_from_logs",
    "render_ascii_flamegraph",
    "render_svg_flamegraph",
    "CompressionTreeAuditReport",
    "audit_compression_tree",
    "calculate_tree_account_size",
    "attest_simulation_result",
]

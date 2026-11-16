from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .instruction_decoder import KNOWN_PROGRAMS
from .models import SimulationResult

# Recognized DEX programs that execute swaps
DEX_PROGRAM_IDS = {
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium AMM v4
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",  # Raydium CLMM
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C",  # Raydium CPMM
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",  # Orca Whirlpool
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",  # Pump.fun
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",  # Jupiter v6
    "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB",  # Jupiter v4
    "srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX",  # OpenBook v1
    "opnb2TXrmDdHGaeR2wTcrFio526bBHu4WnwSZmkq9G6",  # OpenBook v2
    "PhoeNiXZ8ByJGLkxNfZRnkUfjvmuYqLR89jjFHGqdXY",  # Phoenix DEX
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo",  # Meteora DLMM
    "Eo7WjKq67rjJQSZxS6z3YkapzY3eMj6Xy8X5EQVn5UaB",  # Meteora Dynamic AMM
    "2wT8Yq49kHgDzXuPxZSaeLaH1qbmGXtEyPy64bL7aD3c",  # Lifinity v2
    "MoonCVVNZFSYkqNXP6bxHLPL6QQJiMagDL3qcqUQTrG",  # Moonshot
}


@dataclass
class MEVAttackVector:
    vector_type: str  # "SANDWICH_RISK", "EXCESSIVE_SLIPPAGE", "UNPROTECTED_PUBLIC_MEMPOOL", etc.
    severity: str    # "INFO", "WARNING", "CRITICAL"
    description: str
    impact: str
    remediation: str

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class MEVVulnerabilityReport:
    risk_level: str  # "SAFE", "LOW", "MEDIUM", "HIGH", "CRITICAL"
    is_sandwich_vulnerable: bool
    is_dex_swap: bool
    detected_slippage_bps: Optional[int]
    max_recommended_slippage_bps: int
    estimated_extractable_mev_pct: float
    attack_vectors: List[MEVAttackVector] = field(default_factory=list)
    mitigations: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def scan_mev_vulnerabilities(
    result: SimulationResult,
    slippage_tolerance_bps: Optional[int] = None,
    is_public_mempool: bool = True,
    max_safe_slippage_bps: int = 50,  # 0.50%
) -> MEVVulnerabilityReport:
    """
    Evaluates a transaction simulation for MEV vulnerability, sandwich attack exposure,
    excessive slippage, and frontrunning risks.
    """
    attack_vectors: List[MEVAttackVector] = []
    mitigations: List[str] = []

    # 1. Detect if any DEX/AMM programs are invoked
    dex_detected = False
    dex_names: List[str] = []

    def check_invocations(nodes):
        nonlocal dex_detected
        for node in nodes:
            if node.program_id in DEX_PROGRAM_IDS:
                dex_detected = True
                name = KNOWN_PROGRAMS.get(node.program_id, node.program_name or node.program_id[:8])
                if name not in dex_names:
                    dex_names.append(name)
            elif node.instruction_name and any(
                k in node.instruction_name.lower() for k in ["swap", "buy", "sell", "route"]
            ):
                dex_detected = True
                name = node.program_name or node.program_id[:8]
                if name not in dex_names:
                    dex_names.append(name)
            if node.children:
                check_invocations(node.children)

    check_invocations(result.cpi_roots)

    # Check token diffs to see if tokens were swapped
    has_token_swap = False
    if len(result.token_diffs) >= 2:
        inflow = any(td.delta < 0 for td in result.token_diffs)
        outflow = any(td.delta > 0 for td in result.token_diffs)
        if inflow and outflow:
            has_token_swap = True
            dex_detected = True

    # 2. Check for slippage error breach in simulation
    if result.error and any(
        k in result.error.name.lower() for k in ["slippage", "slippagetoleranceexceeded", "exceeded"]
    ):
        attack_vectors.append(
            MEVAttackVector(
                vector_type="SLIPPAGE_BREACH",
                severity="CRITICAL",
                description=(
                    f"Simulation failed due to slippage violation ({result.error.name}: {result.error.description}). "
                    "Current pool price has moved past allowable minimum output."
                ),
                impact="Transaction reverted on-chain; network and priority fees wasted.",
                remediation="Refresh quote with recent slot state or adjust slippage bounds before broadcast.",
            )
        )
        mitigations.append("Refresh pool reserves and quote against the most recent slot.")

    # 3. Assess slippage tolerance configuration
    effective_slippage_bps = slippage_tolerance_bps
    if effective_slippage_bps is None:
        # Check logs for mentions of slippage bps
        for log in result.raw_logs:
            if "slippage" in log.lower():
                import re
                m = re.search(r"slippage\s*(?:bps|basis points|:)?\s*(\d+)", log, re.IGNORECASE)
                if m:
                    effective_slippage_bps = int(m.group(1))
                    break

    estimated_extractable_pct = 0.0
    is_sandwich_vulnerable = False

    if dex_detected:
        if effective_slippage_bps is not None:
            if effective_slippage_bps > 300:  # > 3%
                is_sandwich_vulnerable = True
                estimated_extractable_pct = round((effective_slippage_bps - max_safe_slippage_bps) / 100.0, 2)
                attack_vectors.append(
                    MEVAttackVector(
                        vector_type="CRITICAL_SLIPPAGE_EXPOSURE",
                        severity="CRITICAL",
                        description=(
                            f"Extremely wide slippage tolerance configured ({effective_slippage_bps} bps / "
                            f"{effective_slippage_bps/100:.1f}%). Highly profitable target for sandwich bots."
                        ),
                        impact=f"Searcher bots can extract up to ~{estimated_extractable_pct:.2f}% of swap value.",
                        remediation=f"Tighten slippage tolerance to ≤ {max_safe_slippage_bps} bps (0.50%).",
                    )
                )
                mitigations.append(f"Reduce slippage tolerance from {effective_slippage_bps} bps to ≤ {max_safe_slippage_bps} bps.")
            elif effective_slippage_bps > max_safe_slippage_bps:
                is_sandwich_vulnerable = True
                estimated_extractable_pct = round((effective_slippage_bps - max_safe_slippage_bps) / 100.0, 2)
                attack_vectors.append(
                    MEVAttackVector(
                        vector_type="ELEVATED_SLIPPAGE_TOLERANCE",
                        severity="WARNING",
                        description=(
                            f"Slippage tolerance of {effective_slippage_bps} bps exceeds recommended maximum of "
                            f"{max_safe_slippage_bps} bps."
                        ),
                        impact="Moderate vulnerability to two-sided sandwich exploitation.",
                        remediation=f"Set slippage to ≤ {max_safe_slippage_bps} bps or route via private Jito bundle.",
                    )
                )
                mitigations.append(f"Set slippage tolerance to ≤ {max_safe_slippage_bps} bps.")

        # 4. Check mempool privacy
        if is_public_mempool and (is_sandwich_vulnerable or effective_slippage_bps is None or effective_slippage_bps > 50):
            attack_vectors.append(
                MEVAttackVector(
                    vector_type="UNPROTECTED_PUBLIC_MEMPOOL",
                    severity="WARNING" if not is_sandwich_vulnerable else "CRITICAL",
                    description=(
                        "Transaction is targeted for public Solana validator gossip. Public mempool orders "
                        "are monitored by latency-optimized MEV searchers and Jito shred stream subscribers."
                    ),
                    impact="Order execution order can be manipulated via validator tip front-running.",
                    remediation="Route transaction through private Jito-Solana MEV bundle endpoint.",
                )
            )
            mitigations.append("Broadcast via Jito MEV bundle with dedicated tip instruction.")

        # 5. Check priority fee headroom relative to sandwich vulnerability
        if result.optimization and hasattr(result.optimization, "priority_fee_micro_lamports"):
            # If priority fee is 0 or minimal on a public DEX swap
            pass

    # Determine risk level
    if any(v.severity == "CRITICAL" for v in attack_vectors):
        risk_level = "CRITICAL"
    elif any(v.severity == "WARNING" for v in attack_vectors):
        risk_level = "HIGH" if is_public_mempool and is_sandwich_vulnerable else "MEDIUM"
    elif dex_detected:
        risk_level = "LOW" if is_public_mempool else "SAFE"
    else:
        risk_level = "SAFE"

    if not mitigations:
        if risk_level == "SAFE":
            mitigations.append("No MEV attack vectors detected. Standard execution safe.")
        else:
            mitigations.append("Maintain tight slippage and consider private RPC routing.")

    # Generate summary
    if risk_level == "CRITICAL":
        summary = (
            f"CRITICAL MEV RISK: Transaction exhibits severe vulnerability to sandwich attacks "
            f"across {', '.join(dex_names) or 'DEXs'}. Searchers can extract up to {estimated_extractable_pct:.2f}% value."
        )
    elif risk_level in ("HIGH", "MEDIUM"):
        summary = (
            f"{risk_level} MEV RISK: Elevated slippage or public mempool broadcast detected on "
            f"{', '.join(dex_names) or 'DEX swap'}. Recommend Jito bundle routing."
        )
    elif risk_level == "LOW":
        summary = (
            f"LOW MEV RISK: DEX swap detected with safe slippage parameters on {', '.join(dex_names) or 'DEX'}."
        )
    else:
        summary = "SAFE: No DEX liquidity pools or sandwich vulnerabilities identified."

    return MEVVulnerabilityReport(
        risk_level=risk_level,
        is_sandwich_vulnerable=is_sandwich_vulnerable,
        is_dex_swap=dex_detected,
        detected_slippage_bps=effective_slippage_bps,
        max_recommended_slippage_bps=max_safe_slippage_bps,
        estimated_extractable_mev_pct=estimated_extractable_pct,
        attack_vectors=attack_vectors,
        mitigations=mitigations,
        summary=summary,
    )

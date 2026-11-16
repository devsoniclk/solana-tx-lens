from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .optimizer import BASE_SIGNATURE_FEE_LAMPORTS, DEFAULT_PRIORITY_FEES_MICRO_LAMPORTS


@dataclass
class PriorityFeeTier:
    tier: str  # "min", "low", "medium", "high", "ultra", "extreme"
    percentile: int  # 25, 50, 75, 90, 99
    micro_lamports_per_cu: int
    total_fee_lamports: int
    total_fee_sol: float
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class JitoTipTier:
    tier: str  # "standard", "high_priority", "urgent_arbitrage", "sniper"
    tip_lamports: int
    tip_sol: float
    target_block_landing_prob: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class SolanaFeeGuide:
    tx_type: str  # "transfer", "dex_swap", "arbitrage", "nft_mint", "generic"
    estimated_cus: int
    recommended_cu_limit: int
    priority_fee_tiers: List[PriorityFeeTier] = field(default_factory=list)
    jito_tip_tiers: List[JitoTipTier] = field(default_factory=list)
    recommendation: str = ""
    cli_instructions: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# Micro-lamports per Compute Unit by tier
PRIORITY_TIER_CONFIG = [
    ("min", 25, 0, "No priority fee; base 5,000 lamport signature fee only. Prone to drop during congestion."),
    ("low", 50, 1_000, "1,000 micro-lamports/CU. Suitable for standard transfers during low network traffic."),
    ("medium", 75, 25_000, "25,000 micro-lamports/CU. Standard inclusion fee for typical DeFi interactions."),
    ("high", 90, 100_000, "100,000 micro-lamports/CU. Recommended for time-sensitive DEX swaps and liquidations."),
    ("ultra", 95, 500_000, "500,000 micro-lamports/CU. High-probability next-block landing during volatile market events."),
    ("extreme", 99, 2_000_000, "2,000,000 micro-lamports/CU. Maximum gas war bidding for competitive state access."),
]

# Jito Tip Tiers in lamports
JITO_TIP_CONFIG = [
    ("standard", 10_000, "80%", "0.00001 SOL tip. Normal bundle inclusion under steady leader schedule."),
    ("high_priority", 100_000, "95%", "0.0001 SOL tip. Priority bundle inclusion for DEX swaps and NFT buys."),
    ("urgent_arbitrage", 1_000_000, "99%", "0.001 SOL tip. Guaranteed landing for atomic arbitrage and liquidation loops."),
    ("sniper", 10_000_000, "99.9%", "0.01 SOL tip. Ultra-competitive meme coin launch / token pool sniping."),
]


def generate_fee_guide(
    estimated_cus: int = 200_000,
    tx_type: str = "dex_swap",
    is_bundle: bool = False,
    safety_buffer_pct: float = 0.15,
) -> SolanaFeeGuide:
    """
    Generates dynamic multi-tier priority fee and Jito MEV tip recommendations
    calibrated to transaction type, compute allocation, and target inclusion urgency.
    """
    if estimated_cus <= 0:
        estimated_cus = 200_000

    buffered = int(estimated_cus * (1.0 + safety_buffer_pct))
    recommended_limit = ((buffered + 999) // 1000) * 1000
    recommended_limit = max(1_000, min(recommended_limit, 1_400_000))

    priority_tiers: List[PriorityFeeTier] = []
    for tier_name, pctl, micro_lamports, desc in PRIORITY_TIER_CONFIG:
        p_fee_lamports = int((recommended_limit * micro_lamports) / 1_000_000)
        tot_lamports = BASE_SIGNATURE_FEE_LAMPORTS + p_fee_lamports
        priority_tiers.append(
            PriorityFeeTier(
                tier=tier_name,
                percentile=pctl,
                micro_lamports_per_cu=micro_lamports,
                total_fee_lamports=tot_lamports,
                total_fee_sol=round(tot_lamports / 1_000_000_000, 9),
                description=desc,
            )
        )

    jito_tiers: List[JitoTipTier] = []
    for tier_name, tip_lamports, prob, desc in JITO_TIP_CONFIG:
        jito_tiers.append(
            JitoTipTier(
                tier=tier_name,
                tip_lamports=tip_lamports,
                tip_sol=round(tip_lamports / 1_000_000_000, 9),
                target_block_landing_prob=prob,
                description=desc,
            )
        )

    # Tailor recommendation based on tx_type and bundle status
    if is_bundle:
        rec = (
            f"Atomic Jito Bundle configuration: Set compute limit to {recommended_limit:,} CUs with 0 priority fee. "
            f"Attach Jito tip instruction with tier 'high_priority' (0.0001 SOL) or 'urgent_arbitrage' (0.001 SOL)."
        )
        cli_inst = (
            f"# Web3 SDK Tip Transfer:\n"
            f"SystemProgram.transfer({{ fromPubkey: payer, toPubkey: JITO_TIP_ACCOUNT, lamports: 100_000 }})"
        )
    elif tx_type == "dex_swap":
        rec = (
            f"DEX Swap execution: Set ComputeUnitLimit to {recommended_limit:,} CUs. Use 'high' tier "
            f"(100,000 micro-lamports/CU = ~0.000025 SOL total) or private Jito bundle to prevent frontrunning."
        )
        cli_inst = (
            f"ComputeBudgetProgram.setComputeUnitLimit({{ units: {recommended_limit} }});\n"
            f"ComputeBudgetProgram.setComputeUnitPrice({{ microLamports: 100_000 }});"
        )
    elif tx_type == "arbitrage":
        rec = (
            f"Arbitrage loop: Set ComputeUnitLimit to {recommended_limit:,} CUs. Standard public mempool "
            f"broadcast will be frontrun; submit via Jito MEV bundle with >= 0.001 SOL tip."
        )
        cli_inst = (
            f"# Recommend Jito Bundle execution with 1,000,000 lamport tip to Jito leader."
        )
    elif tx_type == "nft_mint":
        rec = (
            f"NFT Mint / Competitive State: Set ComputeUnitLimit to {recommended_limit:,} CUs with 'ultra' "
            f"(500,000 micro-lamports/CU) to compete for block write locks."
        )
        cli_inst = (
            f"ComputeBudgetProgram.setComputeUnitLimit({{ units: {recommended_limit} }});\n"
            f"ComputeBudgetProgram.setComputeUnitPrice({{ microLamports: 500_000 }});"
        )
    else:
        rec = (
            f"Standard Transaction: Set ComputeUnitLimit to {recommended_limit:,} CUs with 'medium' "
            f"(25,000 micro-lamports/CU = ~0.000010 SOL total)."
        )
        cli_inst = (
            f"ComputeBudgetProgram.setComputeUnitLimit({{ units: {recommended_limit} }});\n"
            f"ComputeBudgetProgram.setComputeUnitPrice({{ microLamports: 25_000 }});"
        )

    return SolanaFeeGuide(
        tx_type=tx_type,
        estimated_cus=estimated_cus,
        recommended_cu_limit=recommended_limit,
        priority_fee_tiers=priority_tiers,
        jito_tip_tiers=jito_tiers,
        recommendation=rec,
        cli_instructions=cli_inst,
    )

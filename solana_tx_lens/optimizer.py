from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ComputeBudgetOptimization:
    simulated_cus: int
    recommended_limit: int
    safety_buffer_pct: float
    default_limit: int
    cu_savings: int
    cu_savings_pct: float
    priority_fee_micro_lamports: Dict[str, int]
    estimated_tx_fees_sol: Dict[str, float]
    recommendation_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# Default priority fee tiers in micro-lamports per compute unit
DEFAULT_PRIORITY_FEES_MICRO_LAMPORTS: Dict[str, int] = {
    "min": 0,
    "low": 1_000,       # 0.001 lamport / CU
    "medium": 25_000,   # 0.025 lamports / CU
    "high": 100_000,    # 0.1 lamports / CU
    "ultra": 500_000,   # 0.5 lamports / CU
}

BASE_SIGNATURE_FEE_LAMPORTS: int = 5_000  # Standard Solana signature fee


def optimize_compute_budget(
    simulated_cus: int,
    safety_buffer_pct: float = 0.15,
    default_limit: int = 200_000,
    max_allowed_cus: int = 1_400_000,
    custom_priority_fees: Optional[Dict[str, int]] = None,
) -> ComputeBudgetOptimization:
    """
    Computes the optimal ComputeBudget SetComputeUnitLimit and priority fee tiers
    for a simulated transaction.

    Solana transactions without SetComputeUnitLimit allocate 200,000 CUs (or 1.4M for
    versioned transactions requesting max). Right-sizing CU limits prevents overpaying
    priority fees and reduces block-space contention.
    """
    if simulated_cus <= 0:
        recommended = default_limit
    else:
        # Add safety buffer (default 15%) rounded up to nearest 1,000 CUs
        buffered = int(simulated_cus * (1.0 + safety_buffer_pct))
        rounded = ((buffered + 999) // 1000) * 1000
        # Clamp between 1,000 and max_allowed_cus
        recommended = max(1_000, min(rounded, max_allowed_cus))

    baseline = default_limit if simulated_cus <= default_limit else max_allowed_cus
    savings = max(0, baseline - recommended)
    savings_pct = round((savings / baseline) * 100.0, 2) if baseline > 0 else 0.0

    fee_tiers = dict(custom_priority_fees or DEFAULT_PRIORITY_FEES_MICRO_LAMPORTS)

    # Calculate total transaction fee in SOL for each priority tier:
    # Total Fee (lamports) = BASE (5,000) + (recommended_limit * micro_lamports / 1,000,000)
    tx_fees_sol: Dict[str, float] = {}
    for tier, micro_lamports in fee_tiers.items():
        priority_fee_lamports = int((recommended * micro_lamports) / 1_000_000)
        total_lamports = BASE_SIGNATURE_FEE_LAMPORTS + priority_fee_lamports
        tx_fees_sol[tier] = round(total_lamports / 1_000_000_000, 9)

    if simulated_cus <= 0:
        summary = "No compute units consumed. Using standard baseline limit."
    elif savings > 0:
        summary = (
            f"Optimize limit to {recommended:,} CUs (+{int(safety_buffer_pct*100)}% buffer). "
            f"Saves {savings:,} CUs ({savings_pct}%) vs {baseline:,} allocation."
        )
    else:
        summary = (
            f"Transaction consumed high compute ({simulated_cus:,} CUs). "
            f"Set limit to {recommended:,} CUs to prevent OutOfComputeUnits failure."
        )

    return ComputeBudgetOptimization(
        simulated_cus=simulated_cus,
        recommended_limit=recommended,
        safety_buffer_pct=safety_buffer_pct,
        default_limit=baseline,
        cu_savings=savings,
        cu_savings_pct=savings_pct,
        priority_fee_micro_lamports=fee_tiers,
        estimated_tx_fees_sol=tx_fees_sol,
        recommendation_summary=summary,
    )

from typing import List, Optional
from .models import HealthIssue, SimulationHealth, SimulationResult

COMPUTE_BUDGET_PROG = "ComputeBudget111111111111111111111111111111"


def assess_simulation_health(result: SimulationResult) -> SimulationHealth:
    """
    Performs automated pre-flight security, risk, and MEV sanity checks on a simulation result.
    Detects CU exhaustion, slippage failures, sandwich vulnerabilities, and rent issues.
    """
    issues: List[HealthIssue] = []
    has_critical = False

    # 1. Compute Unit Exhaustion & Headroom Check
    cu_util = (
        (result.total_compute_units / max(1, result.max_compute_units)) * 100.0
        if result.max_compute_units > 0
        else 0.0
    )

    if (
        result.total_compute_units >= result.max_compute_units
        and result.max_compute_units > 0
    ) or (result.error and result.error.name == "ComputationalBudgetExceeded"):
        issues.append(
            HealthIssue(
                check="CU_EXHAUSTION",
                severity="CRITICAL",
                message=(
                    f"Compute unit budget exhausted ({result.total_compute_units:,} / "
                    f"{result.max_compute_units:,} CUs). Transaction will fail on-chain."
                ),
                recommendation=(
                    "Prepend SetComputeUnitLimit instruction with higher CU allocation "
                    "(e.g., 400,000 - 1,400,000 CUs)."
                ),
            )
        )
        has_critical = True
    elif cu_util >= 85.0:
        issues.append(
            HealthIssue(
                check="CU_HEADROOM_WARNING",
                severity="WARNING",
                message=(
                    f"High CU utilization ({cu_util:.1f}%). Consumed "
                    f"{result.total_compute_units:,} of {result.max_compute_units:,} CUs."
                ),
                recommendation=(
                    "Add at least 15-20% CU headroom to prevent out-of-gas reverts caused "
                    "by dynamic state size variance under live network execution."
                ),
            )
        )

    # 2. Slippage & DEX Breaches
    if result.error and (
        result.error.name in ("SlippageExceeded", "ZeroAmount", "InsufficientLiquidity")
        or result.error.code in (6001, 0x1771)
        or "slippage" in (result.error.description or "").lower()
    ):
        issues.append(
            HealthIssue(
                check="SLIPPAGE_BREACH",
                severity="CRITICAL",
                message="DEX slippage tolerance exceeded; output tokens below minimum expected.",
                recommendation=(
                    "Refresh pool reserve quotes, increase slippage tolerance (bps), "
                    "or route through Jupiter multi-hop routing."
                ),
            )
        )
        has_critical = True

    # 3. Rent Exemption Violation
    if result.error and (
        result.error.name in ("InsufficientFundsForRent", "ConstraintRentExempt")
        or "rent" in (result.error.description or "").lower()
    ):
        issues.append(
            HealthIssue(
                check="RENT_EXEMPTION_VIOLATION",
                severity="CRITICAL",
                message="Account balance is below the required rent-exempt minimum threshold.",
                recommendation="Transfer sufficient SOL to cover rent-exemption for the account's allocated byte size.",
            )
        )
        has_critical = True

    # 4. Token Asymmetry / Potential Sandwich Attack Check
    if result.token_diffs:
        outflows = [d for d in result.token_diffs if d.delta < 0]
        inflows = [d for d in result.token_diffs if d.delta > 0]
        if outflows and not inflows and result.success:
            issues.append(
                HealthIssue(
                    check="ASYMMETRIC_TOKEN_OUTFLOW",
                    severity="WARNING",
                    message="Token outflow detected without counterparty token inflow in a successful swap/interaction.",
                    recommendation="Verify token destination account ownership and assert recipient balances.",
                )
            )

    # 5. Priority Fee Check
    has_cb = any(root.program_id == COMPUTE_BUDGET_PROG for root in result.cpi_roots)
    if not has_cb:
        issues.append(
            HealthIssue(
                check="PRIORITY_FEE_ADVISORY",
                severity="INFO",
                message="No Compute Budget priority fee instruction detected in transaction.",
                recommendation=(
                    "Include SetComputeUnitPrice to prioritize bundle inclusion during network congestion "
                    "and protect against MEV searcher reordering."
                ),
            )
        )

    if has_critical or not result.success:
        overall_status = "CRITICAL_FAILURE"
    elif any(iss.severity == "WARNING" for iss in issues):
        overall_status = "WARNING"
    else:
        overall_status = "HEALTHY"

    return SimulationHealth(
        status=overall_status,
        cu_utilization_pct=round(cu_util, 2),
        issues=issues,
        has_critical_failure=has_critical,
    )

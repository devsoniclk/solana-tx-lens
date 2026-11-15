from solana_tx_lens.guard import assess_simulation_health
from solana_tx_lens.models import (
    CPIInvocation,
    ErrorInfo,
    SimulationResult,
    TokenBalanceDiff,
)


def test_guard_healthy_simulation():
    res = SimulationResult(
        success=True,
        total_compute_units=45_000,
        max_compute_units=200_000,
        cpi_roots=[
            CPIInvocation(program_id="ComputeBudget111111111111111111111111111111", depth=1),
            CPIInvocation(program_id="11111111111111111111111111111111", depth=1),
        ],
        account_diffs=[],
    )
    health = assess_simulation_health(res)
    assert health.status == "HEALTHY"
    assert not health.has_critical_failure
    assert health.cu_utilization_pct == 22.5


def test_guard_cu_headroom_warning():
    res = SimulationResult(
        success=True,
        total_compute_units=185_000,
        max_compute_units=200_000,
        cpi_roots=[
            CPIInvocation(program_id="ComputeBudget111111111111111111111111111111", depth=1),
        ],
        account_diffs=[],
    )
    health = assess_simulation_health(res)
    assert health.status == "WARNING"
    assert any(iss.check == "CU_HEADROOM_WARNING" for iss in health.issues)


def test_guard_cu_exhaustion_critical():
    res = SimulationResult(
        success=False,
        total_compute_units=200_000,
        max_compute_units=200_000,
        cpi_roots=[],
        account_diffs=[],
        error=ErrorInfo(
            error_type="ComputeBudget",
            code=0,
            name="ComputationalBudgetExceeded",
            description="Exceeded CUs",
        ),
    )
    health = assess_simulation_health(res)
    assert health.status == "CRITICAL_FAILURE"
    assert health.has_critical_failure
    assert any(iss.check == "CU_EXHAUSTION" for iss in health.issues)


def test_guard_slippage_breach():
    res = SimulationResult(
        success=False,
        total_compute_units=30_000,
        max_compute_units=200_000,
        cpi_roots=[],
        account_diffs=[],
        error=ErrorInfo(
            error_type="Custom",
            code=6001,
            name="SlippageExceeded",
            description="Slippage tolerance exceeded",
        ),
    )
    health = assess_simulation_health(res)
    assert health.status == "CRITICAL_FAILURE"
    assert any(iss.check == "SLIPPAGE_BREACH" for iss in health.issues)


def test_guard_asymmetric_token_outflow():
    res = SimulationResult(
        success=True,
        total_compute_units=50_000,
        max_compute_units=200_000,
        cpi_roots=[
            CPIInvocation(program_id="ComputeBudget111111111111111111111111111111", depth=1),
        ],
        account_diffs=[],
        token_diffs=[
            TokenBalanceDiff(
                account="Acc1",
                mint="USDC",
                owner="Owner1",
                pre_amount=100.0,
                post_amount=50.0,
                delta=-50.0,
                decimals=6,
            )
        ],
    )
    health = assess_simulation_health(res)
    assert health.status == "WARNING"
    assert any(iss.check == "ASYMMETRIC_TOKEN_OUTFLOW" for iss in health.issues)

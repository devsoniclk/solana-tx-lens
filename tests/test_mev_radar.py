import pytest
from solana_tx_lens.mev_radar import scan_mev_vulnerabilities
from solana_tx_lens.models import CPIInvocation, ErrorInfo, SimulationResult, TokenBalanceDiff


def test_mev_radar_safe_non_dex():
    res = SimulationResult(
        success=True,
        total_compute_units=15_000,
        max_compute_units=200_000,
        cpi_roots=[
            CPIInvocation(
                program_id="11111111111111111111111111111111",
                depth=1,
                program_name="System Program",
                instruction_name="Transfer",
                consumed_cus=500,
            )
        ],
        account_diffs=[],
    )
    radar = scan_mev_vulnerabilities(res)
    assert radar.risk_level == "SAFE"
    assert not radar.is_sandwich_vulnerable
    assert not radar.is_dex_swap


def test_mev_radar_critical_slippage_exposure():
    res = SimulationResult(
        success=True,
        total_compute_units=120_000,
        max_compute_units=200_000,
        cpi_roots=[
            CPIInvocation(
                program_id="675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium AMM
                depth=1,
                program_name="Raydium AMM v4",
                instruction_name="SwapBaseIn",
                consumed_cus=85_000,
            )
        ],
        account_diffs=[],
        token_diffs=[
            TokenBalanceDiff(
                account="AccA",
                mint="So11111111111111111111111111111111111111112",
                owner="User",
                pre_amount=5.0,
                post_amount=4.0,
                delta=-1.0,
                decimals=9,
                symbol="SOL",
            ),
            TokenBalanceDiff(
                account="AccB",
                mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                owner="User",
                pre_amount=100.0,
                post_amount=320.0,
                delta=220.0,
                decimals=6,
                symbol="USDC",
            ),
        ],
        raw_logs=["Program log: Raydium swap with slippage bps: 400"],
    )
    radar = scan_mev_vulnerabilities(res, slippage_tolerance_bps=400, is_public_mempool=True)
    assert radar.risk_level == "CRITICAL"
    assert radar.is_sandwich_vulnerable
    assert radar.is_dex_swap
    assert radar.detected_slippage_bps == 400
    assert radar.estimated_extractable_mev_pct > 0.0
    assert any(v.vector_type == "CRITICAL_SLIPPAGE_EXPOSURE" for v in radar.attack_vectors)
    assert any("Jito" in m for m in radar.mitigations)


def test_mev_radar_slippage_error_breach():
    res = SimulationResult(
        success=False,
        total_compute_units=65_000,
        max_compute_units=200_000,
        cpi_roots=[],
        account_diffs=[],
        error=ErrorInfo(
            error_type="Custom",
            code=6001,
            name="SlippageToleranceExceeded",
            description="Exceeded maximum allowable slippage limit",
            program_id="whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
        ),
    )
    radar = scan_mev_vulnerabilities(res)
    assert radar.risk_level == "CRITICAL"
    assert any(v.vector_type == "SLIPPAGE_BREACH" for v in radar.attack_vectors)

from __future__ import annotations

from solana_tx_lens.contention import audit_account_contention
from solana_tx_lens.html_report import render_html_report
from solana_tx_lens.models import AccountDiff, CPIInvocation, SimulationResult, TokenBalanceDiff
from solana_tx_lens.optimizer import optimize_compute_budget


def test_render_html_report_contains_key_elements():
    cpi = CPIInvocation(
        program_id="JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
        depth=1,
        program_name="Jupiter Aggregator v6",
        instruction_name="sharedAccountsRoute",
        consumed_cus=45_000,
    )
    acc_diff = AccountDiff(
        pubkey="UserWallet111111111111111111111111111111111",
        pre_lamports=1_000_000_000,
        post_lamports=995_000_000,
        lamports_delta=-5_000_000,
        pre_owner="11111111111111111111111111111111",
        post_owner="11111111111111111111111111111111",
        data_len_delta=0,
    )
    tok_diff = TokenBalanceDiff(
        account="TokenAccount1111111111111111111111111111111",
        mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        owner="UserWallet111111111111111111111111111111111",
        pre_amount=100.0,
        post_amount=150.0,
        delta=50.0,
        decimals=6,
        symbol="USDC",
    )
    res = SimulationResult(
        success=True,
        total_compute_units=45_000,
        max_compute_units=200_000,
        cpi_roots=[cpi],
        account_diffs=[acc_diff],
        token_diffs=[tok_diff],
        raw_logs=["Program JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4 invoke [1]"],
    )

    opt = optimize_compute_budget(45_000)
    cnt = audit_account_contention([
        {"pubkey": "UserWallet111111111111111111111111111111111", "signer": True, "writable": True},
    ])

    html_str = render_html_report(res, optimization=opt, contention=cnt)
    assert "<!DOCTYPE html>" in html_str
    assert "SIMULATION PASSED" in html_str
    assert "Jupiter Aggregator v6" in html_str
    assert "sharedAccountsRoute" in html_str
    assert "Compute Budget & Priority Fee Optimization" in html_str
    assert "Account Write-Lock Contention & Parallelism" in html_str
    assert "USDC" in html_str
    assert "sequenceDiagram" in html_str


def test_simulation_result_to_html_method():
    res = SimulationResult(
        success=True,
        total_compute_units=12_000,
        max_compute_units=200_000,
        cpi_roots=[],
        account_diffs=[],
    )
    html_out = res.to_html(title="Custom Title Test")
    assert "Custom Title Test" in html_out
    assert "<!DOCTYPE html>" in html_out

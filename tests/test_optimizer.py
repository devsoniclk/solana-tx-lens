from __future__ import annotations

from solana_tx_lens.optimizer import optimize_compute_budget


def test_optimize_compute_budget_baseline():
    opt = optimize_compute_budget(simulated_cus=45_000, safety_buffer_pct=0.15)
    # 45,000 * 1.15 = 51,750 -> rounded to nearest 1000 is 52,000
    assert opt.simulated_cus == 45_000
    assert opt.recommended_limit == 52_000
    assert opt.default_limit == 200_000
    assert opt.cu_savings == 148_000
    assert opt.cu_savings_pct == 74.0
    assert "medium" in opt.priority_fee_micro_lamports
    assert "medium" in opt.estimated_tx_fees_sol
    assert opt.estimated_tx_fees_sol["min"] == 0.000005  # Base 5000 lamports = 0.000005 SOL


def test_optimize_compute_budget_high_compute():
    opt = optimize_compute_budget(simulated_cus=350_000, safety_buffer_pct=0.10)
    # 350_000 * 1.10 = 385,000
    assert opt.recommended_limit == 385_000
    assert opt.default_limit == 1_400_000
    assert opt.cu_savings == 1_015_000
    assert opt.cu_savings_pct == 72.5


def test_optimize_compute_budget_zero_cus():
    opt = optimize_compute_budget(simulated_cus=0)
    assert opt.recommended_limit == 200_000
    assert opt.cu_savings == 0

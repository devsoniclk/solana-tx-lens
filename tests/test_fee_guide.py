import pytest
from solana_tx_lens.fee_guide import generate_fee_guide


def test_generate_fee_guide_dex_swap():
    guide = generate_fee_guide(estimated_cus=120_000, tx_type="dex_swap")
    assert guide.tx_type == "dex_swap"
    assert guide.estimated_cus == 120_000
    assert guide.recommended_cu_limit == 138_000  # 120k * 1.15 = 138k
    assert len(guide.priority_fee_tiers) == 6
    assert len(guide.jito_tip_tiers) == 4

    # High tier should be present
    high_tier = next(t for t in guide.priority_fee_tiers if t.tier == "high")
    assert high_tier.micro_lamports_per_cu == 100_000
    assert high_tier.total_fee_sol > 0

    assert "DEX Swap execution" in guide.recommendation
    assert "ComputeBudgetProgram.setComputeUnitLimit" in guide.cli_instructions


def test_generate_fee_guide_bundle():
    guide = generate_fee_guide(estimated_cus=80_000, is_bundle=True)
    assert "Atomic Jito Bundle" in guide.recommendation
    assert "SystemProgram.transfer" in guide.cli_instructions
    urgent_tip = next(t for t in guide.jito_tip_tiers if t.tier == "urgent_arbitrage")
    assert urgent_tip.tip_sol == 0.001


def test_generate_fee_guide_arbitrage():
    guide = generate_fee_guide(estimated_cus=250_000, tx_type="arbitrage")
    assert "Arbitrage loop" in guide.recommendation
    assert guide.recommended_cu_limit == 288_000  # 250k * 1.15 = 287.5k -> 288k

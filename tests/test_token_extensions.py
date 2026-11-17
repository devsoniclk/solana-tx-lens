from __future__ import annotations

from solana_tx_lens.token_extensions import (
    TOKEN_2022_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    calculate_transfer_fee,
    inspect_token_extensions,
)


def test_calculate_transfer_fee():
    # 100 bps = 1.0%
    assert calculate_transfer_fee(10_000, 100, 500) == 100
    # Capped by maximum_fee
    assert calculate_transfer_fee(100_000, 100, 50) == 50
    # Zero fee
    assert calculate_transfer_fee(10_000, 0, 500) == 0
    # Zero amount
    assert calculate_transfer_fee(0, 100, 500) == 0


def test_inspect_legacy_token():
    rep = inspect_token_extensions(
        mint="So11111111111111111111111111111111111111112",
        program_id=TOKEN_PROGRAM_ID,
    )
    assert not rep.is_token_2022
    assert rep.risk_rating == "LOW"
    assert len(rep.detected_extensions) == 0


def test_inspect_token_2022_transfer_fee():
    extensions = [
        {
            "type": "TransferFeeConfig",
            "fee_basis_points": 250,  # 2.5%
            "maximum_fee": 10_000_000,  # 10 tokens cap in raw units (decimals=6)
            "withholding_account": "Withhold111111111111111111111111111111111",
        }
    ]
    rep = inspect_token_extensions(
        mint="Token2022Mint11111111111111111111111111111",
        program_id=TOKEN_2022_PROGRAM_ID,
        account_data_extensions=extensions,
        transfer_amount=100.0,
        decimals=6,
    )
    assert rep.is_token_2022
    assert rep.transfer_fee is not None
    assert rep.transfer_fee.fee_basis_points == 250
    assert rep.gross_transfer_amount == 100.0
    assert rep.fee_deducted == 2.5
    assert rep.net_transfer_amount == 97.5
    assert rep.risk_score >= 10


def test_inspect_token_2022_transfer_fee_capped():
    extensions = [
        {
            "type": "TransferFeeConfig",
            "fee_basis_points": 250,  # 2.5% = 2.5 tokens
            "maximum_fee": 100_000,  # Capped at 0.1 tokens (100,000 raw units with 6 decimals)
            "withholding_account": "Withhold111111111111111111111111111111111",
        }
    ]
    rep = inspect_token_extensions(
        mint="Token2022Mint11111111111111111111111111111",
        program_id=TOKEN_2022_PROGRAM_ID,
        account_data_extensions=extensions,
        transfer_amount=100.0,
        decimals=6,
    )
    assert rep.is_token_2022
    assert rep.fee_deducted == 0.1
    assert rep.net_transfer_amount == 99.9


def test_inspect_token_2022_transfer_hook_with_logs():
    extensions = [
        {
            "type": "TransferHook",
            "program_id": "HookProg1111111111111111111111111111111111",
        }
    ]
    logs = [
        "Program TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb invoke [1]",
        "Program HookProg1111111111111111111111111111111111 invoke [2]",
        "TransferHook: validation successful",
        "Program HookProg1111111111111111111111111111111111 success",
        "Program TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb success",
    ]
    rep = inspect_token_extensions(
        mint="HookMint11111111111111111111111111111111111",
        account_data_extensions=extensions,
        simulation_logs=logs,
    )
    assert rep.transfer_hook is not None
    assert rep.transfer_hook.invoked
    assert rep.transfer_hook.success


def test_inspect_token_2022_permanent_delegate_critical():
    extensions = [
        {
            "type": "PermanentDelegate",
            "delegate": "BadActorDelegate1111111111111111111111111111",
        }
    ]
    rep = inspect_token_extensions(
        mint="DangerousMint111111111111111111111111111111",
        account_data_extensions=extensions,
    )
    assert rep.risk_rating in ("HIGH", "CRITICAL")
    assert any(e.extension_type == "PermanentDelegate" for e in rep.detected_extensions)


def test_inspect_token_2022_soulbound_and_frozen():
    extensions = [
        {"type": "NonTransferable"},
        {"type": "DefaultAccountState", "state": "Frozen"},
    ]
    rep = inspect_token_extensions(
        mint="SoulboundMint111111111111111111111111111111",
        account_data_extensions=extensions,
    )
    assert rep.risk_score >= 60
    assert rep.risk_rating == "CRITICAL"

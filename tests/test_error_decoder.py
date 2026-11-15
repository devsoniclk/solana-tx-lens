from solana_tx_lens.error_decoder import decode_solana_error


def test_decode_anchor_standard_error():
    err = decode_solana_error("InstructionError(0, Custom(200))")
    assert err.error_type == "Anchor"
    assert err.code == 200
    assert err.name == "ConstraintMut"
    assert "mut constraint" in err.description


def test_decode_dex_slippage_error_numeric():
    err = decode_solana_error("InstructionError(1, Custom(6001))")
    assert err.error_type == "DEX"
    assert err.code == 6001
    assert err.name == "SlippageExceeded"
    assert "Slippage tolerance" in err.description


def test_decode_dex_slippage_error_hex():
    # 0x1771 == 6001
    err = decode_solana_error("custom program error: 0x1771")
    assert err.error_type == "DEX"
    assert err.code == 6001
    assert err.name == "SlippageExceeded"


def test_decode_native_compute_budget_error():
    err = decode_solana_error("Program failed to complete: ComputationalBudgetExceeded")
    assert err.error_type == "Native"
    assert err.name == "ComputationalBudgetExceeded"
    assert "compute unit limit was exceeded" in err.description

from solana_tx_lens.instruction_decoder import extract_instruction_name, get_program_label


def test_get_program_label():
    assert get_program_label("11111111111111111111111111111111") == "System Program"
    assert get_program_label("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA") == "SPL Token"
    assert get_program_label("675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8") == "Raydium AMM v4"
    assert get_program_label("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P") == "Pump.fun"
    # Unknown long address should be shortened
    shortened = get_program_label("ComputeBudget111111111111111111111111111111")
    assert shortened == "Compute Budget"
    unknown = get_program_label("MyCustomProgramPubkeyAddress123456789ABCDEF")
    assert "..." in unknown


def test_extract_instruction_name():
    logs = [
        "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke [2]",
        "Program log: Instruction: TransferChecked",
        "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA success",
    ]
    assert extract_instruction_name(logs) == "TransferChecked"

    raydium_logs = [
        "Program 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 invoke [1]",
        "Program log: initialize2: InitializeInstruction2",
    ]
    assert extract_instruction_name(raydium_logs) == "initialize2"

    pump_logs = [
        "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P invoke [1]",
        "Program log: buy: Slippage 500",
    ]
    assert extract_instruction_name(pump_logs) == "buy"

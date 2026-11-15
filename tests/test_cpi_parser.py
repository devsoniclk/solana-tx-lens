from solana_tx_lens.cpi_parser import parse_cpi_tree


SAMPLE_LOGS = [
    "Program 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 invoke [1]",
    "Program log: initialize2: InitializeInstruction2",
    "Program 11111111111111111111111111111111 invoke [2]",
    "Program 11111111111111111111111111111111 success",
    "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke [2]",
    "Program log: Instruction: Transfer",
    "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA consumed 4645 of 185000 compute units",
    "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA success",
    "Program 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 consumed 32415 of 200000 compute units",
    "Program 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 success",
]


def test_parse_cpi_tree_nested_structure():
    roots = parse_cpi_tree(SAMPLE_LOGS)
    assert len(roots) == 1

    root = roots[0]
    assert root.program_id == "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
    assert root.depth == 1
    assert root.consumed_cus == 32415
    assert not root.failed

    # Check children (depth 2)
    assert len(root.children) == 2
    assert root.children[0].program_id == "11111111111111111111111111111111"
    assert root.children[0].depth == 2

    assert root.children[1].program_id == "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
    assert root.children[1].depth == 2
    assert root.children[1].consumed_cus == 4645


def test_parse_cpi_tree_failure():
    failing_logs = [
        "Program JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4 invoke [1]",
        "Program 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 invoke [2]",
        "Program 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 failed: custom program error: 0x1771",
        "Program JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4 failed: custom program error: 0x1771",
    ]
    roots = parse_cpi_tree(failing_logs)
    assert len(roots) == 1
    root = roots[0]
    assert root.failed

    child = root.children[0]
    assert child.failed
    assert "0x1771" in child.error_message

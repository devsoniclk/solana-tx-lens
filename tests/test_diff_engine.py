from solana_tx_lens.diff_engine import (
    compute_account_diffs,
    compute_token_diffs,
    parse_token_transfers_from_logs,
)


def test_compute_account_diffs_lamport_transfer():
    pre = [{"pubkey": "AccountA", "lamports": 1_000_000_000, "owner": "11111111111111111111111111111111"}]
    post = [{"pubkey": "AccountA", "lamports": 900_000_000, "owner": "11111111111111111111111111111111"}]

    diffs = compute_account_diffs(pre, post)
    assert len(diffs) == 1
    assert diffs[0].pubkey == "AccountA"
    assert diffs[0].lamports_delta == -100_000_000


def test_compute_token_diffs_pre_post():
    pre = [
        {
            "account": "TokenAcc1",
            "mint": "USDC_MINT",
            "owner": "OwnerX",
            "uiTokenAmount": {"uiAmount": 250.0, "decimals": 6},
        }
    ]
    post = [
        {
            "account": "TokenAcc1",
            "mint": "USDC_MINT",
            "owner": "OwnerX",
            "uiTokenAmount": {"uiAmount": 100.0, "decimals": 6},
        },
        {
            "account": "TokenAcc2",
            "mint": "SOL_MINT",
            "owner": "OwnerX",
            "uiTokenAmount": {"uiAmount": 1.25, "decimals": 9},
        },
    ]

    diffs = compute_token_diffs(pre, post)
    assert len(diffs) == 2

    # Verify deltas
    diff_map = {d.account: d for d in diffs}
    assert diff_map["TokenAcc1"].delta == -150.0
    assert diff_map["TokenAcc1"].decimals == 6

    assert diff_map["TokenAcc2"].delta == 1.25
    assert diff_map["TokenAcc2"].decimals == 9


def test_parse_token_transfers_from_logs():
    logs = [
        "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke [2]",
        "Program log: Instruction: TransferChecked: 15000000",
        "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA success",
    ]
    transfers = parse_token_transfers_from_logs(logs)
    assert len(transfers) == 1
    assert transfers[0].delta == 15000000.0

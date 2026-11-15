from solana_tx_lens.diff_engine import compute_account_diffs


def test_compute_account_diffs_lamport_transfer():
    pre = [
        {"pubkey": "User11111111111111111111111111111111111111", "lamports": 1_000_000_000, "owner": "11111111111111111111111111111111"},
        {"pubkey": "Vault2222222222222222222222222222222222222", "lamports": 500_000_000, "owner": "11111111111111111111111111111111"},
    ]
    post = [
        {"pubkey": "User11111111111111111111111111111111111111", "lamports": 800_000_000, "owner": "11111111111111111111111111111111"},
        {"pubkey": "Vault2222222222222222222222222222222222222", "lamports": 700_000_000, "owner": "11111111111111111111111111111111"},
    ]

    diffs = compute_account_diffs(pre, post)
    assert len(diffs) == 2

    user_diff = next(d for d in diffs if d.pubkey.startswith("User"))
    assert user_diff.lamports_delta == -200_000_000

    vault_diff = next(d for d in diffs if d.pubkey.startswith("Vault"))
    assert vault_diff.lamports_delta == +200_000_000

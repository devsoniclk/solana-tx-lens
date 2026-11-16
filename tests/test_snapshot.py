from __future__ import annotations

import base64
from solana_tx_lens.snapshot import (
    ShadowStateReplayer,
    calculate_rent_exempt_reserve,
    create_account_snapshot_delta,
)


def test_rent_exempt_reserve_calculation():
    # 0 data len: (128 + 0) * 3480 * 2 = 890,880 lamports (~0.00089 SOL)
    reserve_0 = calculate_rent_exempt_reserve(0)
    assert reserve_0 == 890880

    # 165 bytes (SPL Token Account): (128 + 165) * 3480 * 2 = 2,039,280 lamports (~0.002039 SOL)
    reserve_spl = calculate_rent_exempt_reserve(165)
    assert reserve_spl == 2039280


def test_account_creation_diff():
    post = {
        "pubkey": "NewAcct111111111111111111111111111111111111",
        "lamports": 5_000_000,
        "owner": "11111111111111111111111111111111",
        "data": base64.b64encode(b"hello world").decode("utf-8"),
        "executable": False,
    }

    summary = create_account_snapshot_delta([], [post])
    assert summary.total_accounts_touched == 1
    assert summary.accounts_created == 1
    assert summary.accounts_closed == 0
    assert summary.total_lamports_delta == 5_000_000
    assert summary.total_bytes_delta == len(b"hello world")
    assert summary.account_deltas[0].is_rent_exempt is True


def test_account_closure_diff():
    pre = {
        "pubkey": "ClosingAcct1111111111111111111111111111111",
        "lamports": 2_039_280,
        "owner": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "data": base64.b64encode(b"\x00" * 165).decode("utf-8"),
    }
    post = {
        "pubkey": "ClosingAcct1111111111111111111111111111111",
        "lamports": 0,
        "owner": "11111111111111111111111111111111",
        "data": "",
    }

    summary = create_account_snapshot_delta([pre], [post])
    assert summary.accounts_closed == 1
    assert summary.total_lamports_delta == -2_039_280
    assert summary.account_deltas[0].owner_changed is True
    assert summary.account_deltas[0].data_len_delta == -165


def test_rent_exempt_violation_detection():
    # Account has 100 bytes data but only 10,000 lamports (far below rent exemption)
    post = {
        "pubkey": "Underfunded1111111111111111111111111111111",
        "lamports": 10_000,
        "owner": "11111111111111111111111111111111",
        "data": base64.b64encode(b"\xaa" * 100).decode("utf-8"),
    }

    summary = create_account_snapshot_delta([], [post])
    assert len(summary.rent_exempt_violations) == 1
    assert "Underfunded" in summary.rent_exempt_violations[0]


def test_shadow_state_replayer_transitions():
    replayer = ShadowStateReplayer()
    acc1 = {"pubkey": "AcctA", "lamports": 1000, "data": ""}
    acc2 = {"pubkey": "AcctB", "lamports": 2000, "data": ""}

    replayer.apply_transition([acc1, acc2])
    assert replayer.get_account("AcctA")["lamports"] == 1000

    # Step 2: update AcctA
    acc1_v2 = {"pubkey": "AcctA", "lamports": 1500, "data": ""}
    replayer.apply_transition([acc1_v2])
    assert replayer.get_account("AcctA")["lamports"] == 1500

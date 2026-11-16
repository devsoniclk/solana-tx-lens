from __future__ import annotations

import json
from solana_tx_lens.bundle import (
    JITO_TIP_ACCOUNTS,
    BundleSimulator,
    JitoTipAnalysis,
)


def test_empty_bundle():
    sim = BundleSimulator()
    res = sim.simulate_bundle([])
    assert res.success is True
    assert res.transaction_count == 0
    assert res.total_compute_units == 0


def test_atomic_successful_bundle():
    sim = BundleSimulator()
    tx1 = {
        "unitsConsumed": 25000,
        "logs": [
            "Program 11111111111111111111111111111111 invoke [1]",
            "Program 11111111111111111111111111111111 success",
        ],
        "preAccounts": [
            {"pubkey": "UserAccount1111111111111111111111111111111", "lamports": 5000000000, "owner": "11111111111111111111111111111111", "data": ""},
        ],
        "accounts": [
            {"pubkey": "UserAccount1111111111111111111111111111111", "lamports": 4900000000, "owner": "11111111111111111111111111111111", "data": "", "writable": True},
        ],
    }
    tx2 = {
        "unitsConsumed": 45000,
        "logs": [
            "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke [1]",
            "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA success",
        ],
        "preTokenBalances": [
            {"accountIndex": 0, "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "owner": "UserOwner", "uiTokenAmount": {"uiAmount": 100.0, "decimals": 6}},
        ],
        "postTokenBalances": [
            {"accountIndex": 0, "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "owner": "UserOwner", "uiTokenAmount": {"uiAmount": 250.0, "decimals": 6}},
        ],
    }

    res = sim.simulate_bundle([tx1, tx2])
    assert res.success is True
    assert res.transaction_count == 2
    assert res.total_compute_units == 70000
    assert res.reverted_at_index is None
    assert len(res.cumulative_account_diffs) == 1
    assert res.cumulative_account_diffs[0].lamports_delta == -100000000
    assert len(res.cumulative_token_diffs) == 1
    assert res.cumulative_token_diffs[0].delta == 150.0

    # Ensure export methods work
    d = res.to_dict()
    assert d["transaction_count"] == 2
    j = res.to_json()
    assert "70,000" in res.summary or "70000" in j
    html = res.to_html()
    assert "ATOMIC BUNDLE PASSED" in html


def test_bundle_revert_atomicity():
    sim = BundleSimulator()
    tx_ok = {
        "unitsConsumed": 15000,
        "logs": ["Program 11111111111111111111111111111111 invoke [1]", "Program 11111111111111111111111111111111 success"],
    }
    tx_fail = {
        "unitsConsumed": 30000,
        "err": {"InstructionError": [0, {"Custom": 6001}]},
        "logs": [
            "Program JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4 invoke [1]",
            "Program log: AnchorError thrown: Slippage tolerance exceeded",
            "Program JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4 failed: custom program error: 0x1771",
        ],
    }

    res = sim.simulate_bundle([tx_ok, tx_fail])
    assert res.success is False
    assert res.reverted_at_index == 1
    assert "reverted" in res.summary.lower()
    assert res.total_compute_units == 45000


def test_jito_tip_detection():
    sim = BundleSimulator()
    jito_acc = "96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5"
    assert jito_acc in JITO_TIP_ACCOUNTS

    tip_tx = {
        "unitsConsumed": 12000,
        "logs": [
            "Program 11111111111111111111111111111111 invoke [1]",
            "Program 11111111111111111111111111111111 success",
        ],
        "preAccounts": [
            {"pubkey": jito_acc, "lamports": 100000000, "owner": "11111111111111111111111111111111", "data": ""},
        ],
        "accounts": [
            {"pubkey": jito_acc, "lamports": 110000000, "owner": "11111111111111111111111111111111", "data": ""},
        ],
    }

    res = sim.simulate_bundle([tip_tx])
    assert res.success is True
    assert res.jito_tip.is_valid_jito_tip is True
    assert res.jito_tip.tip_account == jito_acc
    assert res.jito_tip.tip_lamports == 10000000
    assert abs(res.jito_tip.tip_sol - 0.01) < 1e-6
    assert res.jito_tip.tip_tier == "high"


def test_cross_transaction_contention_warning():
    sim = BundleSimulator()
    hot_account = "HotLiquidityPoolAccount1111111111111111111"
    tx1 = {
        "unitsConsumed": 20000,
        "logs": [],
        "accounts": [
            {"pubkey": hot_account, "writable": True, "signer": False},
        ],
    }
    tx2 = {
        "unitsConsumed": 20000,
        "logs": [],
        "accounts": [
            {"pubkey": hot_account, "writable": True, "signer": False},
        ],
    }

    res = sim.simulate_bundle([tx1, tx2])
    assert len(res.bundle_contention_warnings) >= 1
    assert "Cross-Tx Write Lock Collision" in res.bundle_contention_warnings[0]

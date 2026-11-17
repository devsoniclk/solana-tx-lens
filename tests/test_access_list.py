from __future__ import annotations

from solana_tx_lens.access_list import (
    MAX_TX_BYTE_SIZE,
    analyze_access_list,
    estimate_tx_serialized_size,
)


def test_estimate_tx_serialized_size():
    keys = ["Account" + str(i).zfill(25) for i in range(10)]
    stats = estimate_tx_serialized_size(keys, signatures_count=1, instructions_data_bytes=100)
    assert stats.within_mtu_limit
    assert stats.estimated_serialized_bytes > 300
    assert stats.remaining_bytes == MAX_TX_BYTE_SIZE - stats.estimated_serialized_bytes


def test_analyze_access_list_clean():
    keys = [
        "Signer1111111111111111111111111111111111111",
        "WritableAcc111111111111111111111111111111111",
        "ReadOnlyAcc111111111111111111111111111111111",
    ]
    rep = analyze_access_list(
        keys,
        writable_indices=[0, 1],
        signer_indices=[0],
    )
    assert rep.total_accounts == 3
    assert len(rep.write_locks) == 2
    assert len(rep.read_locks) == 1
    assert len(rep.signers) == 1
    assert rep.concurrency_score == 100
    assert len(rep.lock_anti_patterns) == 0


def test_analyze_access_list_anti_pattern_program_writable():
    # Marking Tokenkeg program as writable is a severe anti-pattern
    keys = [
        "Signer1111111111111111111111111111111111111",
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    ]
    rep = analyze_access_list(
        keys,
        writable_indices=[0, 1],
        signer_indices=[0],
    )
    assert rep.concurrency_score < 100
    assert len(rep.lock_anti_patterns) > 0
    assert any("Tokenkeg" in p or "WRITABLE" in p for p in rep.lock_anti_patterns)


def test_analyze_access_list_lut_recommendation():
    # Many read-only accounts should trigger an Address Lookup Table recommendation
    keys = ["Signer1111111111111111111111111111111111111"] + [
        f"StaticReadOnlyKey{i:020d}" for i in range(5)
    ]
    rep = analyze_access_list(
        keys,
        writable_indices=[0],
        signer_indices=[0],
    )
    assert rep.lut_recommendation is not None
    assert len(rep.lut_recommendation.candidate_pubkeys) == 5
    assert rep.lut_recommendation.bytes_saved > 0

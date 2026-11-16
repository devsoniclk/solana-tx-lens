from __future__ import annotations

from solana_tx_lens.contention import audit_account_contention


def test_audit_account_contention_parallelizable():
    accounts = [
        {"pubkey": "Sender1111111111111111111111111111111111111", "signer": True, "writable": True},
        {"pubkey": "Receiver1111111111111111111111111111111111", "signer": False, "writable": True},
        {"pubkey": "11111111111111111111111111111111", "signer": False, "writable": False},  # System Program
        {"pubkey": "SysvarRent111111111111111111111111111111111", "signer": False, "writable": False},
    ]
    report = audit_account_contention(accounts)
    assert report.total_accounts == 4
    assert report.writable_count == 2
    assert report.readonly_count == 2
    assert report.hotspot_count == 0
    assert report.concurrency_verdict in ("HIGHLY_PARALLELIZABLE", "MODERATE_CONTENTION")
    assert report.parallelizability_score > 0.50
    assert len(report.warnings) == 0


def test_audit_account_contention_hotspot_sysvar_writable():
    # Dangerous: marking Sysvar as writable
    accounts = [
        {"pubkey": "SysvarC1ock11111111111111111111111111111111", "signer": False, "writable": True},
        {"pubkey": "UserAccount11111111111111111111111111111111", "signer": True, "writable": True},
    ]
    report = audit_account_contention(accounts)
    assert report.hotspot_count == 1
    assert report.concurrency_verdict == "SEVERE_LOCK_CONTENTION"
    assert any("Sysvar" in w for w in report.warnings)


def test_audit_account_contention_dex_pool_hotspot():
    accounts = [
        {"pubkey": "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8", "signer": False, "writable": True},  # Raydium AMM
        {"pubkey": "Trader1111111111111111111111111111111111111", "signer": True, "writable": True},
    ]
    report = audit_account_contention(accounts)
    assert report.hotspot_count == 1
    assert any("Raydium AMM v4" in w for w in report.warnings)

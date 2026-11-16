from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# Known Solana programs and system hotspots
KNOWN_SYSTEM_PROGRAMS: Dict[str, str] = {
    "11111111111111111111111111111111": "System Program",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA": "SPL Token Program",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb": "Token-2022 Program",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL": "Associated Token Program",
    "ComputeBudget111111111111111111111111111111": "Compute Budget Program",
    "AddressLookupTab1e1111111111111111111111111": "Address Lookup Table Program",
}

KNOWN_SYSVARS: Dict[str, str] = {
    "SysvarC1ock11111111111111111111111111111111": "Sysvar: Clock",
    "SysvarRent111111111111111111111111111111111": "Sysvar: Rent",
    "SysvarEpochSchedu1e111111111111111111111111": "Sysvar: Epoch Schedule",
    "SysvarStakeHistory1111111111111111111111111": "Sysvar: Stake History",
    "Sysvar1nstructions1111111111111111111111111": "Sysvar: Instructions",
    "SysvarFees111111111111111111111111111111111": "Sysvar: Fees",
}

KNOWN_DEX_PROTOCOLS: Dict[str, str] = {
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium AMM v4",
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "Raydium CLMM",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "Orca Whirlpool",
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo": "Meteora DLMM",
    "PhoeNiXZ8ByJGLkxNfZRnkUfjvmuYqLR89jjFHGqdXY": "Phoenix Orderbook",
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": "Pump.fun AMM",
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "Jupiter Aggregator v6",
}


@dataclass
class AccountAccess:
    pubkey: str
    is_signer: bool
    is_writable: bool
    label: Optional[str] = None
    is_hotspot: bool = False
    hotspot_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class ContentionReport:
    total_accounts: int
    writable_count: int
    readonly_count: int
    hotspot_count: int
    parallelizability_score: float  # 0.0 to 1.0 (1.0 = fully parallelizable, 0.0 = total lock bottleneck)
    concurrency_verdict: str        # "HIGHLY_PARALLELIZABLE", "MODERATE_CONTENTION", "SEVERE_LOCK_CONTENTION"
    accounts: List[AccountAccess]
    hotspot_accounts: List[AccountAccess]
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def audit_account_contention(
    account_keys: List[Dict[str, Any]],
    raw_logs: Optional[List[str]] = None,
) -> ContentionReport:
    """
    Audits account write-lock contention and Sealevel parallel execution suitability.

    On Solana, instructions locking the same writable accounts cannot execute concurrently
    within the same block or slot. Writing to shared global state (sysvars, liquidity pools,
    bonding curves) causes transaction landing latency and higher failure rates during congestion.
    """
    accounts: List[AccountAccess] = []
    hotspots: List[AccountAccess] = []
    warnings: List[str] = []

    writable_count = 0
    readonly_count = 0

    for item in account_keys:
        pubkey = item.get("pubkey") or item.get("key", "")
        if not pubkey:
            continue

        is_signer = bool(item.get("signer", False))
        is_writable = bool(item.get("writable", False))

        label = None
        is_hotspot = False
        hotspot_type = None

        if pubkey in KNOWN_SYSVARS:
            label = KNOWN_SYSVARS[pubkey]
            is_hotspot = True
            hotspot_type = "Sysvar"
            if is_writable:
                warnings.append(
                    f"CRITICAL: Sysvar '{label}' ({pubkey}) is marked writable! "
                    "Sysvars must always be read-only."
                )
        elif pubkey in KNOWN_SYSTEM_PROGRAMS:
            label = KNOWN_SYSTEM_PROGRAMS[pubkey]
            if is_writable:
                warnings.append(
                    f"CRITICAL: Program '{label}' ({pubkey}) is marked writable! "
                    "Programs must be read-only executable accounts."
                )
        elif pubkey in KNOWN_DEX_PROTOCOLS:
            label = KNOWN_DEX_PROTOCOLS[pubkey]
            is_hotspot = True
            hotspot_type = "DEX Protocol"
        elif is_writable:
            # Check if this account is accessed by multiple programs or looks like a shared AMM pool
            # Heuristic: Check if mentioned in DEX logs
            if raw_logs:
                for line in raw_logs:
                    if pubkey[:10] in line and ("swap" in line.lower() or "deposit" in line.lower()):
                        is_hotspot = True
                        hotspot_type = "DEX Liquidity Pool / State"
                        break

        acc = AccountAccess(
            pubkey=pubkey,
            is_signer=is_signer,
            is_writable=is_writable,
            label=label,
            is_hotspot=is_hotspot,
            hotspot_type=hotspot_type,
        )
        accounts.append(acc)

        if is_writable:
            writable_count += 1
            if is_hotspot:
                hotspots.append(acc)
                warnings.append(
                    f"Contention Warning: Writable access on shared hotspot '{acc.label or acc.pubkey}'. "
                    "Transactions locking this account cannot execute concurrently in the same thread."
                )
        else:
            readonly_count += 1

    total = len(accounts)
    if total == 0:
        return ContentionReport(
            total_accounts=0,
            writable_count=0,
            readonly_count=0,
            hotspot_count=0,
            parallelizability_score=1.0,
            concurrency_verdict="HIGHLY_PARALLELIZABLE",
            accounts=[],
            hotspot_accounts=[],
            warnings=[],
        )

    # Parallelizability scoring formula:
    # Baseline ratio: readonly / total
    # Hotspot penalty: -0.25 per writable hotspot
    ro_ratio = readonly_count / total
    hotspot_penalty = min(0.60, len(hotspots) * 0.25)
    score = max(0.0, min(1.0, round(ro_ratio * 0.8 + (0.2 if len(hotspots) == 0 else 0.0) - hotspot_penalty, 2)))

    if len(hotspots) > 0 or score < 0.40:
        verdict = "SEVERE_LOCK_CONTENTION"
    elif score < 0.70 or writable_count > 5:
        verdict = "MODERATE_CONTENTION"
    else:
        verdict = "HIGHLY_PARALLELIZABLE"

    return ContentionReport(
        total_accounts=total,
        writable_count=writable_count,
        readonly_count=readonly_count,
        hotspot_count=len(hotspots),
        parallelizability_score=score,
        concurrency_verdict=verdict,
        accounts=accounts,
        hotspot_accounts=hotspots,
        warnings=warnings,
    )

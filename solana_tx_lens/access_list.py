from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

# Known system programs, sysvars, and popular DEX/Token programs that should NEVER be writable
READ_ONLY_PROGRAMS: Set[str] = {
    "11111111111111111111111111111111",  # System Program
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # SPL Token Program
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",  # Token-2022 Program
    "ComputeBudget111111111111111111111111111111",  # Compute Budget Program
    "SysvarRent111111111111111111111111111111111",  # Sysvar Rent
    "SysvarC1ock11111111111111111111111111111111",  # Sysvar Clock
    "SysvarInstructions1111111111111111111111111",  # Sysvar Instructions
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",  # Jupiter v6
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",  # Orca Whirlpool
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium AMM v4
    "srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX",  # OpenBook v1
}

MAX_TX_BYTE_SIZE = 1232  # Solana MTU limit


@dataclass
class AccountLockRole:
    pubkey: str
    is_writable: bool
    is_signer: bool
    is_program_or_sysvar: bool = False
    contention_warning: Optional[str] = None


@dataclass
class LUTRecommendation:
    candidate_pubkeys: List[str]
    current_bytes: int
    compressed_bytes: int
    bytes_saved: int
    compression_ratio: float
    lut_suggested_address: Optional[str] = None


@dataclass
class SerializationStats:
    estimated_serialized_bytes: int
    mtu_limit_bytes: int = MAX_TX_BYTE_SIZE
    remaining_bytes: int = 0
    utilization_pct: float = 0.0
    within_mtu_limit: bool = True


@dataclass
class AccessListOptimizationReport:
    total_accounts: int
    write_locks: List[str]
    read_locks: List[str]
    signers: List[str]
    account_roles: List[AccountLockRole] = field(default_factory=list)
    lock_anti_patterns: List[str] = field(default_factory=list)
    concurrency_score: int = 100  # 100 = optimal non-blocking parallel execution, 0 = severe serial bottleneck
    serialization: Optional[SerializationStats] = None
    lut_recommendation: Optional[LUTRecommendation] = None
    actionable_improvements: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def estimate_tx_serialized_size(
    account_keys: List[str],
    signatures_count: int = 1,
    instructions_data_bytes: int = 128,
    has_lut: bool = False,
    lut_indices_count: int = 0,
) -> SerializationStats:
    """Estimates the Solana wire-format serialized transaction byte length."""
    # Wire structure:
    # 1 byte compact-u16 (signatures count) + (64 bytes * signatures_count)
    # Header: 3 bytes (num_required_signatures, num_readonly_signed, num_readonly_unsigned)
    # Account keys: compact-u16 + (32 bytes * num_accounts)
    # Blockhash: 32 bytes
    # Instructions + data
    sig_bytes = 1 + (64 * signatures_count)
    header_bytes = 3
    accounts_bytes = 1 + (32 * len(account_keys))
    blockhash_bytes = 32
    lut_table_bytes = 0
    if has_lut:
        lut_table_bytes = 32 + 1 + lut_indices_count  # LUT address + indices

    total = sig_bytes + header_bytes + accounts_bytes + blockhash_bytes + lut_table_bytes + instructions_data_bytes
    rem = MAX_TX_BYTE_SIZE - total
    pct = round((total / MAX_TX_BYTE_SIZE) * 100, 2)
    return SerializationStats(
        estimated_serialized_bytes=total,
        mtu_limit_bytes=MAX_TX_BYTE_SIZE,
        remaining_bytes=rem,
        utilization_pct=pct,
        within_mtu_limit=total <= MAX_TX_BYTE_SIZE,
    )


def analyze_access_list(
    account_keys: List[str],
    writable_indices: Optional[List[int]] = None,
    signer_indices: Optional[List[int]] = None,
    instructions_data_bytes: int = 128,
) -> AccessListOptimizationReport:
    """
    Performs deep inspection of Solana transaction account access lists:
    - Segregates read/write locks for Sealevel parallel execution.
    - Flags concurrency anti-patterns (e.g. programs marked writable).
    - Identifies Address Lookup Table (ALT) compression candidates.
    - Calculates transaction serialization byte budget.
    """
    total = len(account_keys)
    w_indices = set(writable_indices if writable_indices is not None else range(len(account_keys)))
    s_indices = set(signer_indices if signer_indices is not None else [0])

    write_locks: List[str] = []
    read_locks: List[str] = []
    signers: List[str] = []
    roles: List[AccountLockRole] = []
    anti_patterns: List[str] = []
    improvements: List[str] = []
    penalty = 0

    lut_candidates: List[str] = []

    for idx, pubkey in enumerate(account_keys):
        is_w = idx in w_indices
        is_s = idx in s_indices
        is_prog = pubkey in READ_ONLY_PROGRAMS

        warning = None
        if is_s:
            signers.append(pubkey)

        if is_w:
            write_locks.append(pubkey)
            if is_prog:
                warning = f"Anti-Pattern: Program/Sysvar {pubkey[:8]}... is marked WRITABLE! This blocks parallel validator execution."
                anti_patterns.append(warning)
                penalty += 35
                improvements.append(f"Demote {pubkey} from writable to read-only to prevent validator bank thread serialization.")
        else:
            read_locks.append(pubkey)
            # Read-only non-signer accounts are prime candidates for LUT compression
            if not is_s and not is_prog:
                lut_candidates.append(pubkey)

        roles.append(
            AccountLockRole(
                pubkey=pubkey,
                is_writable=is_w,
                is_signer=is_s,
                is_program_or_sysvar=is_prog,
                contention_warning=warning,
            )
        )

    # Concurrency scoring
    # Excessive write locks reduce parallel execution capability in Sealevel
    if len(write_locks) > 8:
        excess = len(write_locks) - 8
        penalty += excess * 3
        improvements.append(f"High write-lock footprint ({len(write_locks)} accounts). Review whether accounts can be downgraded to read-only.")

    concurrency_score = max(0, min(100, 100 - penalty))

    # Serialization calculation
    stats = estimate_tx_serialized_size(
        account_keys=account_keys,
        signatures_count=max(1, len(signers)),
        instructions_data_bytes=instructions_data_bytes,
    )

    if not stats.within_mtu_limit:
        anti_patterns.append(f"Transaction exceeds Solana 1232-byte MTU limit ({stats.estimated_serialized_bytes} bytes). Must use Address Lookup Tables.")
        improvements.append("Transaction payload exceeds MTU; compress static accounts into an Address Lookup Table (ALT).")

    # LUT Recommendation
    lut_rec = None
    if len(lut_candidates) >= 2 or len(account_keys) > 15:
        # Each account moved to LUT replaces 32 bytes in header with 1 byte index
        curr_b = len(lut_candidates) * 32
        comp_b = len(lut_candidates) * 1
        saved = curr_b - comp_b
        ratio = round(comp_b / curr_b if curr_b > 0 else 1.0, 3)
        lut_rec = LUTRecommendation(
            candidate_pubkeys=lut_candidates,
            current_bytes=curr_b,
            compressed_bytes=comp_b,
            bytes_saved=saved,
            compression_ratio=ratio,
        )
        improvements.append(f"Compress {len(lut_candidates)} static accounts into an ALT to save ~{saved} bytes on the wire format.")

    if not improvements:
        improvements.append("Account access list is optimally configured for Sealevel parallel execution.")

    return AccessListOptimizationReport(
        total_accounts=total,
        write_locks=write_locks,
        read_locks=read_locks,
        signers=signers,
        account_roles=roles,
        lock_anti_patterns=anti_patterns,
        concurrency_score=concurrency_score,
        serialization=stats,
        lut_recommendation=lut_rec,
        actionable_improvements=improvements,
    )

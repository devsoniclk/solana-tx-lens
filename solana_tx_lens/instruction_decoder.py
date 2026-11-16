import re
from typing import Dict, List, Optional

KNOWN_PROGRAMS: Dict[str, str] = {
    # System & Core
    "11111111111111111111111111111111": "System Program",
    "Config1111111111111111111111111111111111111": "Config Program",
    "Stake11111111111111111111111111111111111111": "Stake Program",
    "Vote111111111111111111111111111111111111111": "Vote Program",
    "BPFLoaderUpgradeab1e11111111111111111111111": "BPF Upgradeable Loader",
    "ComputeBudget111111111111111111111111111111": "Compute Budget",
    "AddressLookupTab1e1111111111111111111111111": "Address Lookup Table",
    "Ed25519SigVerify111111111111111111111111111": "Ed25519 Precompile",
    "KeccakSecp256k11111111111111111111111111111": "Secp256k1 Precompile",
    # Tokens & Accounts
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA": "SPL Token",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb": "Token-2022",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL": "Associated Token Account",
    "Memo1UhkJRfHyvLMcVucJwxXeuD728EqVDDwQDxFMNo": "Memo v1",
    "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr": "Memo v2",
    # DEXs & AMMs
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium AMM v4",
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "Raydium CLMM",
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C": "Raydium CPMM",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "Orca Whirlpool",
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": "Pump.fun",
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "Jupiter v6",
    "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB": "Jupiter v4",
    "srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX": "OpenBook v1",
    "opnb2TXrmDdHGaeR2wTcrFio526bBHu4WnwSZmkq9G6": "OpenBook v2",
    "PhoeNiXZ8ByJGLkxNfZRnkUfjvmuYqLR89jjFHGqdXY": "Phoenix DEX",
    "M2mx93ekt1fmXSVkTrUL9xVFHkmME8HTUi5Cyc5aF7K": "Magic Eden v2",
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo": "Meteora DLMM",
    "Eo7WjKq67rjJQSZxS6z3YkapzY3eMj6Xy8X5EQVn5UaB": "Meteora Dynamic AMM",
    "2wT8Yq49kHgDzXuPxZSaeLaH1qbmGXtEyPy64bL7aD3c": "Lifinity v2",
    "MoonCVVNZFSYkqNXP6bxHLPL6QQJiMagDL3qcqUQTrG": "Moonshot",
    "unOp9Q2MrFsKPms8Uhq97FFqMmAGaARUWNocPFDnT43": "Sanctum Router",
    "dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH": "Drift Protocol v2",
    "KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD": "Kamino Lending",
}

INSTRUCTION_LOG_PATTERNS = [
    re.compile(r"Program log: Instruction: (.+)", re.IGNORECASE),
    re.compile(r"Program log: instruction: (.+)", re.IGNORECASE),
    re.compile(r"Program log: (initialize\w*):", re.IGNORECASE),
    re.compile(r"Program log: (swap\w*):", re.IGNORECASE),
    re.compile(r"Program log: (buy|sell|create):", re.IGNORECASE),
    re.compile(r"Program log: Anchor: (\w+)", re.IGNORECASE),
]


def get_program_label(program_id: str) -> str:
    """
    Returns a human-readable label for known Solana programs or a shortened pubkey.
    """
    if program_id in KNOWN_PROGRAMS:
        return KNOWN_PROGRAMS[program_id]
    if len(program_id) > 10:
        return f"{program_id[:4]}...{program_id[-4:]}"
    return program_id


def extract_instruction_name(logs: List[str]) -> Optional[str]:
    """
    Scans execution logs of an invocation to extract the instruction name or operation.
    """
    for line in logs:
        for pattern in INSTRUCTION_LOG_PATTERNS:
            match = pattern.search(line)
            if match:
                raw_name = match.group(1).strip()
                # Clean up trailing params or details
                if ":" in raw_name:
                    raw_name = raw_name.split(":")[0].strip()
                return raw_name
    return None

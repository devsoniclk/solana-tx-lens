import re
from typing import Any, Dict, List, Optional
from .models import AccountDiff, TokenBalanceDiff

TOKEN_TRANSFER_LOG_RE = re.compile(
    r"Program log: (?:Instruction: )?Transfer(?:Checked)?(?::\s*(\d+))?",
    re.IGNORECASE,
)


def compute_account_diffs(
    pre_accounts: List[Dict[str, Any]], post_accounts: List[Dict[str, Any]]
) -> List[AccountDiff]:
    """
    Computes pre vs post simulation account state diffs (lamports, owner, data length).
    """
    diffs: List[AccountDiff] = []
    pre_map = {acc.get("pubkey", ""): acc for acc in pre_accounts if "pubkey" in acc}

    for post in post_accounts:
        pubkey = post.get("pubkey", "")
        pre = pre_map.get(pubkey, {})

        pre_lamports = pre.get("lamports", 0)
        post_lamports = post.get("lamports", 0)
        delta = post_lamports - pre_lamports

        pre_owner = pre.get("owner", "")
        post_owner = post.get("owner", "")

        pre_len = len(pre.get("data", "") or "")
        post_len = len(post.get("data", "") or "")
        data_delta = post_len - pre_len

        if delta != 0 or pre_owner != post_owner or data_delta != 0:
            diffs.append(
                AccountDiff(
                    pubkey=pubkey,
                    pre_lamports=pre_lamports,
                    post_lamports=post_lamports,
                    lamports_delta=delta,
                    pre_owner=pre_owner,
                    post_owner=post_owner,
                    data_len_delta=data_delta,
                )
            )

    return diffs


def compute_token_diffs(
    pre_token_balances: List[Dict[str, Any]], post_token_balances: List[Dict[str, Any]]
) -> List[TokenBalanceDiff]:
    """
    Computes SPL Token balance deltas from pre and post simulation token balance structures.
    Supports standard Solana JSON-RPC preTokenBalances / postTokenBalances format.
    """
    diffs: List[TokenBalanceDiff] = []
    pre_map: Dict[str, Dict[str, Any]] = {}

    for item in pre_token_balances:
        key = (
            item.get("account")
            or f"{item.get('owner', '')}_{item.get('mint', '')}_{item.get('accountIndex', '')}"
        )
        pre_map[key] = item

    all_keys = set(pre_map.keys())
    post_map: Dict[str, Dict[str, Any]] = {}

    for item in post_token_balances:
        key = (
            item.get("account")
            or f"{item.get('owner', '')}_{item.get('mint', '')}_{item.get('accountIndex', '')}"
        )
        post_map[key] = item
        all_keys.add(key)

    for key in sorted(all_keys):
        pre = pre_map.get(key, {})
        post = post_map.get(key, {})

        account = post.get("account") or pre.get("account") or key
        mint = post.get("mint") or pre.get("mint") or "Unknown"
        owner = post.get("owner") or pre.get("owner") or "Unknown"

        pre_ui = pre.get("uiTokenAmount", {})
        post_ui = post.get("uiTokenAmount", {})

        decimals = post_ui.get("decimals") or pre_ui.get("decimals", 0)

        pre_amt = float(pre_ui.get("uiAmount") or 0.0)
        post_amt = float(post_ui.get("uiAmount") or 0.0)
        delta = round(post_amt - pre_amt, decimals if decimals else 6)

        if delta != 0.0:
            diffs.append(
                TokenBalanceDiff(
                    account=account,
                    mint=mint,
                    owner=owner,
                    pre_amount=pre_amt,
                    post_amount=post_amt,
                    delta=delta,
                    decimals=decimals,
                )
            )

    return diffs


def parse_token_transfers_from_logs(logs: List[str]) -> List[TokenBalanceDiff]:
    """
    Extracts high-level token transfer events directly from execution logs
    when full pre/post token balance tables are omitted in simulation payloads.
    """
    transfers: List[TokenBalanceDiff] = []
    curr_prog = ""

    for line in logs:
        if "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke" in line:
            curr_prog = "SPL Token"
        elif "Program TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb invoke" in line:
            curr_prog = "Token-2022"

        m = TOKEN_TRANSFER_LOG_RE.search(line)
        if m and curr_prog:
            raw_amt = m.group(1)
            amount = float(raw_amt) if raw_amt else 0.0
            transfers.append(
                TokenBalanceDiff(
                    account=f"{curr_prog} Instruction",
                    mint="SPL-Token",
                    owner="",
                    pre_amount=0.0,
                    post_amount=amount,
                    delta=amount,
                    decimals=0,
                )
            )

    return transfers

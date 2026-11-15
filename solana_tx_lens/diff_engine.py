from typing import Any, Dict, List
from .models import AccountDiff


def compute_account_diffs(pre_accounts: List[Dict[str, Any]], post_accounts: List[Dict[str, Any]]) -> List[AccountDiff]:
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

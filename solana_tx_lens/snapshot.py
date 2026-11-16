from __future__ import annotations

import base64
import dataclasses
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Solana rent exemption parameters (standard sysvar rent constant)
ACCOUNT_STORAGE_OVERHEAD = 128
LAMPORTS_PER_BYTE_YEAR = 3480
YEARS_OF_RENT = 2
LAMPORTS_PER_SOL = 1_000_000_000


def calculate_rent_exempt_reserve(data_len: int) -> int:
    """Calculates Solana rent-exempt minimum lamports required for given data length."""
    return (ACCOUNT_STORAGE_OVERHEAD + data_len) * LAMPORTS_PER_BYTE_YEAR * YEARS_OF_RENT


@dataclass
class AccountSnapshotDelta:
    pubkey: str
    pre_lamports: int
    post_lamports: int
    lamports_delta: int
    sol_delta: float
    pre_owner: str
    post_owner: str
    owner_changed: bool
    pre_data_len: int
    post_data_len: int
    data_len_delta: int
    pre_executable: bool
    post_executable: bool
    rent_exempt_reserve: int
    is_rent_exempt: bool
    raw_data_modified: bool = False
    modified_byte_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class ShadowReplaySummary:
    total_accounts_touched: int
    accounts_created: int
    accounts_closed: int
    total_lamports_delta: int
    total_sol_delta: float
    total_bytes_delta: int
    rent_exempt_violations: List[str] = field(default_factory=list)
    account_deltas: List[AccountSnapshotDelta] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_accounts_touched": self.total_accounts_touched,
            "accounts_created": self.accounts_created,
            "accounts_closed": self.accounts_closed,
            "total_lamports_delta": self.total_lamports_delta,
            "total_sol_delta": self.total_sol_delta,
            "total_bytes_delta": self.total_bytes_delta,
            "rent_exempt_violations": self.rent_exempt_violations,
            "account_deltas": [d.to_dict() for d in self.account_deltas],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class ShadowStateReplayer:
    """
    Simulates in-memory Solana slot state transitions, computing binary account deltas
    and allowing chained transaction verification without extra RPC roundtrips.
    """

    def __init__(self, initial_accounts: Optional[List[Dict[str, Any]]] = None):
        self.state: Dict[str, Dict[str, Any]] = {}
        if initial_accounts:
            for acc in initial_accounts:
                pk = acc.get("pubkey") or acc.get("address")
                if pk:
                    self.state[pk] = dict(acc)

    def get_account(self, pubkey: str) -> Optional[Dict[str, Any]]:
        return self.state.get(pubkey)

    @staticmethod
    def diff_account(
        pubkey: str, pre_acc: Optional[Dict[str, Any]], post_acc: Optional[Dict[str, Any]]
    ) -> AccountSnapshotDelta:
        pre = pre_acc or {}
        post = post_acc or {}

        pre_lamports = pre.get("lamports", 0)
        post_lamports = post.get("lamports", 0)
        lamports_delta = post_lamports - pre_lamports

        pre_owner = pre.get("owner", "11111111111111111111111111111111")
        post_owner = post.get("owner", pre_owner)
        owner_changed = (pre_owner != post_owner) and bool(pre) and bool(post)

        # Compute data length & modified bytes
        pre_data_raw = pre.get("data", "")
        post_data_raw = post.get("data", "")

        pre_bytes = b""
        post_bytes = b""
        if isinstance(pre_data_raw, str) and pre_data_raw:
            try:
                pre_bytes = base64.b64decode(pre_data_raw)
            except Exception:
                pre_bytes = pre_data_raw.encode("utf-8", errors="ignore")
        elif isinstance(pre_data_raw, list) and pre_data_raw:
            try:
                pre_bytes = base64.b64decode(pre_data_raw[0])
            except Exception:
                pass

        if isinstance(post_data_raw, str) and post_data_raw:
            try:
                post_bytes = base64.b64decode(post_data_raw)
            except Exception:
                post_bytes = post_data_raw.encode("utf-8", errors="ignore")
        elif isinstance(post_data_raw, list) and post_data_raw:
            try:
                post_bytes = base64.b64decode(post_data_raw[0])
            except Exception:
                pass

        pre_len = len(pre_bytes)
        post_len = len(post_bytes)
        data_delta = post_len - pre_len

        # Modified byte count diff
        diff_count = 0
        min_len = min(pre_len, post_len)
        for i in range(min_len):
            if pre_bytes[i] != post_bytes[i]:
                diff_count += 1
        diff_count += abs(data_delta)

        pre_exec = bool(pre.get("executable", False))
        post_exec = bool(post.get("executable", False))

        rent_exempt_min = calculate_rent_exempt_reserve(post_len)
        is_exempt = post_lamports >= rent_exempt_min or post_lamports == 0

        return AccountSnapshotDelta(
            pubkey=pubkey,
            pre_lamports=pre_lamports,
            post_lamports=post_lamports,
            lamports_delta=lamports_delta,
            sol_delta=lamports_delta / LAMPORTS_PER_SOL,
            pre_owner=pre_owner,
            post_owner=post_owner,
            owner_changed=owner_changed,
            pre_data_len=pre_len,
            post_data_len=post_len,
            data_len_delta=data_delta,
            pre_executable=pre_exec,
            post_executable=post_exec,
            rent_exempt_reserve=rent_exempt_min,
            is_rent_exempt=is_exempt,
            raw_data_modified=(pre_bytes != post_bytes),
            modified_byte_count=diff_count,
        )

    def diff_snapshots(
        self,
        pre_accounts: List[Dict[str, Any]],
        post_accounts: List[Dict[str, Any]],
        account_keys: Optional[List[str]] = None,
    ) -> ShadowReplaySummary:
        """Diffs simulation pre-state and post-state accounts."""
        pre_map: Dict[str, Dict[str, Any]] = {}
        for acc in pre_accounts:
            pk = acc.get("pubkey") or acc.get("address")
            if pk:
                pre_map[pk] = acc

        post_map: Dict[str, Dict[str, Any]] = {}
        for idx, acc in enumerate(post_accounts):
            pk = acc.get("pubkey") or acc.get("address")
            if not pk and account_keys and idx < len(account_keys):
                pk = account_keys[idx]
            if pk:
                post_map[pk] = acc

        all_keys = list(set(list(pre_map.keys()) + list(post_map.keys())))
        if account_keys:
            all_keys = sorted(all_keys, key=lambda k: account_keys.index(k) if k in account_keys else 9999)

        deltas: List[AccountSnapshotDelta] = []
        created = 0
        closed = 0
        tot_lamports = 0
        tot_bytes = 0
        violations: List[str] = []

        for pk in all_keys:
            pre_acc = pre_map.get(pk)
            post_acc = post_map.get(pk)
            d = self.diff_account(pk, pre_acc, post_acc)

            if not pre_acc and post_acc and d.post_lamports > 0:
                created += 1
            elif pre_acc and post_acc and pre_acc.get("lamports", 0) > 0 and post_acc.get("lamports", 0) == 0:
                closed += 1

            if not d.is_rent_exempt and d.post_lamports > 0:
                violations.append(
                    f"{pk}: {d.post_lamports} lamports < required {d.rent_exempt_reserve} for {d.post_data_len} bytes"
                )

            deltas.append(d)
            tot_lamports += d.lamports_delta
            tot_bytes += d.data_len_delta

        return ShadowReplaySummary(
            total_accounts_touched=len(deltas),
            accounts_created=created,
            accounts_closed=closed,
            total_lamports_delta=tot_lamports,
            total_sol_delta=tot_lamports / LAMPORTS_PER_SOL,
            total_bytes_delta=tot_bytes,
            rent_exempt_violations=violations,
            account_deltas=deltas,
        )

    def apply_transition(self, post_accounts: List[Dict[str, Any]], account_keys: Optional[List[str]] = None):
        """Applies post-simulation state to in-memory bank shadow state."""
        for idx, acc in enumerate(post_accounts):
            pk = acc.get("pubkey") or acc.get("address")
            if not pk and account_keys and idx < len(account_keys):
                pk = account_keys[idx]
            if pk:
                self.state[pk] = dict(acc)


def create_account_snapshot_delta(
    pre_accounts: List[Dict[str, Any]],
    post_accounts: List[Dict[str, Any]],
    account_keys: Optional[List[str]] = None,
) -> ShadowReplaySummary:
    """Convenience functional interface to compute shadow account deltas."""
    replayer = ShadowStateReplayer(pre_accounts)
    return replayer.diff_snapshots(pre_accounts, post_accounts, account_keys=account_keys)

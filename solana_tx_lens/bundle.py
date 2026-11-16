from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .contention import audit_account_contention
from .models import AccountDiff, SimulationResult, TokenBalanceDiff
from .simulator import SolanaSimulator

JITO_TIP_ACCOUNTS: Set[str] = {
    "96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5",
    "HFqU5x63VTqvQss8hp11i4wVV8bD44PvwucfZ2bU7gRe",
    "Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY",
    "ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49",
    "DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh",
    "ADuUkR4vqLUMWXxW9gh6D6L8pMSawimctcNZ5pGwDcEt",
    "DttWaMuVvTiduZRnguLF7jNxTgiMBZ1hyAumKUiL2KRL",
    "3AVi9Tg9Uo68tJfuvoKvqKNWKkC5wPdSSdeBnizKZ6jT",
}


@dataclass
class JitoTipAnalysis:
    tip_account: Optional[str] = None
    tip_lamports: int = 0
    tip_sol: float = 0.0
    is_valid_jito_tip: bool = False
    detected_in_tx_index: Optional[int] = None
    tip_tier: str = "none"

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class BundleSimulationResult:
    success: bool
    transaction_count: int
    total_compute_units: int
    reverted_at_index: Optional[int] = None
    revert_error: Optional[str] = None
    transactions: List[SimulationResult] = field(default_factory=list)
    jito_tip: JitoTipAnalysis = field(default_factory=JitoTipAnalysis)
    cumulative_account_diffs: List[AccountDiff] = field(default_factory=list)
    cumulative_token_diffs: List[TokenBalanceDiff] = field(default_factory=list)
    bundle_contention_warnings: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_html(self, title: str = "Solana Bundle Simulation Dossier") -> str:
        from .html_report import render_bundle_html_report

        return render_bundle_html_report(self, title=title)


class BundleSimulator:
    """
    Simulates and validates atomic multi-transaction bundles (such as Jito MEV bundles)
    with cumulative CU tracking, cross-transaction state transitions, and tip verification.
    """

    def __init__(self, rpc_url: str = "https://api.mainnet-beta.solana.com", timeout: int = 15):
        self.rpc_url = rpc_url
        self.timeout = timeout
        self.simulator = SolanaSimulator(rpc_url=rpc_url, timeout=timeout)

    def simulate_bundle(self, transactions: List[Dict[str, Any]]) -> BundleSimulationResult:
        if not transactions:
            return BundleSimulationResult(
                success=True,
                transaction_count=0,
                total_compute_units=0,
                summary="Empty bundle. No transactions to simulate.",
            )

        sim_results: List[SimulationResult] = []
        total_cus = 0
        reverted_idx: Optional[int] = None
        revert_err: Optional[str] = None
        is_bundle_success = True

        tip_analysis = JitoTipAnalysis()
        tx_writable_accounts: List[Set[str]] = []

        # Chained account state tracking
        initial_lamports: Dict[str, int] = {}
        latest_lamports: Dict[str, int] = {}
        account_owners: Dict[str, str] = {}
        account_data_lens: Dict[str, int] = {}

        # Chained token state tracking: (mint, owner) -> balance info
        token_initial: Dict[str, Dict[str, Any]] = {}
        token_latest: Dict[str, Dict[str, Any]] = {}

        for idx, tx_data in enumerate(transactions):
            # Parse individual transaction simulation
            sim_val = tx_data.get("value") or tx_data.get("result") or tx_data
            res = self.simulator.parse_raw_simulation(
                sim_val,
                pre_accounts=tx_data.get("preAccounts"),
                pre_token_balances=tx_data.get("preTokenBalances"),
                post_token_balances=tx_data.get("postTokenBalances"),
                account_keys=tx_data.get("accountKeys") or tx_data.get("accounts"),
            )
            sim_results.append(res)
            total_cus += res.total_compute_units

            # Detect write-lock contention across transactions
            curr_writables = set()
            account_keys = tx_data.get("accountKeys") or tx_data.get("accounts") or []
            for k in account_keys:
                if isinstance(k, dict) and k.get("writable"):
                    curr_writables.add(k.get("pubkey", ""))
            tx_writable_accounts.append(curr_writables)

            # Check for Jito tip in account diffs or logs
            if not tip_analysis.is_valid_jito_tip:
                for diff in res.account_diffs:
                    if diff.pubkey in JITO_TIP_ACCOUNTS and diff.lamports_delta > 0:
                        tip_lamports = diff.lamports_delta
                        tip_sol = tip_lamports / 1_000_000_000.0
                        tier = "low"
                        if tip_sol >= 0.1:
                            tier = "sniper"
                        elif tip_sol >= 0.01:
                            tier = "high"
                        elif tip_sol >= 0.001:
                            tier = "medium"

                        tip_analysis = JitoTipAnalysis(
                            tip_account=diff.pubkey,
                            tip_lamports=tip_lamports,
                            tip_sol=tip_sol,
                            is_valid_jito_tip=True,
                            detected_in_tx_index=idx,
                            tip_tier=tier,
                        )
                        break

            # Check if transaction failed
            if not res.success or res.error is not None:
                if is_bundle_success:
                    is_bundle_success = False
                    reverted_idx = idx
                    revert_err = res.error.description if res.error else "Transaction execution failed"

            # Aggregate account diffs into cumulative transition
            for diff in res.account_diffs:
                if diff.pubkey not in initial_lamports:
                    initial_lamports[diff.pubkey] = diff.pre_lamports
                    account_owners[diff.pubkey] = diff.pre_owner
                    account_data_lens[diff.pubkey] = 0
                latest_lamports[diff.pubkey] = diff.post_lamports
                account_owners[diff.pubkey] = diff.post_owner
                account_data_lens[diff.pubkey] += diff.data_len_delta

            # Aggregate token diffs
            for t_diff in res.token_diffs:
                key = f"{t_diff.mint}:{t_diff.owner}"
                if key not in token_initial:
                    token_initial[key] = {
                        "account": t_diff.account,
                        "mint": t_diff.mint,
                        "owner": t_diff.owner,
                        "pre_amount": t_diff.pre_amount,
                        "decimals": t_diff.decimals,
                        "symbol": t_diff.symbol,
                    }
                token_latest[key] = {
                    "account": t_diff.account,
                    "mint": t_diff.mint,
                    "owner": t_diff.owner,
                    "post_amount": t_diff.post_amount,
                    "decimals": t_diff.decimals,
                    "symbol": t_diff.symbol,
                }

        # Cross-transaction contention analysis
        contention_warnings: List[str] = []
        for i in range(len(tx_writable_accounts)):
            for j in range(i + 1, len(tx_writable_accounts)):
                overlap = tx_writable_accounts[i].intersection(tx_writable_accounts[j])
                if overlap:
                    for pub in overlap:
                        if pub:
                            contention_warnings.append(
                                f"Cross-Tx Write Lock Collision: Account {pub[:8]}...{pub[-4:]} locked for writing in Tx #{i} and Tx #{j}."
                            )

        # Build cumulative AccountDiff list
        cum_account_diffs: List[AccountDiff] = []
        for pubkey, init_l in initial_lamports.items():
            post_l = latest_lamports.get(pubkey, init_l)
            delta = post_l - init_l
            if delta != 0:
                cum_account_diffs.append(
                    AccountDiff(
                        pubkey=pubkey,
                        pre_lamports=init_l,
                        post_lamports=post_l,
                        lamports_delta=delta,
                        pre_owner=account_owners.get(pubkey, "11111111111111111111111111111111"),
                        post_owner=account_owners.get(pubkey, "11111111111111111111111111111111"),
                        data_len_delta=account_data_lens.get(pubkey, 0),
                    )
                )

        # Build cumulative TokenBalanceDiff list
        cum_token_diffs: List[TokenBalanceDiff] = []
        for key, init_t in token_initial.items():
            post_t = token_latest.get(key, init_t)
            pre_amt = init_t["pre_amount"]
            post_amt = post_t["post_amount"]
            delta = post_amt - pre_amt
            if delta != 0 or pre_amt != post_amt:
                cum_token_diffs.append(
                    TokenBalanceDiff(
                        account=init_t["account"],
                        mint=init_t["mint"],
                        owner=init_t["owner"],
                        pre_amount=pre_amt,
                        post_amount=post_amt,
                        delta=delta,
                        decimals=init_t["decimals"],
                        symbol=init_t["symbol"],
                    )
                )

        # Formulate summary
        if is_bundle_success:
            tip_str = f"with {tip_analysis.tip_sol:.4f} SOL Jito tip" if tip_analysis.is_valid_jito_tip else "no Jito tip detected"
            summary = (
                f"Bundle PASSED: {len(transactions)} transaction(s) executed atomically. "
                f"Consumed {total_cus:,} total CUs ({tip_str})."
            )
        else:
            summary = (
                f"Bundle REVERTED at transaction #{reverted_idx}: {revert_err}. "
                f"All subsequent bundle operations aborted."
            )

        return BundleSimulationResult(
            success=is_bundle_success,
            transaction_count=len(transactions),
            total_compute_units=total_cus,
            reverted_at_index=reverted_idx,
            revert_error=revert_err,
            transactions=sim_results,
            jito_tip=tip_analysis,
            cumulative_account_diffs=cum_account_diffs,
            cumulative_token_diffs=cum_token_diffs,
            bundle_contention_warnings=contention_warnings,
            summary=summary,
        )

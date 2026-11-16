from __future__ import annotations

import json
import urllib.request
from typing import Any, Dict, List, Optional
from .contention import audit_account_contention
from .cpi_parser import parse_cpi_tree
from .diff_engine import compute_account_diffs, compute_token_diffs, parse_token_transfers_from_logs
from .error_decoder import decode_solana_error
from .events import decode_program_events_and_returns
from .guard import assess_simulation_health
from .mev_radar import scan_mev_vulnerabilities
from .models import SimulationResult
from .optimizer import optimize_compute_budget
from .route_analyzer import analyze_swap_route
from .snapshot import create_account_snapshot_delta
from .stress_tester import stress_test_simulation


class SolanaSimulator:
    """
    Headless Solana transaction simulator and diagnostic client.
    Interacts with standard Solana JSON-RPC without third-party dependencies.
    """

    def __init__(self, rpc_url: str = "https://api.mainnet-beta.solana.com", timeout: int = 15):
        self.rpc_url = rpc_url
        self.timeout = timeout

    def simulate_encoded_transaction(self, tx_base64: str) -> SimulationResult:
        """
        Submits simulateTransaction to the RPC endpoint and decodes the result.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "simulateTransaction",
            "params": [
                tx_base64,
                {
                    "encoding": "base64",
                    "sigVerify": False,
                    "replaceRecentBlockhash": True,
                    "accounts": {
                        "encoding": "base64",
                        "addresses": [],
                    },
                },
            ],
        }

        req = urllib.request.Request(
            self.rpc_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if "error" in data:
            raise RuntimeError(f"RPC simulation call failed: {data['error']}")

        val = data.get("result", {}).get("value", {})
        return self.parse_raw_simulation(val)

    @staticmethod
    def parse_raw_simulation(
        sim_value: Dict[str, Any],
        pre_accounts: Optional[List[Dict[str, Any]]] = None,
        pre_token_balances: Optional[List[Dict[str, Any]]] = None,
        post_token_balances: Optional[List[Dict[str, Any]]] = None,
        account_keys: Optional[List[Dict[str, Any]]] = None,
    ) -> SimulationResult:
        """
        Parses a raw RPC simulation value dictionary into a structured SimulationResult,
        including account diffs, token balance deltas, pre-flight security health checks,
        dynamic compute budget optimization, and write-lock contention audit.
        """
        logs = sim_value.get("logs", []) or []
        err = sim_value.get("err")
        units_consumed = sim_value.get("unitsConsumed", 0)

        cpi_roots = parse_cpi_tree(logs)
        post_accounts = sim_value.get("accounts", []) or []
        account_diffs = compute_account_diffs(pre_accounts or [], post_accounts)

        # Extract token balances if provided directly or embedded in sim_value
        pre_tb = pre_token_balances or sim_value.get("preTokenBalances", []) or []
        post_tb = post_token_balances or sim_value.get("postTokenBalances", []) or []
        token_diffs = compute_token_diffs(pre_tb, post_tb)

        if not token_diffs and logs:
            token_diffs = parse_token_transfers_from_logs(logs)

        error_info = None
        if err:
            failing_prog = None
            for root in cpi_roots:
                if root.failed:
                    failing_prog = root.program_id
                    break
            error_info = decode_solana_error(err, failing_prog)

        max_cus = 200_000 if units_consumed <= 200_000 else 1_400_000

        # Compute budget optimization
        optimization = optimize_compute_budget(units_consumed, default_limit=max_cus)

        # Contention audit
        keys = account_keys or sim_value.get("accountKeys") or sim_value.get("accounts")
        contention = None
        if keys and isinstance(keys, list):
            # Format could be list of dicts or list of strings
            formatted_keys = []
            for k in keys:
                if isinstance(k, dict):
                    formatted_keys.append(k)
                elif isinstance(k, str):
                    formatted_keys.append({"pubkey": k, "signer": False, "writable": True})
            contention = audit_account_contention(formatted_keys, raw_logs=logs)

        result = SimulationResult(
            success=(err is None),
            total_compute_units=units_consumed,
            max_compute_units=max_cus,
            cpi_roots=cpi_roots,
            account_diffs=account_diffs,
            token_diffs=token_diffs,
            error=error_info,
            optimization=optimization,
            contention=contention,
            raw_logs=logs,
        )

        result.health = assess_simulation_health(result)
        result.mev_radar = scan_mev_vulnerabilities(result)
        result.route = analyze_swap_route(result)
        result.events_report = decode_program_events_and_returns(logs)
        result.shadow_snapshot = create_account_snapshot_delta(
            pre_accounts or [],
            post_accounts,
            account_keys=[k.get("pubkey") if isinstance(k, dict) else str(k) for k in (keys or [])] if keys else None,
        )
        result.stress_test = stress_test_simulation(result)
        return result

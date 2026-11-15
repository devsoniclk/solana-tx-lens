import json
import urllib.request
from typing import Any, Dict, List, Optional
from .cpi_parser import parse_cpi_tree
from .diff_engine import compute_account_diffs, compute_token_diffs, parse_token_transfers_from_logs
from .error_decoder import decode_solana_error
from .guard import assess_simulation_health
from .models import SimulationResult


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
    ) -> SimulationResult:
        """
        Parses a raw RPC simulation value dictionary into a structured SimulationResult,
        including account diffs, token balance deltas, and pre-flight security health checks.
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
        # If ComputeBudget was used in transaction, detect requested limit from logs if present
        for line in logs:
            if "SetComputeUnitLimit" in line:
                pass

        result = SimulationResult(
            success=(err is None),
            total_compute_units=units_consumed,
            max_compute_units=max_cus,
            cpi_roots=cpi_roots,
            account_diffs=account_diffs,
            token_diffs=token_diffs,
            error=error_info,
            raw_logs=logs,
        )

        result.health = assess_simulation_health(result)
        return result

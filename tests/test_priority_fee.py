import json
import pytest
from solana_tx_lens.priority_fee import DynamicFeeOptimizer
from solana_tx_lens.mcp_server import SolanaLensMCPServer


class TestDynamicFeeOptimizer:

    def test_fee_prediction_percentiles(self):
        optimizer = DynamicFeeOptimizer(cluster="mainnet-beta")
        accounts = [
            "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
            "So11111111111111111111111111111111111111112",
        ]
        res = optimizer.predict_priority_fee(
            writable_accounts=accounts,
            target_compute_units=150_000,
            congestion_multiplier=1.2,
        )

        assert res["target_compute_units"] == 150_000
        assert res["cluster"] == "mainnet-beta"
        recs = res["recommendations"]
        assert "p50_standard" in recs
        assert "p75_fast" in recs
        assert "p90_turbo" in recs
        assert "p99_ultra" in recs

        # Monotonically increasing fees
        assert recs["p50_standard"]["micro_lamports_per_cu"] < recs["p75_fast"]["micro_lamports_per_cu"]
        assert recs["p75_fast"]["micro_lamports_per_cu"] < recs["p90_turbo"]["micro_lamports_per_cu"]
        assert recs["p90_turbo"]["micro_lamports_per_cu"] < recs["p99_ultra"]["micro_lamports_per_cu"]

        assert "ComputeBudgetProgram.setComputeUnitPrice" in res["suggested_instruction"]

    def test_high_congestion_multiplier(self):
        optimizer = DynamicFeeOptimizer()
        accounts = ["SysvarRent111111111111111111111111111111111"]
        base_res = optimizer.predict_priority_fee(accounts, congestion_multiplier=1.0)
        high_res = optimizer.predict_priority_fee(accounts, congestion_multiplier=5.0)

        assert high_res["contention_index"] > base_res["contention_index"]
        assert (
            high_res["recommendations"]["p50_standard"]["micro_lamports_per_cu"]
            > base_res["recommendations"]["p50_standard"]["micro_lamports_per_cu"]
        )


class TestPriorityFeeMCPServer:

    def test_mcp_predict_priority_fee(self):
        server = SolanaLensMCPServer()
        req = {
            "jsonrpc": "2.0",
            "id": 101,
            "method": "tools/call",
            "params": {
                "name": "solana_predict_priority_fee",
                "arguments": {
                    "writable_accounts": ["JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"],
                    "target_compute_units": 250000,
                    "congestion_multiplier": 1.5,
                },
            },
        }
        resp = server.handle_request(req)
        assert resp["id"] == 101
        content = json.loads(resp["result"]["content"][0]["text"])
        assert content["target_compute_units"] == 250000
        assert "recommendations" in content

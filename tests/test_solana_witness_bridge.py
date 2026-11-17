import pytest

from solana_tx_lens.simulator import SolanaSimulator
from solana_tx_lens.witness_bridge import attest_simulation_result


class TestSolanaWitnessBridge:

    def test_attest_simulation_result(self):
        raw_sim = {
            "unitsConsumed": 45_000,
            "err": None,
            "logs": [
                "Program 11111111111111111111111111111111 invoke [1]",
                "Program 11111111111111111111111111111111 success",
            ],
        }

        sim_res = SolanaSimulator.parse_raw_simulation(raw_sim)
        att_res = attest_simulation_result(sim_res, agent_id="solana-tx-lens-agent")

        assert att_res["attested"] is True
        assert att_res["success"] is True
        assert att_res["compute_units"] == 45_000
        assert att_res["step_index"] >= 0

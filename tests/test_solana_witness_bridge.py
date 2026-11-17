import pytest

from solana_tx_lens.simulator import SolanaSimulator
from solana_tx_lens.witness_bridge import attest_simulation_result, HAS_WITNESS


class MockStep:
    def __init__(self, index: int):
        self.index = index


class MockWitnessEngine:
    def __init__(self):
        self.steps = []

    def record_step(self, step_type, description, metadata=None):
        step = MockStep(len(self.steps))
        self.steps.append({"step_type": step_type, "description": description, "metadata": metadata})
        return step


class TestSolanaWitnessBridge:

    def test_attest_simulation_result_with_engine(self):
        raw_sim = {
            "unitsConsumed": 45_000,
            "err": None,
            "logs": [
                "Program 11111111111111111111111111111111 invoke [1]",
                "Program 11111111111111111111111111111111 success",
            ],
        }

        sim_res = SolanaSimulator.parse_raw_simulation(raw_sim)
        mock_eng = MockWitnessEngine()
        att_res = attest_simulation_result(sim_res, engine=mock_eng, agent_id="solana-tx-lens-agent")

        assert att_res["attested"] is True
        assert att_res["success"] is True
        assert att_res["compute_units"] == 45_000
        assert att_res["step_index"] == 0
        assert len(mock_eng.steps) == 1
        assert "Solana Simulation" in mock_eng.steps[0]["description"]

    def test_attest_simulation_result_environment_aware(self):
        raw_sim = {
            "unitsConsumed": 30_000,
            "err": None,
            "logs": ["Program 11111111111111111111111111111111 invoke [1]"],
        }
        sim_res = SolanaSimulator.parse_raw_simulation(raw_sim)
        att_res = attest_simulation_result(sim_res, agent_id="solana-agent-env")

        if HAS_WITNESS:
            assert att_res["attested"] is True
            assert att_res["compute_units"] == 30_000
        else:
            assert att_res["attested"] is False
            assert att_res["reason"] == "agent-witness not installed"

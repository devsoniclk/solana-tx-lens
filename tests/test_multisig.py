import json
import pytest
from solana_tx_lens.multisig import (
    MultisigConsensusVerifier,
    MultisigVerificationError,
)
from solana_tx_lens.mcp_server import SolanaLensMCPServer


class TestMultisigConsensusVerifier:

    def test_threshold_success(self):
        verifier = MultisigConsensusVerifier(threshold=2, total_members=3)
        res = verifier.verify_signers(["pubkey1", "pubkey2"])
        assert res["is_authorized"] is True
        assert res["valid_signatures"] == 2
        assert res["threshold"] == 2

    def test_threshold_insufficient_signatures(self):
        verifier = MultisigConsensusVerifier(threshold=3, total_members=5)
        with pytest.raises(MultisigVerificationError) as exc_info:
            verifier.verify_signers(["pubkey1", "pubkey2"])
        assert "Threshold not met" in str(exc_info.value)
        assert exc_info.value.details["valid_signatures"] == 2

    def test_slashed_signer_rejection(self):
        verifier = MultisigConsensusVerifier(
            threshold=2,
            total_members=4,
            slashed_members=["malicious_agent_key"],
        )
        with pytest.raises(MultisigVerificationError) as exc_info:
            verifier.verify_signers(["pubkey1", "malicious_agent_key"])
        assert "slashed/Byzantine" in str(exc_info.value)

    def test_bft_consensus_certificate_valid(self):
        verifier = MultisigConsensusVerifier(threshold=2, total_members=3)
        cert = {
            "certificate_id": "sol-cert-01",
            "trajectory_id": "tx-traj-01",
            "committed_weight": 3,
            "quorum_threshold": 2,
            "is_finalized": True,
            "precommits": [
                {"agent_id": "val1", "weight": 1},
                {"agent_id": "val2", "weight": 1},
                {"agent_id": "val3", "weight": 1},
            ],
            "slashed_agents": [],
        }
        res = verifier.verify_bft_certificate(cert)
        assert res["status"] == "verified"
        assert res["quorum_achieved"] is True
        assert res["committed_weight"] == 3

    def test_bft_certificate_slashed_vote_rejected(self):
        verifier = MultisigConsensusVerifier(
            threshold=2,
            total_members=3,
            slashed_members=["rogue_validator"],
        )
        cert = {
            "certificate_id": "sol-cert-bad",
            "trajectory_id": "tx-traj-bad",
            "committed_weight": 2,
            "quorum_threshold": 2,
            "is_finalized": True,
            "precommits": [
                {"agent_id": "val1", "weight": 1},
                {"agent_id": "rogue_validator", "weight": 1},
            ],
            "slashed_agents": ["rogue_validator"],
        }
        with pytest.raises(MultisigVerificationError) as exc_info:
            verifier.verify_bft_certificate(cert)
        assert "slashed validator" in str(exc_info.value)


class TestMultisigMCPServer:

    def test_mcp_multisig_consensus(self):
        server = SolanaLensMCPServer()
        req = {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/call",
            "params": {
                "name": "solana_simulate_multisig_consensus",
                "arguments": {
                    "present_signers": ["agent_a", "agent_b"],
                    "threshold": 2,
                    "total_members": 3,
                },
            },
        }
        resp = server.handle_request(req)
        assert resp["id"] == 99
        content = json.loads(resp["result"]["content"][0]["text"])
        assert content["is_authorized"] is True
        assert content["valid_signatures"] == 2

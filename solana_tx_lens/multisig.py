"""
Multi-Agent Swarm Consensus & Threshold Multisig Validator for Solana transactions.
Verifies threshold signatures and BFT consensus certificates before simulation,
preventing execution of unauthorized, under-threshold, or Byzantine-compromised transactions.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union


class MultisigVerificationError(Exception):
    """Raised when a transaction does not satisfy threshold or BFT consensus requirements."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class MultisigConsensusVerifier:
    """
    Validates that a Solana transaction has received sufficient cryptographic
    authorizations from an agent swarm or multisig committee before pre-flight simulation.
    """

    def __init__(
        self,
        threshold: int = 1,
        total_members: int = 1,
        allowed_signers: Optional[List[str]] = None,
        slashed_members: Optional[List[str]] = None,
    ):
        self.threshold = threshold
        self.total_members = max(total_members, threshold)
        self.allowed_signers: Set[str] = set(allowed_signers or [])
        self.slashed_members: Set[str] = set(slashed_members or [])

    def verify_signers(
        self,
        present_signers: List[str],
        instruction_signers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Validates present transaction signers against threshold and exclusion lists.
        """
        signers_set = set(present_signers)
        if instruction_signers:
            signers_set.update(instruction_signers)

        # Check for slashed members
        slashed_present = signers_set.intersection(self.slashed_members)
        if slashed_present:
            raise MultisigVerificationError(
                f"Transaction contains signatures from slashed/Byzantine members: {sorted(list(slashed_present))}",
                details={"slashed_signers": sorted(list(slashed_present))},
            )

        # Check against allowed signers if whitelist is configured
        if self.allowed_signers:
            valid_signers = signers_set.intersection(self.allowed_signers)
        else:
            valid_signers = signers_set

        valid_count = len(valid_signers)
        is_satisfied = valid_count >= self.threshold

        result = {
            "is_authorized": is_satisfied,
            "threshold": self.threshold,
            "valid_signatures": valid_count,
            "required_signatures": self.threshold,
            "valid_signers": sorted(list(valid_signers)),
            "slashed_signers_detected": [],
            "timestamp": time.time(),
        }

        if not is_satisfied:
            raise MultisigVerificationError(
                f"Threshold not met: {valid_count}/{self.threshold} required signatures present.",
                details=result,
            )

        return result

    def verify_bft_certificate(
        self,
        certificate: Union[Dict[str, Any], Any],
    ) -> Dict[str, Any]:
        """
        Validates an agent-witness BFTConsensusCertificate.
        Ensures that committed weight meets quorum threshold and no slashed validators contributed.
        """
        cert = certificate if isinstance(certificate, dict) else certificate.to_dict()

        committed_weight = cert.get("committed_weight", 0)
        quorum_threshold = cert.get("quorum_threshold", 0)
        is_finalized = cert.get("is_finalized", False)
        slashed_agents = set(cert.get("slashed_agents", []))
        precommits = cert.get("precommits", [])

        if not is_finalized:
            raise MultisigVerificationError(
                "BFT consensus certificate is not finalized.",
                details={"certificate_id": cert.get("certificate_id")},
            )

        if committed_weight < quorum_threshold:
            raise MultisigVerificationError(
                f"BFT certificate quorum not met: {committed_weight} < {quorum_threshold}",
                details={"committed_weight": committed_weight, "quorum_threshold": quorum_threshold},
            )

        # Validate that precommit votes do not originate from slashed agents
        valid_precommit_weight = 0
        voted_agents = set()

        for vote in precommits:
            agent = vote.get("agent_id") if isinstance(vote, dict) else getattr(vote, "agent_id", "")
            weight = vote.get("weight", 1) if isinstance(vote, dict) else getattr(vote, "weight", 1)

            if agent in slashed_agents or agent in self.slashed_members:
                raise MultisigVerificationError(
                    f"Byzantine fault: Precommit from slashed validator '{agent}' included in quorum.",
                    details={"slashed_validator": agent},
                )
            if agent in voted_agents:
                raise MultisigVerificationError(
                    f"Equivocation detected: Duplicate vote from validator '{agent}'.",
                    details={"equivocating_validator": agent},
                )
            voted_agents.add(agent)
            valid_precommit_weight += weight

        if valid_precommit_weight < quorum_threshold:
            raise MultisigVerificationError(
                f"Valid precommit weight ({valid_precommit_weight}) < quorum threshold ({quorum_threshold}).",
                details={"valid_weight": valid_precommit_weight, "quorum_threshold": quorum_threshold},
            )

        return {
            "status": "verified",
            "certificate_id": cert.get("certificate_id"),
            "trajectory_id": cert.get("trajectory_id"),
            "quorum_achieved": True,
            "quorum_threshold": quorum_threshold,
            "committed_weight": committed_weight,
            "validator_count": len(voted_agents),
            "timestamp": time.time(),
        }

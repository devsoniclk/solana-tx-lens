"""
agent-witness integration for solana-tx-lens.
Enables automatic cryptographic Merkle attestation of transaction simulations,
compute unit profiling, and CPI call graphs with zero-dependency standalone fallback.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional
from .models import SimulationResult

try:
    import agent_witness
    from agent_witness.models import StepType
    from agent_witness.receipt import WitnessEngine
    HAS_WITNESS = True
except ImportError:
    HAS_WITNESS = False
    class StepType:  # type: ignore
        TOOL_RESULT = "tool_result"
        TOOL_CALL = "tool_call"
        OBSERVATION = "observation"
        THOUGHT = "thought"
        DECISION = "decision"


def attest_simulation_result(
    result: SimulationResult,
    engine: Optional[Any] = None,
    agent_id: str = "solana-trading-agent",
) -> Dict[str, Any]:
    """
    Attests a transaction simulation into an agent-witness deliberation step.
    """
    step_desc = f"Solana Simulation: success={result.success}, CUs={result.total_compute_units}/{result.max_compute_units}"
    prog_ids = []
    for r in result.cpi_roots:
        prog_ids.append(r.program_id)
        for c in r.children:
            prog_ids.append(c.program_id)

    meta = {
        "success": result.success,
        "total_compute_units": result.total_compute_units,
        "max_compute_units": result.max_compute_units,
        "cpi_invocations_count": len(result.cpi_roots),
        "program_ids": sorted(set(prog_ids)),
        "account_diffs_count": len(result.account_diffs),
        "token_diffs_count": len(result.token_diffs),
        "error": result.error.name if result.error else None,
    }

    eng = engine or (WitnessEngine(agent_id=agent_id) if HAS_WITNESS else None)
    if eng:
        step = eng.record_step(StepType.TOOL_RESULT, step_desc, metadata=meta)
        return {
            "attested": True,
            "step_index": getattr(step, "index", 0),
            "success": result.success,
            "compute_units": result.total_compute_units,
            "witness_installed": HAS_WITNESS,
        }
    else:
        return {
            "attested": False,
            "reason": "agent-witness not installed",
            "witness_installed": False,
        }

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CPIInvocation:
    program_id: str
    depth: int
    consumed_cus: int = 0
    logs: List[str] = field(default_factory=list)
    children: List["CPIInvocation"] = field(default_factory=list)
    failed: bool = False
    error_message: Optional[str] = None


@dataclass
class AccountDiff:
    pubkey: str
    pre_lamports: int
    post_lamports: int
    lamports_delta: int
    pre_owner: str
    post_owner: str
    data_len_delta: int


@dataclass
class ErrorInfo:
    error_type: str  # "Anchor", "System", "Token", "ComputeBudget", "Custom"
    code: int
    name: str
    description: str
    program_id: Optional[str] = None


@dataclass
class SimulationResult:
    success: bool
    total_compute_units: int
    max_compute_units: int
    cpi_roots: List[CPIInvocation]
    account_diffs: List[AccountDiff]
    error: Optional[ErrorInfo] = None
    raw_logs: List[str] = field(default_factory=list)

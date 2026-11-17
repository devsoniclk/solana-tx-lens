from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .contention import ContentionReport
    from .optimizer import ComputeBudgetOptimization


@dataclass
class CPIInvocation:
    program_id: str
    depth: int
    program_name: Optional[str] = None
    instruction_name: Optional[str] = None
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
class TokenBalanceDiff:
    account: str
    mint: str
    owner: str
    pre_amount: float
    post_amount: float
    delta: float
    decimals: int
    symbol: Optional[str] = None


@dataclass
class ErrorInfo:
    error_type: str  # "Anchor", "System", "Token", "ComputeBudget", "Custom"
    code: int
    name: str
    description: str
    program_id: Optional[str] = None


@dataclass
class HealthIssue:
    check: str
    severity: str  # "INFO", "WARNING", "CRITICAL"
    message: str
    recommendation: str


@dataclass
class SimulationHealth:
    status: str  # "HEALTHY", "WARNING", "CRITICAL_FAILURE"
    cu_utilization_pct: float
    issues: List[HealthIssue] = field(default_factory=list)
    has_critical_failure: bool = False


@dataclass
class SimulationResult:
    success: bool
    total_compute_units: int
    max_compute_units: int
    cpi_roots: List[CPIInvocation]
    account_diffs: List[AccountDiff]
    token_diffs: List[TokenBalanceDiff] = field(default_factory=list)
    health: Optional[SimulationHealth] = None
    error: Optional[ErrorInfo] = None
    optimization: Optional[Any] = None
    contention: Optional[Any] = None
    mev_radar: Optional[Any] = None
    route: Optional[Any] = None
    events_report: Optional[Any] = None
    shadow_snapshot: Optional[Any] = None
    stress_test: Optional[Any] = None
    token_extensions: Optional[Any] = None
    access_list_report: Optional[Any] = None
    policy_report: Optional[Any] = None
    raw_logs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_mermaid(self, diagram_type: str = "sequence") -> str:
        from .visualizer import render_cpi_mermaid_flowchart, render_cpi_mermaid_sequence

        if diagram_type == "flowchart":
            return render_cpi_mermaid_flowchart(self.cpi_roots)
        return render_cpi_mermaid_sequence(self.cpi_roots)

    def to_html(self, title: str = "Solana Transaction Simulation Dossier") -> str:
        from .html_report import render_html_report

        return render_html_report(
            self,
            optimization=self.optimization,
            contention=self.contention,
            title=title,
        )

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .models import SimulationResult


@dataclass
class SlippageSensitivityResult:
    tested_slippage_bps: int
    expected_out_amount: float
    min_out_amount: float
    revert_probability_pct: float
    status: str  # "SAFE", "TIGHT", "HIGH_REVERT_RISK"
    explanation: str


@dataclass
class CUSensitivityResult:
    simulated_cus: int
    configured_limit: int
    safety_buffer_cus: int
    buffer_percentage: float
    cliff_threshold_cus: int
    evaluation: str  # "CRITICAL_DEFICIT", "THIN_MARGIN", "HEALTHY", "OVERPROVISIONED"
    recommendation: str


@dataclass
class FeeVolatilityScenario:
    multiplier: float
    surge_tier: str
    implied_fee_lamports: int
    implied_fee_sol: float
    estimated_inclusion_delay_slots: int
    drop_risk_pct: float


@dataclass
class ExecutionSensitivityReport:
    robustness_score: int  # 0 to 100
    risk_tier: str  # "HIGH_RISK", "MODERATE_RISK", "ROBUST", "INSTITUTIONAL"
    slippage_matrix: List[SlippageSensitivityResult] = field(default_factory=list)
    cu_sensitivity: Optional[CUSensitivityResult] = None
    fee_volatility_scenarios: List[FeeVolatilityScenario] = field(default_factory=list)
    critical_vulnerabilities: List[str] = field(default_factory=list)
    actionable_recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "robustness_score": self.robustness_score,
            "risk_tier": self.risk_tier,
            "slippage_matrix": [dataclasses.asdict(s) for s in self.slippage_matrix],
            "cu_sensitivity": dataclasses.asdict(self.cu_sensitivity) if self.cu_sensitivity else None,
            "fee_volatility_scenarios": [dataclasses.asdict(f) for f in self.fee_volatility_scenarios],
            "critical_vulnerabilities": self.critical_vulnerabilities,
            "actionable_recommendations": self.actionable_recommendations,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class SlippageStressTester:
    """
    Stress-tests Solana transaction simulation outputs under adverse market conditions:
    AMM price impact jumps, slippage cliffs, compute unit truncation, and fee surges.
    """

    DEFAULT_SLIPPAGE_TEST_TIERS_BPS = [5, 15, 25, 50, 100, 250, 500]

    def __init__(self, target_slippage_bps: int = 50):
        self.target_slippage_bps = target_slippage_bps

    def evaluate(
        self,
        sim_result: SimulationResult,
        configured_cu_limit: Optional[int] = None,
        observed_slippage_bps: Optional[int] = None,
    ) -> ExecutionSensitivityReport:
        vulnerabilities: List[str] = []
        recommendations: List[str] = []
        deductions = 0

        # 1. CU Sensitivity Analysis
        consumed = sim_result.total_compute_units
        configured = configured_cu_limit or sim_result.max_compute_units or 200_000

        # Cliff threshold: on Solana, instructions jitter by +/- 5% to 15% due to dynamic branching
        cliff_cu = int(consumed * 1.02)
        buffer_cu = configured - consumed
        buffer_pct = (buffer_cu / consumed * 100) if consumed > 0 else 100.0

        if configured < consumed:
            cu_eval = "CRITICAL_DEFICIT"
            cu_rec = f"Transaction exceeds configured limit ({configured} < {consumed}). Set limit to at least {int(consumed * 1.15)}."
            vulnerabilities.append("Immediate ComputeLimitExceeded revert guaranteed on-chain.")
            deductions += 50
        elif buffer_pct < 8.0:
            cu_eval = "THIN_MARGIN"
            cu_rec = f"Compute unit margin is razor-thin (+{buffer_pct:.1f}%). Increase safety buffer to +15% ({int(consumed * 1.15)} CUs)."
            vulnerabilities.append(f"Razor-thin compute buffer (+{buffer_pct:.1f}%): high risk of runtime CPI jitter failure.")
            deductions += 25
        elif buffer_pct > 150.0 and consumed > 1000:
            cu_eval = "OVERPROVISIONED"
            cu_rec = f"Overprovisioned by +{buffer_pct:.1f}%. Right-size compute unit limit to {int(consumed * 1.15)} to reduce scheduler footprint."
            deductions += 5
        else:
            cu_eval = "HEALTHY"
            cu_rec = f"Optimal safety buffer (+{buffer_pct:.1f}% / +{buffer_cu:,} CUs)."

        cu_res = CUSensitivityResult(
            simulated_cus=consumed,
            configured_limit=configured,
            safety_buffer_cus=buffer_cu,
            buffer_percentage=buffer_pct,
            cliff_threshold_cus=cliff_cu,
            evaluation=cu_eval,
            recommendation=cu_rec,
        )

        # 2. Slippage & DEX Route Sensitivity
        slippage_matrix: List[SlippageSensitivityResult] = []
        user_bps = observed_slippage_bps or self.target_slippage_bps

        # Infer token output if available
        token_out_amount = 100.0
        if sim_result.token_diffs:
            positives = [d.delta for d in sim_result.token_diffs if d.delta > 0]
            if positives:
                token_out_amount = max(positives)

        for bps in self.DEFAULT_SLIPPAGE_TEST_TIERS_BPS:
            frac = bps / 10_000.0
            min_out = token_out_amount * (1.0 - frac)

            # Revert probability model based on network volatility
            if bps <= 5:
                prob = 85.0
                status = "HIGH_REVERT_RISK"
                expl = f"5 bps is ultra-tight; normal pool micro-volatility causes >85% failure."
            elif bps <= 15:
                prob = 40.0
                status = "TIGHT"
                expl = f"15 bps acceptable only in calm blocks or low-volume pairs."
            elif bps <= 50:
                prob = 5.0
                status = "SAFE"
                expl = f"{bps} bps standard institutional execution tolerance."
            elif bps <= 150:
                prob = 1.0
                status = "SAFE"
                expl = f"{bps} bps guarantees inclusion but exposes to sandwich extraction."
            else:
                prob = 0.5
                status = "HIGH_REVERT_RISK"
                expl = f"{bps} bps excessive; MEV sandwich bot guaranteed extraction."

            slippage_matrix.append(
                SlippageSensitivityResult(
                    tested_slippage_bps=bps,
                    expected_out_amount=token_out_amount,
                    min_out_amount=min_out,
                    revert_probability_pct=prob,
                    status=status,
                    explanation=expl,
                )
            )

        if user_bps < 15:
            vulnerabilities.append(f"Target slippage ({user_bps} bps) is vulnerable to micro-price drift revert (0x1771).")
            deductions += 20
        elif user_bps > 150:
            vulnerabilities.append(f"Target slippage ({user_bps} bps) leaves large attack surface for sandwich bots.")
            deductions += 15

        # 3. Priority Fee Volatility Stress Testing
        # Test base priority fee at 10,000 micro-lamports / CU
        base_microlamports_per_cu = 10_000
        volatility_scenarios: List[FeeVolatilityScenario] = []
        multipliers = [
            (1.0, "Current Benchmark", 0, 0.0),
            (2.0, "Moderate Congestion (+100%)", 1, 5.0),
            (5.0, "NFT Mint / Token Launch Surge (+400%)", 3, 25.0),
            (10.0, "Extreme Block Contention (+900%)", 8, 65.0),
            (25.0, "Network Shock (+2400%)", 20, 92.0),
        ]

        for mult, label, delay_slots, drop_risk in multipliers:
            rate = int(base_microlamports_per_cu * mult)
            fee_lamports = int(rate * consumed / 1_000_000)
            volatility_scenarios.append(
                FeeVolatilityScenario(
                    multiplier=mult,
                    surge_tier=label,
                    implied_fee_lamports=fee_lamports,
                    implied_fee_sol=fee_lamports / 1_000_000_000,
                    estimated_inclusion_delay_slots=delay_slots,
                    drop_risk_pct=drop_risk,
                )
            )

        # 4. Check MEV & Contention if present
        if hasattr(sim_result, "mev_radar") and sim_result.mev_radar:
            radar = sim_result.mev_radar
            is_high_mev = getattr(radar, "risk_level", "") in ("HIGH", "CRITICAL") or getattr(radar, "is_sandwich_vulnerable", False)
            if is_high_mev:
                vulnerabilities.append(f"Pre-flight MEV Radar flagged high sandwich exposure ({getattr(radar, 'risk_level', 'HIGH')}).")
                deductions += 25
                recommendations.append("Route via private Jito bundle or decrease slippage bound to protect against sandwich bots.")

        if hasattr(sim_result, "contention") and sim_result.contention:
            cnt = sim_result.contention
            is_high_cnt = getattr(cnt, "concurrency_verdict", "") == "SEVERE_LOCK_CONTENTION" or getattr(cnt, "hotspot_count", 0) > 0
            if is_high_cnt:
                hotspot_len = len(getattr(cnt, "hotspot_accounts", []))
                vulnerabilities.append(f"Account write-lock contention detected on {hotspot_len} hotspot accounts.")
                deductions += 15
                recommendations.append("Apply high priority fee tier to win write-lock scheduling races.")

        # Compute final Robustness Score
        final_score = max(5, 100 - deductions)
        if final_score >= 85:
            tier = "INSTITUTIONAL"
        elif final_score >= 70:
            tier = "ROBUST"
        elif final_score >= 50:
            tier = "MODERATE_RISK"
        else:
            tier = "HIGH_RISK"

        if not recommendations:
            recommendations.append("Transaction parameters are well-calibrated for current block conditions.")

        return ExecutionSensitivityReport(
            robustness_score=final_score,
            risk_tier=tier,
            slippage_matrix=slippage_matrix,
            cu_sensitivity=cu_res,
            fee_volatility_scenarios=volatility_scenarios,
            critical_vulnerabilities=vulnerabilities,
            actionable_recommendations=recommendations,
        )


def stress_test_simulation(
    sim_result: SimulationResult,
    configured_cu_limit: Optional[int] = None,
    observed_slippage_bps: Optional[int] = None,
) -> ExecutionSensitivityReport:
    """Convenience helper to run execution stress tests on a SimulationResult."""
    tester = SlippageStressTester()
    return tester.evaluate(
        sim_result,
        configured_cu_limit=configured_cu_limit,
        observed_slippage_bps=observed_slippage_bps,
    )

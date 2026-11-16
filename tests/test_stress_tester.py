from __future__ import annotations

from solana_tx_lens.models import AccountDiff, CPIInvocation, SimulationResult
from solana_tx_lens.stress_tester import SlippageStressTester, stress_test_simulation


def test_stress_test_cu_margin_deficit():
    res = SimulationResult(
        success=True,
        total_compute_units=210_000,
        max_compute_units=200_000,
        cpi_roots=[],
        account_diffs=[],
    )

    report = stress_test_simulation(res, configured_cu_limit=200_000)
    assert report.cu_sensitivity is not None
    assert report.cu_sensitivity.evaluation == "CRITICAL_DEFICIT"
    assert report.robustness_score < 60
    assert any("ComputeLimitExceeded" in v for v in report.critical_vulnerabilities)


def test_stress_test_cu_thin_margin():
    res = SimulationResult(
        success=True,
        total_compute_units=195_000,
        max_compute_units=200_000,
        cpi_roots=[],
        account_diffs=[],
    )

    report = stress_test_simulation(res, configured_cu_limit=200_000)
    assert report.cu_sensitivity is not None
    assert report.cu_sensitivity.evaluation == "THIN_MARGIN"
    assert any("thin compute buffer" in v.lower() for v in report.critical_vulnerabilities)


def test_stress_test_optimal_resilience():
    res = SimulationResult(
        success=True,
        total_compute_units=80_000,
        max_compute_units=200_000,
        cpi_roots=[],
        account_diffs=[],
    )

    report = stress_test_simulation(res, configured_cu_limit=95_000, observed_slippage_bps=50)
    assert report.cu_sensitivity is not None
    assert report.cu_sensitivity.evaluation == "HEALTHY"
    assert report.robustness_score >= 80
    assert report.risk_tier in ("ROBUST", "INSTITUTIONAL")
    assert len(report.slippage_matrix) == 7
    assert len(report.fee_volatility_scenarios) == 5


def test_stress_test_extreme_slippage_risk():
    res = SimulationResult(
        success=True,
        total_compute_units=50_000,
        max_compute_units=200_000,
        cpi_roots=[],
        account_diffs=[],
    )

    # User configured 5 bps slippage (too tight)
    rep_tight = stress_test_simulation(res, observed_slippage_bps=5)
    assert any("micro-price drift" in v for v in rep_tight.critical_vulnerabilities)

    # User configured 300 bps slippage (sandwich vulnerable)
    rep_wide = stress_test_simulation(res, observed_slippage_bps=300)
    assert any("sandwich" in v for v in rep_wide.critical_vulnerabilities)

from __future__ import annotations

from solana_tx_lens.models import AccountDiff, CPIInvocation, SimulationResult, TokenBalanceDiff
from solana_tx_lens.policy import PolicyRule, verify_simulation_policy


def _create_mock_simulation(
    cus: int = 150_000,
    cpi_programs: list[str] | None = None,
    lamports_delta: int = -5_000,
    token_delta: float = 10.0,
) -> SimulationResult:
    programs = cpi_programs or ["ComputeBudget111111111111111111111111111111", "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"]
    cpi_roots = [
        CPIInvocation(program_id=pid, depth=1, consumed_cus=cus // len(programs))
        for pid in programs
    ]
    account_diffs = [
        AccountDiff(
            pubkey="UserWallet111111111111111111111111111111111",
            pre_lamports=1_000_000_000,
            post_lamports=1_000_000_000 + lamports_delta,
            lamports_delta=lamports_delta,
            pre_owner="11111111111111111111111111111111",
            post_owner="11111111111111111111111111111111",
            data_len_delta=0,
        )
    ]
    token_diffs = [
        TokenBalanceDiff(
            account="UserTokenAcc1111111111111111111111111111111",
            mint="USDC1111111111111111111111111111111111111111",
            owner="UserWallet111111111111111111111111111111111",
            pre_amount=100.0,
            post_amount=100.0 + token_delta,
            delta=token_delta,
            decimals=6,
            symbol="USDC",
        )
    ]
    return SimulationResult(
        success=True,
        total_compute_units=cus,
        max_compute_units=300_000,
        cpi_roots=cpi_roots,
        account_diffs=account_diffs,
        token_diffs=token_diffs,
    )


def test_verify_policy_all_pass():
    sim = _create_mock_simulation()
    rules = [
        PolicyRule(
            rule_id="r_cu",
            rule_type="max_compute_units",
            params={"limit": 200_000},
        ),
        PolicyRule(
            rule_id="r_req",
            rule_type="required_programs",
            params={"program_ids": ["JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"]},
        ),
        PolicyRule(
            rule_id="r_tok",
            rule_type="min_token_receive",
            params={"mint": "USDC1111111111111111111111111111111111111111", "min_amount": 5.0},
        ),
    ]
    rep = verify_simulation_policy(sim, rules)
    assert rep.passed
    assert rep.violations_count == 0
    assert rep.total_rules_evaluated == 3


def test_verify_policy_forbidden_program_violation():
    sim = _create_mock_simulation(cpi_programs=["DrainerProgram11111111111111111111111111111"])
    rules = [
        PolicyRule(
            rule_id="r_forbid",
            rule_type="forbidden_programs",
            severity="CRITICAL",
            params={"program_ids": ["DrainerProgram11111111111111111111111111111"]},
        )
    ]
    rep = verify_simulation_policy(sim, rules)
    assert not rep.passed
    assert rep.has_critical_violations
    assert rep.violations_count == 1
    assert rep.violations[0].rule_id == "r_forbid"


def test_verify_policy_max_sol_loss_violation():
    sim = _create_mock_simulation(lamports_delta=-50_000_000)  # lost 0.05 SOL
    rules = [
        {
            "rule_id": "r_sol_loss",
            "rule_type": "max_sol_loss",
            "severity": "CRITICAL",
            "params": {
                "account": "UserWallet111111111111111111111111111111111",
                "max_loss_lamports": 10_000_000,  # max 0.01 SOL
            },
        }
    ]
    rep = verify_simulation_policy(sim, rules)
    assert not rep.passed
    assert rep.violations_count == 1
    assert "exceeded cap" in rep.violations[0].message


def test_verify_policy_min_token_receive_failure():
    sim = _create_mock_simulation(token_delta=1.5)
    rules = [
        {
            "rule_id": "r_min_out",
            "rule_type": "min_token_receive",
            "severity": "CRITICAL",
            "params": {"min_amount": 10.0},
        }
    ]
    rep = verify_simulation_policy(sim, rules)
    assert not rep.passed
    assert rep.violations_count == 1
    assert rep.violations[0].actual_value == 1.5

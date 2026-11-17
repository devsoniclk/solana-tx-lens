from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

if TYPE_CHECKING:
    from .models import SimulationResult


@dataclass
class PolicyRule:
    rule_id: str
    rule_type: str  # "min_sol_balance", "max_sol_loss", "min_token_receive", "max_token_spend", "forbidden_programs", "required_programs", "max_compute_units", "require_owner_unchanged"
    severity: str = "CRITICAL"  # "INFO", "WARNING", "CRITICAL"
    params: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None


@dataclass
class PolicyViolation:
    rule_id: str
    rule_type: str
    severity: str
    message: str
    actual_value: Any = None
    expected_value: Any = None


@dataclass
class PolicyVerificationReport:
    passed: bool
    total_rules_evaluated: int
    violations_count: int
    has_critical_violations: bool
    violations: List[PolicyViolation] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def _collect_all_invoked_programs(cpi_roots: List[Any]) -> Set[str]:
    programs = set()

    def _traverse(node: Any):
        if hasattr(node, "program_id") and node.program_id:
            programs.add(node.program_id)
        for child in getattr(node, "children", []):
            _traverse(child)

    for root in cpi_roots:
        _traverse(root)
    return programs


def verify_simulation_policy(
    simulation: SimulationResult,
    rules: List[PolicyRule | Dict[str, Any]],
) -> PolicyVerificationReport:
    """
    Evaluates declarative safety assertion rules against a simulated Solana transaction.
    Protects autonomous AI agents and automated trading systems from malicious CPIs,
    excessive slippage, unauthorized state transfers, and fund drain.
    """
    normalized_rules: List[PolicyRule] = []
    for r in rules:
        if isinstance(r, PolicyRule):
            normalized_rules.append(r)
        elif isinstance(r, dict):
            normalized_rules.append(
                PolicyRule(
                    rule_id=r.get("rule_id", r.get("id", "rule")),
                    rule_type=r.get("rule_type", r.get("type", "")),
                    severity=r.get("severity", "CRITICAL").upper(),
                    params=r.get("params", {}),
                    description=r.get("description"),
                )
            )

    violations: List[PolicyViolation] = []
    all_invoked_programs = _collect_all_invoked_programs(simulation.cpi_roots)

    # Pre-index account diffs and token diffs
    account_diff_map = {d.pubkey: d for d in simulation.account_diffs}
    token_diff_list = simulation.token_diffs or []

    for rule in normalized_rules:
        rtype = rule.rule_type.lower()
        p = rule.params

        if rtype == "max_compute_units":
            limit = p.get("limit", 200_000)
            if simulation.total_compute_units > limit:
                violations.append(
                    PolicyViolation(
                        rule_id=rule.rule_id,
                        rule_type=rule.rule_type,
                        severity=rule.severity,
                        message=f"Compute unit limit exceeded: consumed {simulation.total_compute_units} CUs (limit: {limit})",
                        actual_value=simulation.total_compute_units,
                        expected_value=limit,
                    )
                )

        elif rtype == "forbidden_programs":
            forbidden = set(p.get("program_ids", []))
            overlap = all_invoked_programs.intersection(forbidden)
            if overlap:
                violations.append(
                    PolicyViolation(
                        rule_id=rule.rule_id,
                        rule_type=rule.rule_type,
                        severity=rule.severity,
                        message=f"Forbidden program(s) invoked in simulation tree: {', '.join(sorted(overlap))}",
                        actual_value=list(overlap),
                        expected_value=[],
                    )
                )

        elif rtype == "required_programs":
            required = set(p.get("program_ids", []))
            missing = required.difference(all_invoked_programs)
            if missing:
                violations.append(
                    PolicyViolation(
                        rule_id=rule.rule_id,
                        rule_type=rule.rule_type,
                        severity=rule.severity,
                        message=f"Required program(s) not invoked in simulation: {', '.join(sorted(missing))}",
                        actual_value=list(all_invoked_programs),
                        expected_value=list(required),
                    )
                )

        elif rtype == "max_sol_loss":
            account = p.get("account")
            max_loss_lamports = p.get("max_loss_lamports", 0)
            if account in account_diff_map:
                delta = account_diff_map[account].lamports_delta
                # delta < 0 means loss
                if delta < 0 and abs(delta) > max_loss_lamports:
                    violations.append(
                        PolicyViolation(
                            rule_id=rule.rule_id,
                            rule_type=rule.rule_type,
                            severity=rule.severity,
                            message=f"SOL balance loss for {account[:8]}... ({abs(delta)} lamports) exceeded cap ({max_loss_lamports} lamports)",
                            actual_value=abs(delta),
                            expected_value=max_loss_lamports,
                        )
                    )

        elif rtype == "min_sol_balance":
            account = p.get("account")
            min_post = p.get("min_lamports", 0)
            if account in account_diff_map:
                post = account_diff_map[account].post_lamports
                if post < min_post:
                    violations.append(
                        PolicyViolation(
                            rule_id=rule.rule_id,
                            rule_type=rule.rule_type,
                            severity=rule.severity,
                            message=f"Post-simulation SOL balance for {account[:8]}... ({post} lamports) below minimum threshold ({min_post} lamports)",
                            actual_value=post,
                            expected_value=min_post,
                        )
                    )

        elif rtype == "min_token_receive":
            mint = p.get("mint")
            owner = p.get("owner")
            min_amount = p.get("min_amount", 0.0)
            matched_diffs = [
                td for td in token_diff_list
                if (not mint or td.mint == mint) and (not owner or td.owner == owner)
            ]
            total_received = sum(td.delta for td in matched_diffs if td.delta > 0)
            if total_received < min_amount:
                violations.append(
                    PolicyViolation(
                        rule_id=rule.rule_id,
                        rule_type=rule.rule_type,
                        severity=rule.severity,
                        message=f"Received token amount for mint {mint or 'any'} ({total_received}) below minimum threshold ({min_amount})",
                        actual_value=total_received,
                        expected_value=min_amount,
                    )
                )

        elif rtype == "max_token_spend":
            mint = p.get("mint")
            owner = p.get("owner")
            max_spend = p.get("max_amount", 0.0)
            matched_diffs = [
                td for td in token_diff_list
                if (not mint or td.mint == mint) and (not owner or td.owner == owner)
            ]
            total_spent = sum(abs(td.delta) for td in matched_diffs if td.delta < 0)
            if total_spent > max_spend:
                violations.append(
                    PolicyViolation(
                        rule_id=rule.rule_id,
                        rule_type=rule.rule_type,
                        severity=rule.severity,
                        message=f"Token spend for mint {mint or 'any'} ({total_spent}) exceeded limit ({max_spend})",
                        actual_value=total_spent,
                        expected_value=max_spend,
                    )
                )

        elif rtype == "require_owner_unchanged":
            target_accounts = set(p.get("accounts", []))
            for acc in target_accounts:
                if acc in account_diff_map:
                    ad = account_diff_map[acc]
                    if ad.pre_owner != ad.post_owner:
                        violations.append(
                            PolicyViolation(
                                rule_id=rule.rule_id,
                                rule_type=rule.rule_type,
                                severity=rule.severity,
                                message=f"Account owner mutated for {acc[:8]}... from {ad.pre_owner} to {ad.post_owner}",
                                actual_value=ad.post_owner,
                                expected_value=ad.pre_owner,
                            )
                        )

    has_crit = any(v.severity == "CRITICAL" for v in violations)
    passed = len(violations) == 0 or not has_crit

    if len(violations) == 0:
        summary = f"All {len(normalized_rules)} safety assertion rules verified successfully."
    else:
        summary = f"Policy verification failed with {len(violations)} violation(s) across {len(normalized_rules)} evaluated rules."

    return PolicyVerificationReport(
        passed=passed,
        total_rules_evaluated=len(normalized_rules),
        violations_count=len(violations),
        has_critical_violations=has_crit,
        violations=violations,
        summary=summary,
    )

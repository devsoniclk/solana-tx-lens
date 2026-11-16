from __future__ import annotations

import re
from typing import Dict, List, Set
from .models import AccountDiff, CPIInvocation, SimulationResult, TokenBalanceDiff


def _clean_mermaid_id(raw: str) -> str:
    """Sanitizes a string into a valid Mermaid participant/node identifier."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", raw)
    if not cleaned or cleaned[0].isdigit():
        cleaned = "p_" + cleaned
    return cleaned


def render_cpi_tree(roots: List[CPIInvocation], indent: str = "") -> str:
    """
    Renders a recursive CPI tree into clean, structured ASCII format,
    including program friendly names and recognized instruction names.
    """
    lines: List[str] = []

    for i, node in enumerate(roots):
        is_last = i == len(roots) - 1
        branch = "└── " if is_last else "├── "
        status = "[FAILED]" if node.failed else "[OK]"
        cu_str = f"({node.consumed_cus:,} CUs)" if node.consumed_cus else ""

        prog_display = f"{node.program_id}"
        if node.program_name and node.program_name != node.program_id:
            prog_display = f"{node.program_name} ({node.program_id[:4]}...{node.program_id[-4:]})"

        instr_display = f" -> {node.instruction_name}" if node.instruction_name else ""
        line = f"{indent}{branch}{status} {prog_display} [depth {node.depth}]{instr_display} {cu_str}".strip()
        lines.append(line)

        if node.error_message:
            child_indent = indent + ("    " if is_last else "│   ")
            lines.append(f"{child_indent}└── ERROR: {node.error_message}")

        if node.children:
            child_indent = indent + ("    " if is_last else "│   ")
            lines.append(render_cpi_tree(node.children, indent=child_indent))

    return "\n".join(lines)


def render_cpi_mermaid_sequence(roots: List[CPIInvocation]) -> str:
    """
    Generates a GitHub-flavored Mermaid sequence diagram of the CPI execution tree.
    """
    lines = ["sequenceDiagram", "    autonumber", "    actor Client as Caller / Bot"]
    participants: Dict[str, str] = {}

    def collect_participants(nodes: List[CPIInvocation]):
        for node in nodes:
            if node.program_id not in participants:
                alias = f"P_{len(participants) + 1}_{_clean_mermaid_id(node.program_name or node.program_id[:8])}"
                display = node.program_name or f"{node.program_id[:4]}...{node.program_id[-4:]}"
                participants[node.program_id] = alias
                lines.append(f"    participant {alias} as {display}")
            collect_participants(node.children)

    collect_participants(roots)

    def trace_calls(nodes: List[CPIInvocation], parent_alias: str):
        for node in nodes:
            curr_alias = participants[node.program_id]
            call_label = f"invoke [d={node.depth}]"
            if node.instruction_name:
                call_label += f" ({node.instruction_name})"

            lines.append(f"    {parent_alias}->>+{curr_alias}: {call_label}")

            if node.children:
                trace_calls(node.children, curr_alias)

            if node.failed:
                err_text = (node.error_message or "Execution failed").replace('"', "'")
                if len(err_text) > 40:
                    err_text = err_text[:37] + "..."
                lines.append(f"    {curr_alias}-->>-{parent_alias}: [FAIL] {err_text}")
            else:
                cu_label = f"{node.consumed_cus:,} CUs" if node.consumed_cus else "OK"
                lines.append(f"    {curr_alias}-->>-{parent_alias}: success ({cu_label})")

    trace_calls(roots, "Client")
    return "\n".join(lines)


def render_cpi_mermaid_flowchart(roots: List[CPIInvocation]) -> str:
    """
    Generates a Mermaid flowchart (graph TD) representing the call hierarchy.
    """
    lines = ["flowchart TD", '    Start(["Transaction Entrypoint"])']
    counter = 0

    def traverse(nodes: List[CPIInvocation], parent_node: str):
        nonlocal counter
        for node in nodes:
            counter += 1
            node_id = f"node_{counter}"
            label_name = node.program_name or f"{node.program_id[:4]}...{node.program_id[-4:]}"
            instr = f"<br/>{node.instruction_name}" if node.instruction_name else ""
            cus = f"<br/>{node.consumed_cus:,} CUs" if node.consumed_cus else ""

            if node.failed:
                lines.append(f'    {node_id}["❌ {label_name}{instr}{cus}"]:::failNode')
            else:
                lines.append(f'    {node_id}["✓ {label_name}{instr}{cus}"]:::okNode')

            lines.append(f"    {parent_node} -->|depth {node.depth}| {node_id}")

            if node.children:
                traverse(node.children, node_id)

    traverse(roots, "Start")
    lines.append("    classDef okNode fill:#10B981,stroke:#059669,color:#ffffff,stroke-width:2px;")
    lines.append("    classDef failNode fill:#EF4444,stroke:#DC2626,color:#ffffff,stroke-width:2px;")
    return "\n".join(lines)


def render_simulation_report(result: SimulationResult) -> str:
    """
    Generates a full diagnostic terminal report for a simulation result,
    including CPI tree, token mutations, account diffs, health guard status,
    compute budget optimizer, and account contention audit.
    """
    header = [
        "==================================================================",
        " SOLANA TRANSACTION SIMULATION DIAGNOSTIC REPORT (v0.3.0)",
        "==================================================================",
        f"Status:             {'SUCCESS' if result.success else 'FAILED'}",
        (
            f"Total Compute Used: {result.total_compute_units:,} / "
            f"{result.max_compute_units:,} CUs ({(result.total_compute_units / max(1, result.max_compute_units) * 100):.1f}%)"
        ),
    ]

    if result.health:
        header.extend([
            f"Health Status:      {result.health.status}",
            f"CU Utilization:     {result.health.cu_utilization_pct:.1f}%",
        ])

    if result.error:
        header.extend([
            f"Error Type:         {result.error.error_type}",
            f"Error Name:         {result.error.name} (Code: {result.error.code})",
            f"Description:        {result.error.description}",
        ])

    # Pre-flight Health & MEV Checks
    if result.health and result.health.issues:
        header.append("\n[Pre-flight Safety & MEV Health Checks]")
        for iss in result.health.issues:
            icon = "🔴" if iss.severity == "CRITICAL" else ("🟡" if iss.severity == "WARNING" else "ℹ️")
            header.append(f"  {icon} [{iss.severity}] {iss.check}: {iss.message}")
            header.append(f"     └─ Rec: {iss.recommendation}")

    # Compute Budget & Priority Fee Optimization
    if result.optimization:
        opt = result.optimization
        header.append("\n[Compute Budget & Priority Fee Optimization]")
        header.append(f"  Recommended Limit:  {opt.recommended_limit:,} CUs (+{int(opt.safety_buffer_pct*100)}% buffer)")
        header.append(f"  Allocation Savings: {opt.cu_savings:,} CUs ({opt.cu_savings_pct}%) vs {opt.default_limit:,} baseline")
        header.append(f"  Summary:            {opt.recommendation_summary}")
        header.append("  Estimated Transaction Fees by Priority Tier:")
        for tier, cost in opt.estimated_tx_fees_sol.items():
            u_lamports = opt.priority_fee_micro_lamports.get(tier, 0)
            header.append(f"    - {tier.capitalize():<7}: {cost:.6f} SOL ({u_lamports:,} µ-lamports/CU)")

    # Account Lock Contention & Parallelism Audit
    if result.contention:
        cnt = result.contention
        header.append("\n[Account Write-Lock Contention & Parallelism]")
        header.append(f"  Concurrency Verdict:     {cnt.concurrency_verdict}")
        header.append(f"  Parallelizability Score: {cnt.parallelizability_score:.2f} ({int(cnt.parallelizability_score*100)}%)")
        header.append(f"  Account Lock Ratios:     {cnt.writable_count} Writable / {cnt.readonly_count} Read-Only (Total: {cnt.total_accounts})")
        if cnt.hotspot_count > 0:
            header.append(f"  Locked Shared Hotspots:  {cnt.hotspot_count}")
        for w in cnt.warnings:
            header.append(f"  ⚠️ {w}")

    # MEV Vulnerability Radar
    if getattr(result, "mev_radar", None):
        radar = result.mev_radar
        header.append("\n[MEV Vulnerability Radar & Sandwich Protection]")
        header.append(f"  Risk Level:          {radar.risk_level}")
        header.append(f"  Sandwich Exposure:   {'YES (Vulnerable)' if radar.is_sandwich_vulnerable else 'NO (Protected/Low)'}")
        header.append(f"  Summary:             {radar.summary}")
        if radar.attack_vectors:
            for vec in radar.attack_vectors:
                header.append(f"  ⚠️ [{vec.severity}] {vec.vector_type}: {vec.description}")
        if radar.mitigations:
            header.append("  Mitigation Checklist:")
            for m in radar.mitigations:
                header.append(f"    ✓ {m}")

    # Multi-DEX Swap Route
    if getattr(result, "route", None) and result.route.is_swap:
        rt = result.route
        header.append("\n[Multi-DEX Swap Route & Flow]")
        header.append(f"  Hops:                {rt.total_hops} ({' -> '.join(rt.dexes_involved)})")
        header.append(f"  Route Flow:          {rt.ascii_diagram}")
        header.append(f"  Summary:             {rt.summary}")

    header.append("\n[Cross-Program Invocation (CPI) Execution Tree]")
    if result.cpi_roots:
        header.append(render_cpi_tree(result.cpi_roots))
    else:
        header.append("  (No program invocations recorded in logs)")

    # SPL Token Balance Mutations
    if result.token_diffs:
        header.append("\n[SPL Token Balance Mutations]")
        header.append(f"  {'Token Mint / Account':<44} | {'Token Delta':<18} | {'Owner'}")
        header.append("  " + "-" * 75)
        for td in result.token_diffs:
            sign = "+" if td.delta > 0 else ""
            delta_str = f"{sign}{td.delta:,.4f}"
            target = td.mint[:20] + "..." if len(td.mint) > 23 else td.mint
            owner_str = f"{td.owner[:6]}...{td.owner[-4:]}" if len(td.owner) > 12 else td.owner
            header.append(f"  {target:<44} | {delta_str:<18} | {owner_str}")

    # Account State Diffs
    header.append("\n[Account State Diffs]")
    if result.account_diffs:
        header.append(f"  {'Account Pubkey':<44} | {'Lamports Delta':<16} | {'Data Delta'}")
        header.append("  " + "-" * 75)
        for diff in result.account_diffs:
            sign = "+" if diff.lamports_delta > 0 else ""
            sol_delta = f"{sign}{diff.lamports_delta / 1e9:.6f} SOL"
            header.append(f"  {diff.pubkey:<44} | {sol_delta:<16} | {diff.data_len_delta:+d} bytes")
    else:
        header.append("  (No account balance or data changes)")

    header.append("==================================================================")
    return "\n".join(header)

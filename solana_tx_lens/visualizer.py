from typing import List
from .models import AccountDiff, CPIInvocation, SimulationResult


def render_cpi_tree(roots: List[CPIInvocation], indent: str = "") -> str:
    """
    Renders a recursive CPI tree into clean, structured ASCII format.
    """
    lines: List[str] = []

    for i, node in enumerate(roots):
        is_last = i == len(roots) - 1
        branch = "└── " if is_last else "├── "
        status = "[FAILED]" if node.failed else "[OK]"
        cu_str = f"({node.consumed_cus:,} CUs)" if node.consumed_cus else ""

        line = f"{indent}{branch}{status} Program: {node.program_id} [depth {node.depth}] {cu_str}"
        lines.append(line)

        if node.error_message:
            child_indent = indent + ("    " if is_last else "│   ")
            lines.append(f"{child_indent}└── ERROR: {node.error_message}")

        if node.children:
            child_indent = indent + ("    " if is_last else "│   ")
            lines.append(render_cpi_tree(node.children, indent=child_indent))

    return "\n".join(lines)


def render_simulation_report(result: SimulationResult) -> str:
    """
    Generates a full diagnostic terminal report for a simulation result.
    """
    header = [
        "==================================================================",
        f" SOLANA TRANSACTION SIMULATION DIAGNOSTIC REPORT",
        "==================================================================",
        f"Status:             {'SUCCESS' if result.success else 'FAILED'}",
        f"Total Compute Used: {result.total_compute_units:,} / {result.max_compute_units:,} CUs ({(result.total_compute_units / max(1, result.max_compute_units) * 100):.1f}%)",
    ]

    if result.error:
        header.extend([
            f"Error Type:         {result.error.error_type}",
            f"Error Name:         {result.error.name} (Code: {result.error.code})",
            f"Description:        {result.error.description}",
        ])

    header.append("\n[Cross-Program Invocation (CPI) Execution Tree]")
    if result.cpi_roots:
        header.append(render_cpi_tree(result.cpi_roots))
    else:
        header.append("  (No program invocations recorded in logs)")

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

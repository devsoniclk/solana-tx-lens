from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .instruction_decoder import KNOWN_PROGRAMS
from .mev_radar import DEX_PROGRAM_IDS
from .models import CPIInvocation, SimulationResult, TokenBalanceDiff


@dataclass
class SwapHop:
    hop_index: int
    dex_program: str
    dex_name: str
    token_in_mint: str
    token_in_symbol: str
    amount_in: float
    token_out_mint: str
    token_out_symbol: str
    amount_out: float
    effective_rate: float
    cus_consumed: int

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class SwapRouteReport:
    is_swap: bool
    total_hops: int
    hops: List[SwapHop] = field(default_factory=list)
    input_token: Optional[str] = None
    input_amount: float = 0.0
    output_token: Optional[str] = None
    output_amount: float = 0.0
    is_cyclic_arbitrage: bool = False
    arbitrage_profit: float = 0.0
    dexes_involved: List[str] = field(default_factory=list)
    ascii_diagram: str = ""
    mermaid_flowchart: str = ""
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def render_route_ascii(hops: List[SwapHop]) -> str:
    """Renders a clean ASCII/Unicode pipeline diagram of swap hops."""
    if not hops:
        return "No swap hops detected."

    parts: List[str] = []
    first = hops[0]
    parts.append(f"[{first.token_in_symbol or first.token_in_mint[:6]}]")

    for hop in hops:
        dex_label = hop.dex_name
        rate_str = f" @ 1:{hop.effective_rate:.4f}" if hop.effective_rate > 0 else ""
        out_label = hop.token_out_symbol or hop.token_out_mint[:6]
        parts.append(f" ──({dex_label}{rate_str})──> [{out_label}]")

    return "".join(parts)


def render_route_mermaid(hops: List[SwapHop]) -> str:
    """Renders a Mermaid flowchart representing the swap sequence."""
    if not hops:
        return "flowchart LR\n    empty[No Swap Hops Detected]"

    lines = ["flowchart LR"]
    for i, hop in enumerate(hops):
        in_sym = hop.token_in_symbol or hop.token_in_mint[:6]
        out_sym = hop.token_out_symbol or hop.token_out_mint[:6]
        dex_name = hop.dex_name.replace('"', '\\"')

        node_in = f"node_{i}_in"
        node_out = f"node_{i}_out"
        rate_txt = f"<br/>1 : {hop.effective_rate:.4f}" if hop.effective_rate > 0 else ""

        lines.append(f'    {node_in}["{in_sym}"] -->|"{dex_name}{rate_txt}"| {node_out}["{out_sym}"]')

    return "\n".join(lines)


def analyze_swap_route(result: SimulationResult) -> SwapRouteReport:
    """
    Reconstructs the swap route path across DEX programs and token mints
    from CPI invocations, token balance deltas, and execution logs.
    """
    # 1. Collect DEX invocations
    dex_nodes: List[CPIInvocation] = []

    def scan_nodes(nodes: List[CPIInvocation]):
        for node in nodes:
            if node.program_id in DEX_PROGRAM_IDS:
                dex_nodes.append(node)
            elif node.instruction_name and any(
                k in node.instruction_name.lower() for k in ["swap", "buy", "sell", "route"]
            ):
                dex_nodes.append(node)
            if node.children:
                scan_nodes(node.children)

    scan_nodes(result.cpi_roots)

    # 2. Extract token balance deltas
    negative_diffs = [td for td in result.token_diffs if td.delta < 0]
    positive_diffs = [td for td in result.token_diffs if td.delta > 0]

    # If no token diffs, check if there's account lamports delta
    hops: List[SwapHop] = []
    dexes_involved: List[str] = []

    for idx, node in enumerate(dex_nodes):
        dex_name = KNOWN_PROGRAMS.get(node.program_id, node.program_name or node.program_id[:8])
        if dex_name not in dexes_involved:
            dexes_involved.append(dex_name)

        # Infer in/out token for this hop
        in_mint = "SOL"
        in_sym = "SOL"
        in_amt = 0.0

        out_mint = "TOKEN"
        out_sym = "TOKEN"
        out_amt = 0.0

        if idx < len(negative_diffs):
            td_in = negative_diffs[idx]
            in_mint = td_in.mint
            in_sym = td_in.symbol or td_in.mint[:6]
            in_amt = abs(td_in.delta)
        elif negative_diffs:
            td_in = negative_diffs[0]
            in_mint = td_in.mint
            in_sym = td_in.symbol or td_in.mint[:6]
            in_amt = abs(td_in.delta)

        if idx < len(positive_diffs):
            td_out = positive_diffs[idx]
            out_mint = td_out.mint
            out_sym = td_out.symbol or td_out.mint[:6]
            out_amt = td_out.delta
        elif positive_diffs:
            td_out = positive_diffs[-1]
            out_mint = td_out.mint
            out_sym = td_out.symbol or td_out.mint[:6]
            out_amt = td_out.delta

        rate = (out_amt / in_amt) if in_amt > 0 and out_amt > 0 else 0.0

        hops.append(
            SwapHop(
                hop_index=idx + 1,
                dex_program=node.program_id,
                dex_name=dex_name,
                token_in_mint=in_mint,
                token_in_symbol=in_sym,
                amount_in=in_amt,
                token_out_mint=out_mint,
                token_out_symbol=out_sym,
                amount_out=out_amt,
                effective_rate=round(rate, 6),
                cus_consumed=node.consumed_cus,
            )
        )

    # In case there were token deltas but no recognized DEX program in CPI roots
    if not hops and negative_diffs and positive_diffs:
        for idx in range(min(len(negative_diffs), len(positive_diffs))):
            td_in = negative_diffs[idx]
            td_out = positive_diffs[idx]
            rate = (td_out.delta / abs(td_in.delta)) if td_in.delta != 0 else 0.0
            dex_name = "Automated Market Maker"
            dexes_involved.append(dex_name)
            hops.append(
                SwapHop(
                    hop_index=idx + 1,
                    dex_program="DEX11111111111111111111111111111111",
                    dex_name=dex_name,
                    token_in_mint=td_in.mint,
                    token_in_symbol=td_in.symbol or td_in.mint[:6],
                    amount_in=abs(td_in.delta),
                    token_out_mint=td_out.mint,
                    token_out_symbol=td_out.symbol or td_out.mint[:6],
                    amount_out=td_out.delta,
                    effective_rate=round(rate, 6),
                    cus_consumed=result.total_compute_units,
                )
            )

    is_swap = len(hops) > 0
    input_token = hops[0].token_in_symbol if hops else None
    input_amount = hops[0].amount_in if hops else 0.0
    output_token = hops[-1].token_out_symbol if hops else None
    output_amount = hops[-1].amount_out if hops else 0.0

    is_cyclic_arbitrage = False
    arbitrage_profit = 0.0
    if is_swap and input_token and output_token and input_token == output_token:
        is_cyclic_arbitrage = True
        arbitrage_profit = round(output_amount - input_amount, 6)

    ascii_diag = render_route_ascii(hops)
    mermaid_flow = render_route_mermaid(hops)

    if not is_swap:
        summary = "No multi-hop or direct token swap route detected."
    elif is_cyclic_arbitrage:
        summary = (
            f"Cyclic Arbitrage Route detected across {len(hops)} hop(s) via {', '.join(dexes_involved)}. "
            f"Net PnL: {'+' if arbitrage_profit >= 0 else ''}{arbitrage_profit} {input_token}."
        )
    else:
        summary = (
            f"{len(hops)}-hop Swap Route from {input_amount} {input_token} to {output_amount} {output_token} "
            f"via {', '.join(dexes_involved)}."
        )

    return SwapRouteReport(
        is_swap=is_swap,
        total_hops=len(hops),
        hops=hops,
        input_token=input_token,
        input_amount=input_amount,
        output_token=output_token,
        output_amount=output_amount,
        is_cyclic_arbitrage=is_cyclic_arbitrage,
        arbitrage_profit=arbitrage_profit,
        dexes_involved=dexes_involved,
        ascii_diagram=ascii_diag,
        mermaid_flowchart=mermaid_flow,
        summary=summary,
    )

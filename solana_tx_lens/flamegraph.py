from __future__ import annotations

"""
solana_tx_lens.flamegraph: Hierarchical Compute Unit Flamegraph & Bottleneck Profiler.

Reconstructs multi-level Cross-Program Invocation (CPI) call stacks, calculates inclusive
and exclusive Compute Unit (CU) consumption, identifies runtime bottlenecks, and exports
standalone interactive dark-mode SVG flamegraphs and formatted ASCII call trees.
"""

from dataclasses import asdict, dataclass, field
import html
import re
from typing import Any

INVOKE_REGEX = re.compile(r"^Program\s+([1-9A-HJ-NP-Za-km-z]+)\s+invoke\s+\[(\d+)\]")
CONSUMED_REGEX = re.compile(r"^Program\s+([1-9A-HJ-NP-Za-km-z]+)\s+consumed\s+(\d+)\s+of\s+(\d+)\s+compute\s+units")
SUCCESS_REGEX = re.compile(r"^Program\s+([1-9A-HJ-NP-Za-km-z]+)\s+success")
FAIL_REGEX = re.compile(r"^Program\s+([1-9A-HJ-NP-Za-km-z]+)\s+failed:\s*(.*)")


@dataclass
class FlamegraphNode:
    program_id: str
    depth: int
    inclusive_cus: int = 0
    exclusive_cus: int = 0
    percent_of_total: float = 0.0
    status: str = "success"
    error: str | None = None
    children: list[FlamegraphNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "program_id": self.program_id,
            "depth": self.depth,
            "inclusive_cus": self.inclusive_cus,
            "exclusive_cus": self.exclusive_cus,
            "percent_of_total": round(self.percent_of_total, 2),
            "status": self.status,
            "error": self.error,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class CUHotspot:
    program_id: str
    depth: int
    exclusive_cus: int
    percent_of_total: float


@dataclass
class FlamegraphReport:
    total_cus_consumed: int
    max_depth: int
    root_nodes: list[FlamegraphNode]
    hotspots: list[CUHotspot]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cus_consumed": self.total_cus_consumed,
            "max_depth": self.max_depth,
            "root_nodes": [r.to_dict() for r in self.root_nodes],
            "hotspots": [asdict(h) for h in self.hotspots],
        }


def build_flamegraph_from_logs(logs: list[str]) -> FlamegraphReport:
    """Parses Solana execution logs into a hierarchical CU flamegraph tree."""
    stack: list[FlamegraphNode] = []
    root_nodes: list[FlamegraphNode] = []
    total_tx_cus = 0
    max_depth = 0

    for line in logs:
        line = line.strip()

        # Check invoke [depth]
        inv_match = INVOKE_REGEX.match(line)
        if inv_match:
            pid = inv_match.group(1)
            depth = int(inv_match.group(2))
            max_depth = max(max_depth, depth)
            node = FlamegraphNode(program_id=pid, depth=depth)

            if depth == 1:
                root_nodes.append(node)
                stack = [node]
            else:
                # Find parent at depth - 1
                while stack and stack[-1].depth >= depth:
                    stack.pop()
                if stack:
                    stack[-1].children.append(node)
                stack.append(node)
            continue

        # Check consumed CU
        c_match = CONSUMED_REGEX.match(line)
        if c_match:
            pid = c_match.group(1)
            consumed = int(c_match.group(2))
            # Find the active node matching pid
            for node in reversed(stack):
                if node.program_id == pid and node.inclusive_cus == 0:
                    node.inclusive_cus = consumed
                    break
            continue

        # Check success
        s_match = SUCCESS_REGEX.match(line)
        if s_match:
            pid = s_match.group(1)
            for node in reversed(stack):
                if node.program_id == pid:
                    node.status = "success"
                    break
            continue

        # Check fail
        f_match = FAIL_REGEX.match(line)
        if f_match:
            pid = f_match.group(1)
            err = f_match.group(2)
            for node in reversed(stack):
                if node.program_id == pid:
                    node.status = "failed"
                    node.error = err
                    break
            continue

    # Calculate total CUs and exclusive CUs
    total_tx_cus = sum(r.inclusive_cus for r in root_nodes)
    if total_tx_cus == 0:
        total_tx_cus = 1  # prevent div by zero

    all_nodes: list[FlamegraphNode] = []

    def compute_metrics(node: FlamegraphNode) -> None:
        all_nodes.append(node)
        child_inclusive_sum = sum(c.inclusive_cus for c in node.children)
        node.exclusive_cus = max(0, node.inclusive_cus - child_inclusive_sum)
        node.percent_of_total = (node.inclusive_cus / total_tx_cus) * 100.0
        for child in node.children:
            compute_metrics(child)

    for r in root_nodes:
        compute_metrics(r)

    # Rank hotspots by exclusive CU consumption
    sorted_hotspots = sorted(all_nodes, key=lambda n: n.exclusive_cus, reverse=True)
    hotspots = [
        CUHotspot(
            program_id=h.program_id,
            depth=h.depth,
            exclusive_cus=h.exclusive_cus,
            percent_of_total=(h.exclusive_cus / total_tx_cus) * 100.0,
        )
        for h in sorted_hotspots[:5]
        if h.exclusive_cus > 0
    ]

    return FlamegraphReport(
        total_cus_consumed=total_tx_cus,
        max_depth=max_depth,
        root_nodes=root_nodes,
        hotspots=hotspots,
    )


def render_ascii_flamegraph(report: FlamegraphReport) -> str:
    """Renders formatted ASCII flamegraph tree with horizontal progress bars."""
    lines: list[str] = [
        f"Execution Flamegraph (Total: {report.total_cus_consumed:,} CUs | Max Depth: {report.max_depth})",
        "=" * 78,
    ]

    def _render_node(node: FlamegraphNode, prefix: str = "", is_last: bool = True) -> None:
        connector = "└── " if is_last else "├── "
        bar_len = 16
        filled = int((node.percent_of_total / 100.0) * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)

        short_pid = node.program_id[:4] + "..." + node.program_id[-4:] if len(node.program_id) > 12 else node.program_id
        status_flag = " [FAIL]" if node.status == "failed" else ""
        lines.append(
            f"{prefix}{connector}[{bar}] {node.percent_of_total:5.1f}% | {node.inclusive_cus:>7,} CUs (excl: {node.exclusive_cus:>7,}) {short_pid}{status_flag}"
        )

        child_prefix = prefix + ("    " if is_last else "│   ")
        for i, child in enumerate(node.children):
            _render_node(child, child_prefix, i == len(node.children) - 1)

    for i, r in enumerate(report.root_nodes):
        _render_node(r, "", i == len(report.root_nodes) - 1)

    if report.hotspots:
        lines.append("-" * 78)
        lines.append("Top Execution Hotspots (Exclusive CUs):")
        for idx, h in enumerate(report.hotspots, 1):
            short_pid = h.program_id[:6] + "..." + h.program_id[-6:] if len(h.program_id) > 16 else h.program_id
            lines.append(
                f"  {idx}. {short_pid:<18} (Depth {h.depth}) : {h.exclusive_cus:,} CUs ({h.percent_of_total:.1f}% of total)"
            )

    return "\n".join(lines)


def render_svg_flamegraph(report: FlamegraphReport, width: int = 880) -> str:
    """
    Renders a standalone, responsive dark-mode SVG flamegraph.
    Stacked horizontal bars represent call frames with width proportional to CU consumption.
    """
    row_height = 36
    row_gap = 6
    padding = 24
    total_cus = max(1, report.total_cus_consumed)
    max_depth = max(1, report.max_depth)
    height = padding * 2 + (max_depth * (row_height + row_gap)) + 60

    svg_blocks: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="{height}" style="background:#0b0f19; font-family:-apple-system,BlinkMacSystemFont,monospace; border-radius:8px; border:1px solid #1e293b;">',
        f'<style>',
        f'  .bg {{ fill: #0b0f19; }}',
        f'  .frame {{ rx: 4px; ry: 4px; transition: opacity 0.2s; cursor: pointer; }}',
        f'  .frame:hover {{ opacity: 0.85; stroke: #38bdf8; stroke-width: 1.5; }}',
        f'  .label {{ font-size: 11px; fill: #f8fafc; font-weight: 600; text-anchor: middle; dominant-baseline: middle; pointer-events: none; }}',
        f'  .sublabel {{ font-size: 9px; fill: #94a3b8; text-anchor: middle; dominant-baseline: middle; pointer-events: none; }}',
        f'  .title {{ font-size: 14px; fill: #38bdf8; font-weight: 700; }}',
        f'  .meta {{ font-size: 11px; fill: #64748b; }}',
        f'</style>',
        f'<text x="{padding}" y="{padding + 8}" class="title">Solana Compute Unit Execution Flamegraph</text>',
        f'<text x="{width - padding}" y="{padding + 8}" text-anchor="end" class="meta">Total: {report.total_cus_consumed:,} CUs | Max Depth: {report.max_depth}</text>',
    ]

    # Colors for depths / intensity
    COLORS = ["#3b82f6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"]

    # Render frames recursively
    # Available horizontal width for bars
    chart_width = width - (padding * 2)

    def _render_frames(node: FlamegraphNode, x_start: float, parent_width: float) -> None:
        y = padding + 32 + (node.depth - 1) * (row_height + row_gap)
        node_width = max(18.0, (node.inclusive_cus / total_cus) * chart_width)
        color = COLORS[(node.depth - 1) % len(COLORS)]
        if node.status == "failed":
            color = "#dc2626"

        short_pid = node.program_id[:4] + ".." + node.program_id[-4:] if len(node.program_id) > 10 else node.program_id
        safe_pid = html.escape(node.program_id)

        svg_blocks.append(
            f'<rect x="{x_start:.1f}" y="{y}" width="{node_width:.1f}" height="{row_height}" fill="{color}" class="frame">'
            f'<title>{safe_pid}&#10;Depth: {node.depth}&#10;Inclusive: {node.inclusive_cus:,} CUs ({node.percent_of_total:.1f}%)&#10;Exclusive: {node.exclusive_cus:,} CUs&#10;Status: {node.status}</title>'
            f'</rect>'
        )

        if node_width > 60:
            svg_blocks.append(
                f'<text x="{x_start + node_width / 2:.1f}" y="{y + 13}" class="label">{short_pid}</text>'
                f'<text x="{x_start + node_width / 2:.1f}" y="{y + 26}" class="sublabel">{node.inclusive_cus:,} CUs</text>'
            )

        # Children layout
        child_x = x_start
        for child in node.children:
            child_w = (child.inclusive_cus / total_cus) * chart_width
            _render_frames(child, child_x, child_w)
            child_x += child_w

    curr_x = float(padding)
    for r in report.root_nodes:
        r_width = (r.inclusive_cus / total_cus) * chart_width
        _render_frames(r, curr_x, r_width)
        curr_x += r_width

    svg_blocks.append("</svg>")
    return "\n".join(svg_blocks)

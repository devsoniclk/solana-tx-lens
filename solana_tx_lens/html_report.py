from __future__ import annotations

import html
from typing import Optional
from .contention import ContentionReport
from .models import CPIInvocation, SimulationResult
from .optimizer import ComputeBudgetOptimization


def _render_cpi_html_node(node: CPIInvocation) -> str:
    status_cls = "node-failed" if node.failed else "node-success"
    status_icon = "❌" if node.failed else "⚡"
    prog_label = html.escape(node.program_name or node.program_id)
    ix_label = f" :: <code>{html.escape(node.instruction_name)}</code>" if node.instruction_name else ""
    cu_badge = f"<span class='badge cu'>{node.consumed_cus:,} CUs</span>" if node.consumed_cus else ""
    err_badge = f"<span class='badge err'>{html.escape(node.error_message)}</span>" if node.error_message else ""

    children_html = "".join(_render_cpi_html_node(child) for child in node.children)
    has_children = bool(node.children)

    return f"""
    <div class="cpi-node {status_cls}" style="margin-left: {node.depth * 16}px;">
        <details {"open" if node.depth <= 1 or node.failed else ""}>
            <summary>
                <span class="icon">{status_icon}</span>
                <span class="depth">D{node.depth}</span>
                <span class="prog-name">{prog_label}</span>{ix_label}
                {cu_badge}
                {err_badge}
            </summary>
            {"<div class='cpi-children'>" + children_html + "</div>" if has_children else ""}
        </details>
    </div>
    """


def render_html_report(
    result: SimulationResult,
    optimization: Optional[ComputeBudgetOptimization] = None,
    contention: Optional[ContentionReport] = None,
    title: str = "Solana Transaction Simulation Dossier",
) -> str:
    """
    Renders a standalone, dependency-free, dark-themed HTML diagnostic dossier.
    """
    opt = optimization or getattr(result, "optimization", None)
    cnt = contention or getattr(result, "contention", None)
    health = result.health

    status_badge = (
        '<span class="badge success-badge">SIMULATION PASSED</span>'
        if result.success
        else '<span class="badge fail-badge">SIMULATION FAILED</span>'
    )

    health_status = health.status if health else "UNKNOWN"
    health_badge = f'<span class="badge health-{health_status.lower()}">{health_status}</span>'

    # CPI Tree
    cpi_tree_html = "".join(_render_cpi_html_node(r) for r in result.cpi_roots) or "<p class='dim'>No CPI invocations recorded.</p>"

    # Account Diffs Table
    acc_rows = []
    for diff in result.account_diffs:
        delta_sol = diff.lamports_delta / 1_000_000_000
        delta_cls = "pos" if diff.lamports_delta > 0 else ("neg" if diff.lamports_delta < 0 else "neutral")
        sign = "+" if diff.lamports_delta > 0 else ""
        acc_rows.append(
            f"<tr>"
            f"<td><code>{html.escape(diff.pubkey)}</code></td>"
            f"<td>{diff.pre_lamports / 1e9:.6f} SOL</td>"
            f"<td>{diff.post_lamports / 1e9:.6f} SOL</td>"
            f"<td class='{delta_cls}'>{sign}{delta_sol:.6f} SOL</td>"
            f"<td><code>{html.escape(diff.post_owner)}</code></td>"
            f"</tr>"
        )
    acc_table = "".join(acc_rows) or "<tr><td colspan='5' class='dim'>No account state changes.</td></tr>"

    # Token Diffs Table
    tok_rows = []
    for td in result.token_diffs:
        delta_cls = "pos" if td.delta > 0 else ("neg" if td.delta < 0 else "neutral")
        sign = "+" if td.delta > 0 else ""
        sym = f" ({html.escape(td.symbol)})" if td.symbol else ""
        tok_rows.append(
            f"<tr>"
            f"<td><code>{html.escape(td.account)}</code></td>"
            f"<td><code>{html.escape(td.mint)}</code>{sym}</td>"
            f"<td><code>{html.escape(td.owner)}</code></td>"
            f"<td>{td.pre_amount:.4f}</td>"
            f"<td>{td.post_amount:.4f}</td>"
            f"<td class='{delta_cls}'>{sign}{td.delta:.4f}</td>"
            f"</tr>"
        )
    tok_table = "".join(tok_rows) or "<tr><td colspan='6' class='dim'>No SPL token transfers.</td></tr>"

    # Health Issues
    issue_rows = []
    if health and health.issues:
        for iss in health.issues:
            sev_cls = f"sev-{iss.severity.lower()}"
            issue_rows.append(
                f"<div class='issue-card {sev_cls}'>"
                f"<div class='issue-header'><span class='badge {sev_cls}'>{iss.severity}</span> <strong>{html.escape(iss.check)}</strong></div>"
                f"<div class='issue-msg'>{html.escape(iss.message)}</div>"
                f"<div class='issue-rec'><strong>Fix:</strong> {html.escape(iss.recommendation)}</div>"
                f"</div>"
            )
    health_section = "".join(issue_rows) or "<p class='dim'>All pre-flight safety & MEV guard checks passed cleanly.</p>"

    # Optimizer Section
    opt_html = ""
    if opt:
        fee_rows = []
        for tier, price in opt.priority_fee_micro_lamports.items():
            cost = opt.estimated_tx_fees_sol.get(tier, 0.0)
            fee_rows.append(
                f"<tr>"
                f"<td style='text-transform: capitalize;'><strong>{tier}</strong></td>"
                f"<td>{price:,} µ-lamports/CU</td>"
                f"<td>{cost:.6f} SOL</td>"
                f"</tr>"
            )
        opt_html = f"""
        <div class="card">
            <h3>⚡ Compute Budget & Priority Fee Optimization</h3>
            <p class="summary-text">{html.escape(opt.recommendation_summary)}</p>
            <div class="grid-stats">
                <div class="stat"><span class="label">Simulated</span><span class="val">{opt.simulated_cus:,} CUs</span></div>
                <div class="stat"><span class="label">Recommended Limit</span><span class="val highlight">{opt.recommended_limit:,} CUs</span></div>
                <div class="stat"><span class="label">Buffer</span><span class="val">+{int(opt.safety_buffer_pct*100)}%</span></div>
                <div class="stat"><span class="label">CU Allocation Savings</span><span class="val pos">{opt.cu_savings_pct}%</span></div>
            </div>
            <table>
                <thead><tr><th>Priority Tier</th><th>Micro-Lamports per CU</th><th>Estimated Total Fee (SOL)</th></tr></thead>
                <tbody>{''.join(fee_rows)}</tbody>
            </table>
        </div>
        """

    # Contention Section
    cnt_html = ""
    if cnt:
        cnt_badge_cls = "badge-green" if cnt.concurrency_verdict == "HIGHLY_PARALLELIZABLE" else ("badge-yellow" if cnt.concurrency_verdict == "MODERATE_CONTENTION" else "badge-red")
        acc_acc_rows = []
        for acc in cnt.accounts:
            rw_cls = "rw-write" if acc.is_writable else "rw-read"
            hot_badge = f"<span class='badge err'>HOTSPOT ({acc.hotspot_type})</span>" if acc.is_hotspot else "—"
            acc_acc_rows.append(
                f"<tr>"
                f"<td><code>{html.escape(acc.pubkey)}</code></td>"
                f"<td>{html.escape(acc.label or '—')}</td>"
                f"<td>{'✓' if acc.is_signer else '—'}</td>"
                f"<td><span class='badge {rw_cls}'>{'WRITABLE' if acc.is_writable else 'READ-ONLY'}</span></td>"
                f"<td>{hot_badge}</td>"
                f"</tr>"
            )
        cnt_warns = "".join(f"<li class='warn-item'>{html.escape(w)}</li>" for w in cnt.warnings)
        cnt_html = f"""
        <div class="card">
            <h3>🔒 Account Write-Lock Contention & Parallelism</h3>
            <div class="grid-stats">
                <div class="stat"><span class="label">Verdict</span><span class="val {cnt_badge_cls}">{cnt.concurrency_verdict}</span></div>
                <div class="stat"><span class="label">Parallelizability</span><span class="val highlight">{int(cnt.parallelizability_score * 100)}%</span></div>
                <div class="stat"><span class="label">Writable Accounts</span><span class="val">{cnt.writable_count} / {cnt.total_accounts}</span></div>
                <div class="stat"><span class="label">Locked Hotspots</span><span class="val {'neg' if cnt.hotspot_count > 0 else 'pos'}">{cnt.hotspot_count}</span></div>
            </div>
            {"<ul class='warn-list'>" + cnt_warns + "</ul>" if cnt.warnings else ""}
            <table>
                <thead><tr><th>Pubkey</th><th>Label / Protocol</th><th>Signer</th><th>Access Mode</th><th>Hotspot Status</th></tr></thead>
                <tbody>{''.join(acc_acc_rows)}</tbody>
            </table>
        </div>
        """

    # MEV Radar Section
    radar = getattr(result, "mev_radar", None)
    radar_html = ""
    if radar:
        radar_badge_cls = (
            "badge-green" if radar.risk_level == "SAFE"
            else ("badge-yellow" if radar.risk_level in ("LOW", "MEDIUM") else "badge-red")
        )
        vec_rows = []
        for vec in radar.attack_vectors:
            sev_badge = f"<span class='badge sev-{vec.severity.lower()}'>{vec.severity}</span>"
            vec_rows.append(
                f"<div class='issue-card sev-{vec.severity.lower()}'>"
                f"<div class='issue-header'>{sev_badge} <strong>{html.escape(vec.vector_type)}</strong></div>"
                f"<div class='issue-msg'>{html.escape(vec.description)}</div>"
                f"<div class='issue-rec'><strong>Impact:</strong> {html.escape(vec.impact)}<br/><strong>Fix:</strong> {html.escape(vec.remediation)}</div>"
                f"</div>"
            )
        vecs_html = "".join(vec_rows) or "<p class='dim'>No vulnerable attack vectors identified.</p>"
        mit_items = "".join(f"<li>✓ {html.escape(m)}</li>" for m in radar.mitigations)
        radar_html = f"""
        <div class="card">
            <h3>🛡️ MEV Vulnerability Radar & Sandwich Protection</h3>
            <div class="grid-stats">
                <div class="stat"><span class="label">Risk Level</span><span class="val {radar_badge_cls}">{radar.risk_level}</span></div>
                <div class="stat"><span class="label">Sandwich Vulnerable</span><span class="val {'neg' if radar.is_sandwich_vulnerable else 'pos'}">{'YES' if radar.is_sandwich_vulnerable else 'NO'}</span></div>
                <div class="stat"><span class="label">DEX Swap</span><span class="val">{'YES' if radar.is_dex_swap else 'NO'}</span></div>
                <div class="stat"><span class="label">Max Safe Slippage</span><span class="val highlight">{radar.max_recommended_slippage_bps} bps (0.50%)</span></div>
            </div>
            <p class="summary-text">{html.escape(radar.summary)}</p>
            <div style="margin-top: 12px;">{vecs_html}</div>
            {"<ul class='warn-list' style='margin-top: 12px; color: var(--green);'>" + mit_items + "</ul>" if radar.mitigations else ""}
        </div>
        """

    # Multi-DEX Swap Route Section
    route = getattr(result, "route", None)
    route_html = ""
    if route and route.is_swap:
        hop_rows = []
        for hop in route.hops:
            rate_str = f"1 : {hop.effective_rate:.4f}" if hop.effective_rate > 0 else "—"
            hop_rows.append(
                f"<tr>"
                f"<td><strong>Hop {hop.hop_index}</strong></td>"
                f"<td>{html.escape(hop.dex_name)}</td>"
                f"<td><code>{hop.amount_in:,.4f} {html.escape(hop.token_in_symbol)}</code></td>"
                f"<td><code>{hop.amount_out:,.4f} {html.escape(hop.token_out_symbol)}</code></td>"
                f"<td>{rate_str}</td>"
                f"<td>{hop.cus_consumed:,} CUs</td>"
                f"</tr>"
            )
        arb_badge = "<span class='badge' style='background: #238636; color: #fff; margin-left: 8px;'>CYCLIC ARBITRAGE</span>" if route.is_cyclic_arbitrage else ""
        route_html = f"""
        <div class="card">
            <h3>🔄 Multi-DEX Swap Route & Flow {arb_badge}</h3>
            <p class="summary-text">{html.escape(route.summary)}</p>
            <div style="background: #0d1117; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 13px; color: var(--accent); margin-bottom: 16px; overflow-x: auto;">
                {html.escape(route.ascii_diagram)}
            </div>
            <table>
                <thead><tr><th>Hop</th><th>DEX / AMM</th><th>Token In</th><th>Token Out</th><th>Rate</th><th>Compute Units</th></tr></thead>
                <tbody>{''.join(hop_rows)}</tbody>
            </table>
        </div>
        """

    # Token-2022 Extensions Section
    t22 = getattr(result, "token_extensions", None)
    t22_html = ""
    if t22:
        ext_items = "".join(f"<li><strong>[{html.escape(e.risk_level)}] {html.escape(e.extension_type)}:</strong> {html.escape(e.description)}</li>" for e in getattr(t22, "detected_extensions", []))
        t22_badge_cls = "badge-green" if t22.risk_rating == "LOW" else ("badge-yellow" if t22.risk_rating == "MEDIUM" else "badge-red")
        t22_html = f"""
        <div class="card">
            <h3>🔬 Token-2022 Extensions & Transfer Hook Audit</h3>
            <div class="grid-stats">
                <div class="stat"><span class="label">Mint</span><span class="val highlight">{html.escape(t22.mint[:8])}...</span></div>
                <div class="stat"><span class="label">Token-2022</span><span class="val">{'YES' if t22.is_token_2022 else 'NO'}</span></div>
                <div class="stat"><span class="label">Risk Rating</span><span class="val {t22_badge_cls}">{t22.risk_rating} ({t22.risk_score}/100)</span></div>
                <div class="stat"><span class="label">Fee Deducted</span><span class="val">{t22.fee_deducted:,.4f}</span></div>
            </div>
            {"<ul class='warn-list' style='margin-top: 12px;'>" + ext_items + "</ul>" if ext_items else "<p class='dim'>No extensions active.</p>"}
        </div>
        """

    # Access List & Concurrency Section
    al = getattr(result, "access_list_report", None)
    al_html = ""
    if al:
        al_badge_cls = "badge-green" if al.concurrency_score >= 80 else ("badge-yellow" if al.concurrency_score >= 50 else "badge-red")
        al_html = f"""
        <div class="card">
            <h3>⚡ State Access List & Sealevel Parallelism</h3>
            <div class="grid-stats">
                <div class="stat"><span class="label">Concurrency Score</span><span class="val {al_badge_cls}">{al.concurrency_score}/100</span></div>
                <div class="stat"><span class="label">Write Locks</span><span class="val neg">{len(al.write_locks)}</span></div>
                <div class="stat"><span class="label">Read Locks</span><span class="val pos">{len(al.read_locks)}</span></div>
                <div class="stat"><span class="label">MTU Utilization</span><span class="val highlight">{al.serialization.utilization_pct if al.serialization else 0}%</span></div>
            </div>
        </div>
        """

    # Policy Verification Section
    pv = getattr(result, "policy_report", None)
    pv_html = ""
    if pv:
        pv_badge_cls = "badge-green" if pv.passed else "badge-red"
        v_items = "".join(f"<li><strong>[{html.escape(v.severity)}] {html.escape(v.rule_id)}:</strong> {html.escape(v.message)}</li>" for v in getattr(pv, "violations", []))
        pv_html = f"""
        <div class="card">
            <h3>📋 Pre-Flight Safety Policy Verification</h3>
            <div class="grid-stats">
                <div class="stat"><span class="label">Policy Verdict</span><span class="val {pv_badge_cls}">{'PASSED' if pv.passed else 'FAILED'}</span></div>
                <div class="stat"><span class="label">Rules Evaluated</span><span class="val">{pv.total_rules_evaluated}</span></div>
                <div class="stat"><span class="label">Violations</span><span class="val {'neg' if pv.violations_count > 0 else 'pos'}">{pv.violations_count}</span></div>
            </div>
            <p class="summary-text">{html.escape(pv.summary)}</p>
            {"<ul class='warn-list' style='margin-top: 12px; color: var(--red);'>" + v_items + "</ul>" if v_items else ""}
        </div>
        """

    raw_logs_html = html.escape("\n".join(result.raw_logs)) or "No logs available."
    mermaid_seq = html.escape(result.to_mermaid(diagram_type="sequence"))
    mermaid_flow = html.escape(result.to_mermaid(diagram_type="flowchart"))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
    --bg: #0d1117;
    --card-bg: #161b22;
    --border: #30363d;
    --text: #c9d1d9;
    --text-dim: #8b949e;
    --heading: #f0f6fc;
    --accent: #58a6ff;
    --green: #3fb950;
    --red: #f85149;
    --yellow: #d29922;
    --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--text); font-family: var(--font); line-height: 1.5; padding: 24px; max-width: 1200px; margin: 0 auto; }}
h1, h2, h3 {{ color: var(--heading); margin-bottom: 12px; }}
h1 {{ display: flex; align-items: center; gap: 12px; font-size: 24px; border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 24px; }}
.badge {{ padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; display: inline-block; }}
.success-badge {{ background: #238636; color: #fff; }}
.fail-badge {{ background: #da3633; color: #fff; }}
.health-healthy {{ background: #238636; color: #fff; }}
.health-warning {{ background: #9e6a03; color: #fff; }}
.health-critical_failure {{ background: #da3633; color: #fff; }}
.badge-green {{ color: var(--green); }}
.badge-yellow {{ color: var(--yellow); }}
.badge-red {{ color: var(--red); }}
.cu {{ background: #1f6feb; color: #fff; }}
.err {{ background: #da3633; color: #fff; }}
.rw-write {{ background: #b62324; color: #fff; }}
.rw-read {{ background: #21262d; color: var(--text-dim); border: 1px solid var(--border); }}
.card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 24px; }}
.grid-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 16px; }}
.stat {{ background: #0d1117; border: 1px solid var(--border); border-radius: 6px; padding: 12px; }}
.stat .label {{ display: block; font-size: 12px; color: var(--text-dim); text-transform: uppercase; margin-bottom: 4px; }}
.stat .val {{ font-size: 18px; font-weight: 700; color: var(--heading); }}
.stat .highlight {{ color: var(--accent); }}
.stat .pos {{ color: var(--green); }}
.stat .neg {{ color: var(--red); }}
table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }}
th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
th {{ color: var(--text-dim); font-weight: 600; text-transform: uppercase; font-size: 11px; }}
code {{ font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; background: rgba(110,118,129,0.2); padding: 2px 4px; border-radius: 4px; font-size: 12px; }}
.pos {{ color: var(--green); font-weight: 600; }}
.neg {{ color: var(--red); font-weight: 600; }}
.dim {{ color: var(--text-dim); }}
.cpi-node {{ border-left: 2px solid var(--border); margin: 6px 0; padding-left: 10px; font-size: 13px; }}
.cpi-node summary {{ cursor: pointer; list-style: none; display: flex; align-items: center; gap: 8px; padding: 4px 0; }}
.cpi-node.node-failed {{ border-left-color: var(--red); }}
.cpi-node .icon {{ font-size: 14px; }}
.cpi-node .depth {{ font-weight: 700; color: var(--text-dim); font-size: 11px; }}
.cpi-node .prog-name {{ font-weight: 600; color: var(--heading); }}
.issue-card {{ border-left: 4px solid; padding: 10px 14px; margin-bottom: 10px; background: #0d1117; border-radius: 4px; }}
.issue-card.sev-critical {{ border-left-color: var(--red); }}
.issue-card.sev-warning {{ border-left-color: var(--yellow); }}
.issue-card.sev-info {{ border-left-color: var(--accent); }}
.issue-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }}
.issue-msg {{ font-size: 13px; margin-bottom: 4px; }}
.issue-rec {{ font-size: 12px; color: var(--text-dim); }}
.warn-list {{ list-style-type: none; margin: 12px 0; }}
.warn-item {{ background: rgba(210, 153, 34, 0.15); border: 1px solid var(--yellow); color: #f0883e; padding: 8px 12px; border-radius: 6px; margin-bottom: 8px; font-size: 13px; }}
pre {{ background: #0d1117; border: 1px solid var(--border); padding: 12px; border-radius: 6px; overflow-x: auto; font-family: ui-monospace, monospace; font-size: 12px; color: #e6edf3; }}
</style>
</head>
<body>

<h1>
    <span>🔍 {html.escape(title)}</span>
    {status_badge}
    {health_badge}
</h1>

<div class="card">
    <div class="grid-stats">
        <div class="stat"><span class="label">Total Compute Units</span><span class="val">{result.total_compute_units:,} / {result.max_compute_units:,}</span></div>
        <div class="stat"><span class="label">CU Utilization</span><span class="val {'neg' if (health and health.cu_utilization_pct > 85) else 'pos'}">{health.cu_utilization_pct if health else 0.0}%</span></div>
        <div class="stat"><span class="label">Account Mutations</span><span class="val">{len(result.account_diffs)}</span></div>
        <div class="stat"><span class="label">Token Transfers</span><span class="val">{len(result.token_diffs)}</span></div>
    </div>
</div>

{opt_html}

{cnt_html}

{radar_html}

{route_html}

{t22_html}

{al_html}

{pv_html}

<div class="card">
    <h3>🛡️ Pre-Flight Safety & MEV Guard</h3>
    {health_section}
</div>

<div class="card">
    <h3>🌲 Cross-Program Invocation (CPI) Call Tree</h3>
    {cpi_tree_html}
</div>

<div class="card">
    <h3>💰 Native SOL & Account Diffs</h3>
    <table>
        <thead><tr><th>Account Pubkey</th><th>Pre-Lamports</th><th>Post-Lamports</th><th>Delta</th><th>Post Owner</th></tr></thead>
        <tbody>{acc_table}</tbody>
    </table>
</div>

<div class="card">
    <h3>🪙 SPL Token Balance Transfers</h3>
    <table>
        <thead><tr><th>Token Account</th><th>Mint</th><th>Owner</th><th>Pre Amount</th><th>Post Amount</th><th>Delta</th></tr></thead>
        <tbody>{tok_table}</tbody>
    </table>
</div>

<div class="card">
    <details>
        <summary style="cursor: pointer; font-weight: 600; color: var(--heading);">📊 Mermaid Sequence Diagram Source (Click to Expand)</summary>
        <pre>{mermaid_seq}</pre>
    </details>
</div>

<div class="card">
    <details>
        <summary style="cursor: pointer; font-weight: 600; color: var(--heading);">📜 Raw Simulation Logs (Click to Expand)</summary>
        <pre>{raw_logs_html}</pre>
    </details>
</div>

</body>
</html>
"""


def render_bundle_html_report(bundle: Any, title: str = "Solana Atomic Bundle Simulation Dossier") -> str:
    status_cls = "success" if bundle.success else "failure"
    status_text = "ATOMIC BUNDLE PASSED" if bundle.success else f"BUNDLE REVERTED (Tx #{bundle.reverted_at_index})"
    status_color = "var(--green)" if bundle.success else "var(--red)"

    tip = bundle.jito_tip
    tip_badge = ""
    if tip and tip.is_valid_jito_tip:
        tip_badge = f"<span class='badge' style='background: #238636; color: #fff;'>JITO TIP: {tip.tip_sol:.4f} SOL ({tip.tip_tier.upper()})</span>"
    else:
        tip_badge = "<span class='badge' style='background: #30363d; color: var(--text-dim);'>NO JITO TIP</span>"

    warnings_html = ""
    if bundle.bundle_contention_warnings:
        warn_items = "".join(f"<li>⚠️ {html.escape(w)}</li>" for w in bundle.bundle_contention_warnings)
        warnings_html = f"""
        <div class="card" style="border-left: 4px solid var(--yellow);">
            <h3 style="color: var(--yellow);">⚠️ Cross-Transaction Write-Lock Warnings</h3>
            <ul style="margin-left: 20px; color: var(--text);">{warn_items}</ul>
        </div>
        """

    tx_rows = []
    for idx, tx in enumerate(bundle.transactions):
        tx_status = "<span class='badge' style='background: #238636; color: #fff;'>SUCCESS</span>" if tx.success else "<span class='badge' style='background: #da3633; color: #fff;'>FAILED</span>"
        err_msg = html.escape(tx.error.description) if tx.error else "-"
        tx_rows.append(
            f"<tr><td>#{idx}</td><td>{tx_status}</td><td>{tx.total_compute_units:,}</td><td>{len(tx.cpi_roots)}</td><td>{len(tx.account_diffs)}</td><td>{err_msg}</td></tr>"
        )
    tx_table = "".join(tx_rows) or "<tr><td colspan='6' style='text-align: center; color: var(--text-dim);'>No transactions</td></tr>"

    acc_rows = []
    for diff in bundle.cumulative_account_diffs:
        delta_cls = "delta-pos" if diff.lamports_delta > 0 else ("delta-neg" if diff.lamports_delta < 0 else "")
        delta_str = f"{diff.lamports_delta:+,} lamports ({diff.lamports_delta / 1e9:+.4f} SOL)"
        acc_rows.append(
            f"<tr><td><code>{html.escape(diff.pubkey)}</code></td><td>{diff.pre_lamports:,}</td><td>{diff.post_lamports:,}</td><td class='{delta_cls}'>{delta_str}</td><td><code>{html.escape(diff.post_owner[:8])}...</code></td></tr>"
        )
    acc_table = "".join(acc_rows) or "<tr><td colspan='5' style='text-align: center; color: var(--text-dim);'>No cumulative account balance mutations</td></tr>"

    tok_rows = []
    for t_diff in bundle.cumulative_token_diffs:
        delta_cls = "delta-pos" if t_diff.delta > 0 else ("delta-neg" if t_diff.delta < 0 else "")
        sym = f" ({html.escape(t_diff.symbol)})" if t_diff.symbol else ""
        tok_rows.append(
            f"<tr><td><code>{html.escape(t_diff.account)}</code></td><td><code>{html.escape(t_diff.mint)}</code>{sym}</td><td><code>{html.escape(t_diff.owner)}</code></td><td>{t_diff.pre_amount:.4f}</td><td>{t_diff.post_amount:.4f}</td><td class='{delta_cls}'>{t_diff.delta:+.4f}</td></tr>"
        )
    tok_table = "".join(tok_rows) or "<tr><td colspan='6' style='text-align: center; color: var(--text-dim);'>No cumulative token transfers</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
    --bg: #0d1117;
    --card-bg: #161b22;
    --border: #30363d;
    --text: #c9d1d9;
    --text-dim: #8b949e;
    --heading: #f0f6fc;
    --accent: #58a6ff;
    --green: #3fb950;
    --red: #f85149;
    --yellow: #d29922;
    --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--text); font-family: var(--font); line-height: 1.5; padding: 24px; max-width: 1200px; margin: 0 auto; }}
h1, h2, h3 {{ color: var(--heading); margin-bottom: 12px; }}
h1 {{ display: flex; align-items: center; gap: 12px; font-size: 24px; border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 24px; }}
.card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
.badge {{ display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; text-transform: uppercase; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-top: 16px; }}
.stat {{ background: rgba(255,255,255,0.03); border: 1px solid var(--border); border-radius: 6px; padding: 12px; }}
.stat .label {{ font-size: 11px; text-transform: uppercase; color: var(--text-dim); display: block; margin-bottom: 4px; }}
.stat .val {{ font-size: 20px; font-weight: bold; color: var(--heading); }}
table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }}
th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); text-align: left; }}
th {{ background: rgba(255,255,255,0.04); color: var(--text-dim); font-size: 11px; text-transform: uppercase; }}
code {{ font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12px; color: var(--accent); }}
.delta-pos {{ color: var(--green); font-weight: 600; }}
.delta-neg {{ color: var(--red); font-weight: 600; }}
</style>
</head>
<body>

<h1>
    <span>⚡ {html.escape(title)}</span>
    <span class="badge" style="background: {status_color}; color: #fff;">{status_text}</span>
    {tip_badge}
</h1>

<div class="card">
    <h3>📦 Atomic Bundle Overview</h3>
    <p style="color: var(--text);">{html.escape(bundle.summary)}</p>
    <div class="stats-grid">
        <div class="stat"><span class="label">Transactions</span><span class="val">{bundle.transaction_count}</span></div>
        <div class="stat"><span class="label">Cumulative Compute Units</span><span class="val">{bundle.total_compute_units:,}</span></div>
        <div class="stat"><span class="label">Jito Tip Amount</span><span class="val">{tip.tip_sol:.4f} SOL</span></div>
        <div class="stat"><span class="label">Cumulative Mutated Accounts</span><span class="val">{len(bundle.cumulative_account_diffs)}</span></div>
    </div>
</div>

{warnings_html}

<div class="card">
    <h3>⏱️ Transaction Execution Timeline</h3>
    <table>
        <thead><tr><th>Tx #</th><th>Status</th><th>Compute Units</th><th>CPI Roots</th><th>Account Mutations</th><th>Error</th></tr></thead>
        <tbody>{tx_table}</tbody>
    </table>
</div>

<div class="card">
    <h3>💰 Net Cumulative SOL & Account Mutations</h3>
    <table>
        <thead><tr><th>Account Pubkey</th><th>Pre-Lamports</th><th>Post-Lamports</th><th>Net Delta</th><th>Owner</th></tr></thead>
        <tbody>{acc_table}</tbody>
    </table>
</div>

<div class="card">
    <h3>🪙 Net Cumulative SPL Token Balance Transfers</h3>
    <table>
        <thead><tr><th>Token Account</th><th>Mint</th><th>Owner</th><th>Pre Amount</th><th>Post Amount</th><th>Net Delta</th></tr></thead>
        <tbody>{tok_table}</tbody>
    </table>
</div>

</body>
</html>
"""

from __future__ import annotations

import argparse
import json
import sys
from .access_list import analyze_access_list
from .bundle import BundleSimulator
from .contention import audit_account_contention
from .error_decoder import decode_solana_error
from .events import decode_program_events_and_returns
from .fee_guide import generate_fee_guide
from .html_report import render_bundle_html_report, render_html_report
from .mcp_server import SolanaLensMCPServer
from .mev_radar import scan_mev_vulnerabilities
from .optimizer import optimize_compute_budget
from .policy import verify_simulation_policy
from .route_analyzer import analyze_swap_route
from .simulator import SolanaSimulator
from .snapshot import create_account_snapshot_delta
from .stress_tester import stress_test_simulation
from .token_extensions import inspect_token_extensions
from .visualizer import render_cpi_mermaid_flowchart, render_cpi_mermaid_sequence, render_simulation_report


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sol-lens",
        description="Headless Solana transaction simulation inspector, CPI visualizer, pre-flight MEV guard, fee optimizer, atomic bundle simulator, and MCP server.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # simulate command
    p_sim = subparsers.add_parser(
        "simulate",
        help="Simulate a base64 encoded transaction or analyze a JSON simulation / log file.",
    )
    p_sim.add_argument(
        "target",
        help="Base64 transaction string, or path to JSON simulation output / log file.",
    )
    p_sim.add_argument(
        "--rpc",
        default="https://api.mainnet-beta.solana.com",
        help="Solana RPC endpoint.",
    )
    p_sim.add_argument(
        "--json",
        action="store_true",
        help="Output full structured JSON diagnostic report.",
    )
    p_sim.add_argument(
        "--mermaid",
        action="store_true",
        help="Output GitHub-renderable Mermaid sequence diagram.",
    )
    p_sim.add_argument(
        "--flowchart",
        action="store_true",
        help="Output GitHub-renderable Mermaid flowchart diagram.",
    )
    p_sim.add_argument(
        "--html",
        metavar="FILE",
        default=None,
        help="Generate and save a standalone, dark-themed HTML diagnostic dossier.",
    )

    # bundle command
    p_bnd = subparsers.add_parser(
        "bundle",
        help="Simulate and analyze an atomic multi-transaction bundle (e.g. Jito MEV bundle).",
    )
    p_bnd.add_argument(
        "target",
        help="Path to JSON file containing array of transaction simulation objects in sequential execution order.",
    )
    p_bnd.add_argument(
        "--rpc",
        default="https://api.mainnet-beta.solana.com",
        help="Solana RPC endpoint.",
    )
    p_bnd.add_argument(
        "--json",
        action="store_true",
        help="Output full bundle simulation result as JSON.",
    )
    p_bnd.add_argument(
        "--html",
        metavar="FILE",
        default=None,
        help="Generate and save a standalone, dark-themed HTML diagnostic dossier for the bundle.",
    )

    # mcp command
    p_mcp = subparsers.add_parser(
        "mcp",
        help="Run the standard Model Context Protocol (MCP) JSON-RPC stdio server for AI agents.",
    )
    p_mcp.add_argument(
        "--rpc",
        default="https://api.mainnet-beta.solana.com",
        help="Solana RPC endpoint.",
    )

    # optimize command
    p_opt = subparsers.add_parser(
        "optimize",
        help="Compute optimal SetComputeUnitLimit and priority fee tiers.",
    )
    p_opt.add_argument(
        "target",
        help="Integer compute units consumed, or path to simulation JSON / log file.",
    )
    p_opt.add_argument(
        "--buffer",
        type=float,
        default=0.15,
        help="Safety buffer percentage (default: 0.15 for 15%).",
    )
    p_opt.add_argument(
        "--json",
        action="store_true",
        help="Output optimization recommendation as JSON.",
    )

    # contention command
    p_cnt = subparsers.add_parser(
        "contention",
        help="Audit account write-lock contention and parallel execution bottlenecks.",
    )
    p_cnt.add_argument(
        "target",
        help="Path to JSON file containing simulation or account keys list.",
    )
    p_cnt.add_argument(
        "--json",
        action="store_true",
        help="Output contention audit as JSON.",
    )

    # decode-error command
    p_dec = subparsers.add_parser(
        "decode-error",
        help="Decode a numeric or hex Solana/Anchor error code.",
    )
    p_dec.add_argument("code", help="Error code (e.g. 6001, 0x1771, Custom(6001)).")
    p_dec.add_argument("--program", default=None, help="Optional target program ID.")

    # mev-radar command
    p_mev = subparsers.add_parser(
        "mev-radar",
        help="Scan a transaction simulation for sandwich attacks, excessive slippage, and MEV exposure.",
    )
    p_mev.add_argument("target", help="Base64 transaction string, or path to JSON simulation / log file.")
    p_mev.add_argument("--slippage", type=int, default=None, help="Configured slippage tolerance in basis points (e.g. 50 = 0.50%).")
    p_mev.add_argument("--private", action="store_true", help="Mark as private broadcast (not public validator gossip).")
    p_mev.add_argument("--rpc", default="https://api.mainnet-beta.solana.com", help="Solana RPC endpoint.")
    p_mev.add_argument("--json", action="store_true", help="Output MEV report as JSON.")

    # route command
    p_rt = subparsers.add_parser(
        "route",
        help="Analyze multi-hop DEX swap routing, token price ratios, and cyclic arbitrage loops.",
    )
    p_rt.add_argument("target", help="Base64 transaction string, or path to JSON simulation / log file.")
    p_rt.add_argument("--rpc", default="https://api.mainnet-beta.solana.com", help="Solana RPC endpoint.")
    p_rt.add_argument("--mermaid", action="store_true", help="Output route as Mermaid flowchart.")
    p_rt.add_argument("--json", action="store_true", help="Output route report as JSON.")

    # fee-guide command
    p_fg = subparsers.add_parser(
        "fee-guide",
        help="Generate dynamic multi-tier priority fee and Jito MEV tip recommendations.",
    )
    p_fg.add_argument("--cus", type=int, default=200_000, help="Estimated compute units consumed (default: 200,000).")
    p_fg.add_argument("--type", default="dex_swap", choices=["transfer", "dex_swap", "arbitrage", "nft_mint", "generic"], help="Transaction archetype.")
    p_fg.add_argument("--bundle", action="store_true", help="Calculate fees for Jito MEV bundle.")
    p_fg.add_argument("--json", action="store_true", help="Output fee guide as JSON.")

    # decode-events command
    p_ev = subparsers.add_parser(
        "decode-events",
        help="Decode Anchor event logs (Program data:) and return data (Program return:) from simulation logs.",
    )
    p_ev.add_argument("target", help="Log file path or JSON simulation file.")
    p_ev.add_argument("--json", action="store_true", help="Output events as JSON.")

    # stress-test command
    p_st = subparsers.add_parser(
        "stress-test",
        help="Stress-test transaction resilience against slippage cliffs, CU truncation, and fee surges.",
    )
    p_st.add_argument("target", help="Base64 transaction or simulation JSON file.")
    p_st.add_argument("--rpc", default="https://api.mainnet-beta.solana.com", help="Solana RPC endpoint.")
    p_st.add_argument("--slippage", type=int, default=50, help="Target slippage tolerance in basis points (default: 50).")
    p_st.add_argument("--cu-limit", type=int, default=None, help="Configured CU limit to stress-test.")
    p_st.add_argument("--json", action="store_true", help="Output stress test report as JSON.")

    # shadow-diff command
    p_sd = subparsers.add_parser(
        "shadow-diff",
        help="Compute granular account snapshot byte deltas and verify rent-exemption.",
    )
    p_sd.add_argument("target", help="Simulation JSON file containing accounts.")
    p_sd.add_argument("--json", action="store_true", help="Output account snapshot deltas as JSON.")

    # token-extensions command
    p_te = subparsers.add_parser(
        "token-extensions",
        help="Audit Token-2022 extensions, transfer fees, transfer hooks, and permanent delegates.",
    )
    p_te.add_argument("target", help="Token mint pubkey or JSON file containing mint extensions.")
    p_te.add_argument("--program", default="TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb", help="Token program ID.")
    p_te.add_argument("--amount", type=float, default=0.0, help="Simulated transfer amount.")
    p_te.add_argument("--decimals", type=int, default=6, help="Token decimals (default: 6).")
    p_te.add_argument("--json", action="store_true", help="Output audit report as JSON.")

    # access-list command
    p_al = subparsers.add_parser(
        "access-list",
        help="Analyze transaction account read/write locks, Sealevel concurrency, and ALT compression.",
    )
    p_al.add_argument("target", help="JSON file containing account keys and lock configuration.")
    p_al.add_argument("--json", action="store_true", help="Output access list report as JSON.")

    # verify-policy command
    p_vp = subparsers.add_parser(
        "verify-policy",
        help="Verify declarative safety policy rules against transaction simulation.",
    )
    p_vp.add_argument("target", help="Base64 transaction or simulation JSON file.")
    p_vp.add_argument("--rules", required=True, help="Path to rules JSON file or inline JSON string.")
    p_vp.add_argument("--rpc", default="https://api.mainnet-beta.solana.com", help="Solana RPC endpoint.")
    p_vp.add_argument("--json", action="store_true", help="Output policy report as JSON.")

    args = parser.parse_args()

    if args.command == "mcp":
        server = SolanaLensMCPServer(rpc_url=args.rpc)
        server.run_stdio()

    elif args.command == "bundle":
        with open(args.target, "r") as f:
            data = json.load(f)

        txs = data if isinstance(data, list) else data.get("transactions", [])
        bsim = BundleSimulator(rpc_url=args.rpc)
        res = bsim.simulate_bundle(txs)

        if args.html:
            html_content = res.to_html(title="Solana Atomic Bundle Simulation Dossier")
            with open(args.html, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"Bundle diagnostic HTML dossier written to: {args.html}")
        elif args.json:
            print(res.to_json(indent=2))
        else:
            print("==================================================")
            print(" ATOMIC MULTI-TRANSACTION BUNDLE SIMULATION")
            print("==================================================")
            status_str = "PASSED (ATOMIC)" if res.success else f"REVERTED at Tx #{res.reverted_at_index}"
            print(f"Status:             {status_str}")
            print(f"Transactions:       {res.transaction_count}")
            print(f"Cumulative CUs:     {res.total_compute_units:,}")
            if res.jito_tip.is_valid_jito_tip:
                print(f"Jito Tip Detected:  {res.jito_tip.tip_sol:.4f} SOL ({res.jito_tip.tip_lamports:,} lamports) [{res.jito_tip.tip_tier.upper()}]")
                print(f"Tip Account:        {res.jito_tip.tip_account}")
            else:
                print("Jito Tip Detected:  None")

            if res.bundle_contention_warnings:
                print("\nCross-Tx Contention Warnings:")
                for w in res.bundle_contention_warnings:
                    print(f"  ⚠️ {w}")

            print("\nTransaction Execution Timeline:")
            for idx, tx in enumerate(res.transactions):
                tx_st = "SUCCESS" if tx.success else "FAILED"
                err = f" ({tx.error.description})" if tx.error else ""
                print(f"  [{idx}] {tx_st:<7} | {tx.total_compute_units:,} CUs | CPIs: {len(tx.cpi_roots)} | Accounts: {len(tx.account_diffs)}{err}")

            if res.cumulative_account_diffs:
                print("\nCumulative Net Account Diffs:")
                for diff in res.cumulative_account_diffs:
                    print(f"  - {diff.pubkey[:8]}...{diff.pubkey[-4:]}: {diff.lamports_delta:+,} lamports ({diff.lamports_delta / 1e9:+.4f} SOL)")

            if res.cumulative_token_diffs:
                print("\nCumulative Net Token Transfers:")
                for t_diff in res.cumulative_token_diffs:
                    sym = f" ({t_diff.symbol})" if t_diff.symbol else ""
                    print(f"  - {t_diff.mint[:8]}...{t_diff.mint[-4:]}{sym}: {t_diff.delta:+.4f}")
            print("==================================================")

    elif args.command == "decode-error":
        err_info = decode_solana_error(args.code, args.program)
        print(f"Error Type:   {err_info.error_type}")
        print(
            f"Error Code:   {err_info.code} (0x{err_info.code:x})"
            if err_info.code >= 0
            else "Error Code:   N/A"
        )
        print(f"Name:         {err_info.name}")
        print(f"Description:  {err_info.description}")

    elif args.command == "optimize":
        sim_cus = 0
        try:
            sim_cus = int(args.target)
        except ValueError:
            with open(args.target, "r") as f:
                content = f.read().strip()
                try:
                    data = json.loads(content)
                    sim_cus = data.get("unitsConsumed") or data.get("total_compute_units", 0)
                except json.JSONDecodeError:
                    for line in content.splitlines():
                        if "consumed" in line and "compute units" in line:
                            parts = line.split("consumed")[-1].split("of")[0].strip()
                            try:
                                sim_cus = int(parts)
                                break
                            except ValueError:
                                pass

        opt = optimize_compute_budget(sim_cus, safety_buffer_pct=args.buffer)
        if args.json:
            print(json.dumps(opt.to_dict(), indent=2))
        else:
            print("==================================================")
            print(" COMPUTE BUDGET & PRIORITY FEE OPTIMIZER")
            print("==================================================")
            print(f"Simulated CUs:      {opt.simulated_cus:,}")
            print(f"Recommended Limit:  {opt.recommended_limit:,} CUs (+{int(opt.safety_buffer_pct*100)}% buffer)")
            print(f"Baseline Limit:     {opt.default_limit:,} CUs")
            print(f"Savings:            {opt.cu_savings:,} CUs ({opt.cu_savings_pct}%)")
            print(f"\n{opt.recommendation_summary}\n")
            print("Estimated Transaction Fees by Priority Tier:")
            for tier, sol_fee in opt.estimated_tx_fees_sol.items():
                ul = opt.priority_fee_micro_lamports.get(tier, 0)
                print(f"  - {tier.capitalize():<7}: {sol_fee:.6f} SOL ({ul:,} µ-lamports/CU)")
            print("==================================================")

    elif args.command == "contention":
        with open(args.target, "r") as f:
            data = json.load(f)

        keys = data if isinstance(data, list) else (data.get("accountKeys") or data.get("accounts") or [])
        formatted_keys = []
        for k in keys:
            if isinstance(k, dict):
                formatted_keys.append(k)
            elif isinstance(k, str):
                formatted_keys.append({"pubkey": k, "signer": False, "writable": True})

        logs = data.get("logs", []) if isinstance(data, dict) else []
        cnt = audit_account_contention(formatted_keys, raw_logs=logs)
        if args.json:
            print(json.dumps(cnt.to_dict(), indent=2))
        else:
            print("==================================================")
            print(" ACCOUNT WRITE-LOCK CONTENTION & PARALLELISM AUDIT")
            print("==================================================")
            print(f"Concurrency Verdict:     {cnt.concurrency_verdict}")
            print(f"Parallelizability Score: {cnt.parallelizability_score:.2f} ({int(cnt.parallelizability_score*100)}%)")
            print(f"Accounts:                {cnt.writable_count} Writable / {cnt.readonly_count} Read-Only (Total: {cnt.total_accounts})")
            print(f"Hotspot Locks:           {cnt.hotspot_count}")
            if cnt.warnings:
                print("\nWarnings:")
                for w in cnt.warnings:
                    print(f"  ⚠️ {w}")
            print("==================================================")

    elif args.command == "mev-radar":
        sim_val = None
        try:
            with open(args.target, "r") as f:
                content = f.read().strip()
                try:
                    sim_val = json.loads(content)
                except json.JSONDecodeError:
                    sim_val = {"logs": content.splitlines(), "unitsConsumed": 0, "err": None}
        except (FileNotFoundError, OSError):
            pass

        sim = SolanaSimulator(rpc_url=args.rpc)
        if sim_val:
            res = sim.parse_raw_simulation(sim_val)
        else:
            res = sim.simulate_encoded_transaction(args.target)

        radar = scan_mev_vulnerabilities(res, slippage_tolerance_bps=args.slippage, is_public_mempool=not args.private)
        if args.json:
            print(json.dumps(radar.to_dict(), indent=2))
        else:
            print("==================================================")
            print(" PRE-FLIGHT MEV RADAR & SANDWICH RISK AUDIT")
            print("==================================================")
            print(f"Risk Rating:         {radar.risk_level}")
            print(f"Sandwich Exposure:   {'YES (Vulnerable)' if radar.is_sandwich_vulnerable else 'NO (Protected)'}")
            print(f"DEX Interaction:     {'Detected' if radar.is_dex_swap else 'None'}")
            if radar.detected_slippage_bps is not None:
                print(f"Slippage Configured: {radar.detected_slippage_bps} bps ({radar.detected_slippage_bps/100:.2f}%)")
            print(f"Max Recommended:     {radar.max_recommended_slippage_bps} bps ({radar.max_recommended_slippage_bps/100:.2f}%)")
            print(f"\nSummary:\n  {radar.summary}")
            if radar.attack_vectors:
                print("\nIdentified Attack Vectors:")
                for vec in radar.attack_vectors:
                    print(f"  ⚠️ [{vec.severity}] {vec.vector_type}: {vec.description}")
                    print(f"     Impact: {vec.impact}")
                    print(f"     Fix:    {vec.remediation}")
            if radar.mitigations:
                print("\nActionable Mitigations:")
                for m in radar.mitigations:
                    print(f"  ✓ {m}")
            print("==================================================")

    elif args.command == "route":
        sim_val = None
        try:
            with open(args.target, "r") as f:
                content = f.read().strip()
                try:
                    sim_val = json.loads(content)
                except json.JSONDecodeError:
                    sim_val = {"logs": content.splitlines(), "unitsConsumed": 0, "err": None}
        except (FileNotFoundError, OSError):
            pass

        sim = SolanaSimulator(rpc_url=args.rpc)
        if sim_val:
            res = sim.parse_raw_simulation(sim_val)
        else:
            res = sim.simulate_encoded_transaction(args.target)

        route_rep = analyze_swap_route(res)
        if args.json:
            print(json.dumps(route_rep.to_dict(), indent=2))
        elif args.mermaid:
            print(route_rep.mermaid_flowchart)
        else:
            print("==================================================")
            print(" MULTI-DEX SWAP ROUTE & FLOW GRAPH AUDIT")
            print("==================================================")
            print(f"Swap Detected:    {'Yes' if route_rep.is_swap else 'No'}")
            print(f"Total Hops:       {route_rep.total_hops}")
            print(f"DEXs Involved:    {', '.join(route_rep.dexes_involved) or 'None'}")
            if route_rep.is_cyclic_arbitrage:
                print(f"Cyclic Arbitrage: YES (PnL: {route_rep.arbitrage_profit:+} {route_rep.input_token})")
            print(f"\nRoute Flow Diagram:\n  {route_rep.ascii_diagram}")
            print(f"\nSummary:\n  {route_rep.summary}")
            if route_rep.hops:
                print("\nHop Execution Breakdown:")
                for hop in route_rep.hops:
                    rate_str = f" @ rate 1:{hop.effective_rate:.4f}" if hop.effective_rate > 0 else ""
                    print(f"  [{hop.hop_index}] {hop.dex_name}: {hop.amount_in:,.4f} {hop.token_in_symbol} -> {hop.amount_out:,.4f} {hop.token_out_symbol}{rate_str} ({hop.cus_consumed:,} CUs)")
            print("==================================================")

    elif args.command == "fee-guide":
        guide = generate_fee_guide(estimated_cus=args.cus, tx_type=args.type, is_bundle=args.bundle)
        if args.json:
            print(json.dumps(guide.to_dict(), indent=2))
        else:
            print("==================================================")
            print(" DYNAMIC PRIORITY FEE & JITO TIP ADVISORY")
            print("==================================================")
            print(f"Transaction Type:    {guide.tx_type.upper()}")
            print(f"Estimated CUs:       {guide.estimated_cus:,} CUs")
            print(f"Recommended Limit:   {guide.recommended_cu_limit:,} CUs")
            print(f"\nRecommendation:\n  {guide.recommendation}")
            print("\nPriority Fee Tiers (SetComputeUnitPrice):")
            print(f"  {'Tier':<8} | {'Percentile':<10} | {'µ-lamports/CU':<14} | {'Total Fee (SOL)'}")
            print("  " + "-" * 55)
            for pt in guide.priority_fee_tiers:
                print(f"  {pt.tier:<8} | {pt.percentile}th       | {pt.micro_lamports_per_cu:<14,d} | {pt.total_fee_sol:.6f} SOL")

            print("\nJito MEV Tip Tiers (Private Leader Submission):")
            print(f"  {'Tier':<18} | {'Tip (SOL)':<12} | {'Landing Prob':<12} | {'Tip Lamports'}")
            print("  " + "-" * 60)
            for jt in guide.jito_tip_tiers:
                print(f"  {jt.tier:<18} | {jt.tip_sol:.6f} SOL | {jt.target_block_landing_prob:<12} | {jt.tip_lamports:,}")

            print("\nSDK / CLI Implementation Snippet:")
            for line in guide.cli_instructions.splitlines():
                print(f"  {line}")
            print("==================================================")

    elif args.command == "decode-events":
        logs = []
        try:
            with open(args.target, "r") as f:
                c = f.read().strip()
                try:
                    data = json.loads(c)
                    logs = data.get("logs", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                except json.JSONDecodeError:
                    logs = c.splitlines()
        except Exception:
            logs = [args.target]

        rep = decode_program_events_and_returns(logs)
        if args.json:
            print(rep.to_json(indent=2))
        else:
            print("==================================================")
            print(" PROGRAM RETURN DATA & ANCHOR EVENT LOGS")
            print("==================================================")
            print(f"Total Anchor Events Decoded: {rep.total_events_count}")
            print(f"Has Program Return Data:     {rep.has_return_data}")
            if rep.return_data:
                rd = rep.return_data
                print(f"\nReturn Data:")
                print(f"  Program ID:  {rd.program_id}")
                print(f"  Type:        {rd.interpreted_type}")
                print(f"  Hex:         0x{rd.hex_data}")
                if rd.as_utf8:
                    print(f"  String:      \"{rd.as_utf8}\"")
                if rd.as_u64_le is not None:
                    print(f"  u64 (LE):    {rd.as_u64_le:,}")
                if rd.as_u128_le is not None:
                    print(f"  u128 (LE):   {rd.as_u128_le:,}")

            if rep.anchor_events:
                print(f"\nDecoded Anchor Events:")
                for idx, ev in enumerate(rep.anchor_events, 1):
                    disc_status = "[Catalog Match]" if ev.matched_catalog else "[Unknown Disc]"
                    print(f"  {idx}. {ev.protocol} :: {ev.event_name} {disc_status}")
                    print(f"     Discriminator: 0x{ev.discriminator_hex}")
                    print(f"     Payload Size:  {ev.payload_bytes_len} bytes")
                    if ev.fields:
                        print(f"     Fields:        {ev.fields}")
            else:
                print("\nNo Anchor (Program data:) events detected.")
            print("==================================================")

    elif args.command == "stress-test":
        sim_val = None
        try:
            with open(args.target, "r") as f:
                c = f.read().strip()
                try:
                    sim_val = json.loads(c)
                except json.JSONDecodeError:
                    sim_val = {"logs": c.splitlines(), "unitsConsumed": 0, "err": None}
        except Exception:
            pass

        sim = SolanaSimulator(rpc_url=args.rpc)
        res = sim.parse_raw_simulation(sim_val) if sim_val else sim.simulate_encoded_transaction(args.target)
        stress_rep = stress_test_simulation(res, configured_cu_limit=args.cu_limit, observed_slippage_bps=args.slippage)

        if args.json:
            print(stress_rep.to_json(indent=2))
        else:
            print("==================================================")
            print(" TRANSACTION EXECUTION RESILIENCE & STRESS TEST")
            print("==================================================")
            print(f"Robustness Score:    {stress_rep.robustness_score}/100 [{stress_rep.risk_tier}]")
            cu = stress_rep.cu_sensitivity
            if cu:
                print(f"Compute Units:       {cu.simulated_cus:,} consumed / {cu.configured_limit:,} limit (+{cu.buffer_percentage:.1f}% margin)")
                print(f"CU Evaluation:       {cu.evaluation}")
                print(f"CU Advisory:         {cu.recommendation}")

            print("\nSlippage Sensitivity Matrix:")
            print(f"  {'Tolerance':<10} | {'Status':<18} | {'Revert Prob':<12} | Note")
            print("  " + "-" * 65)
            for sm in stress_rep.slippage_matrix:
                print(f"  {sm.tested_slippage_bps:<3} bps     | {sm.status:<18} | {sm.revert_probability_pct:.1f}%        | {sm.explanation}")

            print("\nPriority Fee Volatility Impact:")
            for sc in stress_rep.fee_volatility_scenarios:
                print(f"  {sc.surge_tier:<35} | {sc.implied_fee_sol:.6f} SOL | Drop Risk: {sc.drop_risk_pct:.1f}%")

            if stress_rep.critical_vulnerabilities:
                print("\nCritical Vulnerabilities:")
                for v in stress_rep.critical_vulnerabilities:
                    print(f"  [!] {v}")

            print("\nRecommendations:")
            for r in stress_rep.actionable_recommendations:
                print(f"  - {r}")
            print("==================================================")

    elif args.command == "shadow-diff":
        with open(args.target, "r") as f:
            data = json.load(f)

        pre_accs = data.get("preAccounts", data.get("pre_accounts", []))
        post_accs = data.get("postAccounts", data.get("accounts", data.get("post_accounts", [])))
        keys = data.get("accountKeys", data.get("account_keys"))

        summary = create_account_snapshot_delta(pre_accs, post_accs, account_keys=keys)
        if args.json:
            print(summary.to_json(indent=2))
        else:
            print("==================================================")
            print(" ACCOUNT SHADOW SNAPSHOT & RENT EXEMPTION AUDIT")
            print("==================================================")
            print(f"Accounts Touched:    {summary.total_accounts_touched}")
            print(f"Accounts Created:    {summary.accounts_created}")
            print(f"Accounts Closed:     {summary.accounts_closed}")
            print(f"Net SOL Delta:       {summary.total_sol_delta:+.6f} SOL ({summary.total_lamports_delta:+,} lamports)")
            print(f"Net Data Delta:      {summary.total_bytes_delta:+,} bytes")

            if summary.rent_exempt_violations:
                print("\nRent-Exempt Violations:")
                for vi in summary.rent_exempt_violations:
                    print(f"  [X] {vi}")
            else:
                print("\nRent-Exempt Check:   ALL ACCOUNTS COMPLIANT")

            print("\nAccount Deltas:")
            for d in summary.account_deltas:
                status = f"Δ {d.sol_delta:+.6f} SOL, Δ {d.data_len_delta:+} B"
                if d.owner_changed:
                    status += f" (Owner -> {d.post_owner[:8]}...)"
                print(f"  {d.pubkey[:16]}...: {status}")
            print("==================================================")

    elif args.command == "token-extensions":
        mint = args.target
        ext_data = []
        logs = []
        try:
            with open(args.target, "r") as f:
                d = json.load(f)
                mint = d.get("mint", args.target)
                ext_data = d.get("extensions", d.get("account_data_extensions", []))
                logs = d.get("logs", [])
        except Exception:
            pass

        t22_rep = inspect_token_extensions(
            mint=mint,
            program_id=args.program,
            account_data_extensions=ext_data,
            simulation_logs=logs,
            transfer_amount=args.amount,
            decimals=args.decimals,
        )
        if args.json:
            print(json.dumps(t22_rep.to_dict(), indent=2))
        else:
            print("==================================================")
            print(" TOKEN-2022 EXTENSIONS & TRANSFER HOOK AUDIT")
            print("==================================================")
            print(f"Mint:             {t22_rep.mint}")
            print(f"Is Token-2022:    {'Yes' if t22_rep.is_token_2022 else 'No'}")
            print(f"Risk Rating:      {t22_rep.risk_rating} ({t22_rep.risk_score}/100)")
            if t22_rep.transfer_fee:
                tf = t22_rep.transfer_fee
                print(f"\nTransfer Fee Config:")
                print(f"  Basis Points:   {tf.fee_basis_points} bps ({tf.fee_basis_points/100:.2f}%)")
                print(f"  Max Fee Cap:    {tf.maximum_fee:,} raw units")
                if t22_rep.gross_transfer_amount > 0:
                    print(f"  Transfer Gross: {t22_rep.gross_transfer_amount:,.4f}")
                    print(f"  Fee Deducted:   {t22_rep.fee_deducted:,.4f}")
                    print(f"  Net Received:   {t22_rep.net_transfer_amount:,.4f}")

            if t22_rep.transfer_hook:
                th = t22_rep.transfer_hook
                print(f"\nTransfer Hook:")
                print(f"  Hook Program:   {th.hook_program_id}")
                print(f"  Invoked:        {'Yes' if th.invoked else 'No'}")
                print(f"  Status:         {'SUCCESS' if th.success else 'FAILED'}")

            if t22_rep.detected_extensions:
                print(f"\nDetected Extensions ({len(t22_rep.detected_extensions)}):")
                for ext in t22_rep.detected_extensions:
                    print(f"  [{ext.risk_level}] {ext.extension_type}: {ext.description}")
                    if ext.warning:
                        print(f"       Warning: {ext.warning}")

            print("\nRecommendations:")
            for rec in t22_rep.recommendations:
                print(f"  - {rec}")
            print("==================================================")

    elif args.command == "access-list":
        try:
            with open(args.target, "r") as f:
                d = json.load(f)
        except Exception:
            d = {"account_keys": [args.target]}

        keys = d.get("account_keys", d.get("accountKeys", []))
        w_idxs = d.get("writable_indices", d.get("writableIndices"))
        s_idxs = d.get("signer_indices", d.get("signerIndices"))

        al_rep = analyze_access_list(keys, writable_indices=w_idxs, signer_indices=s_idxs)
        if args.json:
            print(json.dumps(al_rep.to_dict(), indent=2))
        else:
            print("==================================================")
            print(" SEALEVEL STATE ACCESS LIST & CONCURRENCY AUDIT")
            print("==================================================")
            print(f"Total Accounts:      {al_rep.total_accounts}")
            print(f"Write Locks:         {len(al_rep.write_locks)}")
            print(f"Read Locks:          {len(al_rep.read_locks)}")
            print(f"Signers:             {len(al_rep.signers)}")
            print(f"Concurrency Score:   {al_rep.concurrency_score}/100")

            if al_rep.serialization:
                s = al_rep.serialization
                print(f"\nSerialization Stats:")
                print(f"  Estimated Size:    {s.estimated_serialized_bytes} / {s.mtu_limit_bytes} bytes ({s.utilization_pct}%)")
                print(f"  Within MTU Limit:  {'Yes' if s.within_mtu_limit else 'NO - EXCEEDS MTU'}")

            if al_rep.lut_recommendation:
                lut = al_rep.lut_recommendation
                print(f"\nAddress Lookup Table (ALT) Compression:")
                print(f"  Compressible Keys: {len(lut.candidate_pubkeys)}")
                print(f"  Estimated Savings: {lut.bytes_saved} bytes saved (ratio: {lut.compression_ratio:.1%})")

            if al_rep.lock_anti_patterns:
                print("\nLock Contention Anti-Patterns:")
                for ap in al_rep.lock_anti_patterns:
                    print(f"  [!] {ap}")

            print("\nActionable Improvements:")
            for imp in al_rep.actionable_improvements:
                print(f"  - {imp}")
            print("==================================================")

    elif args.command == "verify-policy":
        sim_val = None
        try:
            with open(args.target, "r") as f:
                content = f.read().strip()
                try:
                    sim_val = json.loads(content)
                except json.JSONDecodeError:
                    sim_val = {"logs": content.splitlines(), "unitsConsumed": 0, "err": None}
        except (FileNotFoundError, OSError):
            pass

        sim = SolanaSimulator(rpc_url=args.rpc)
        if sim_val:
            res = sim.parse_raw_simulation(sim_val)
        else:
            res = sim.simulate_encoded_transaction(args.target)

        # Parse rules
        try:
            with open(args.rules, "r") as f:
                rules_data = json.load(f)
        except Exception:
            rules_data = json.loads(args.rules)

        pol_rep = verify_simulation_policy(res, rules=rules_data)
        if args.json:
            print(json.dumps(pol_rep.to_dict(), indent=2))
        else:
            print("==================================================")
            print(" PRE-FLIGHT SAFETY POLICY & INVARIANT AUDIT")
            print("==================================================")
            print(f"Policy Status:       {'PASSED' if pol_rep.passed else 'FAILED'}")
            print(f"Rules Evaluated:     {pol_rep.total_rules_evaluated}")
            print(f"Violations Detected: {pol_rep.violations_count}")
            print(f"Summary:             {pol_rep.summary}")

            if pol_rep.violations:
                print("\nViolations List:")
                for v in pol_rep.violations:
                    print(f"  [{v.severity}] {v.rule_id} ({v.rule_type}):")
                    print(f"       Message:  {v.message}")
                    if v.actual_value is not None:
                        print(f"       Actual:   {v.actual_value}")
                    if v.expected_value is not None:
                        print(f"       Expected: {v.expected_value}")
            print("==================================================")

    elif args.command == "simulate":
        sim_val = None
        try:
            with open(args.target, "r") as f:
                content = f.read().strip()
                try:
                    sim_val = json.loads(content)
                except json.JSONDecodeError:
                    sim_val = {"logs": content.splitlines(), "unitsConsumed": 0, "err": None}
        except (FileNotFoundError, OSError):
            pass

        sim = SolanaSimulator(rpc_url=args.rpc)
        if sim_val:
            res = sim.parse_raw_simulation(sim_val)
        else:
            res = sim.simulate_encoded_transaction(args.target)

        if args.html:
            html_content = res.to_html(title="Solana Transaction Simulation Dossier")
            with open(args.html, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"Diagnostic HTML dossier written to: {args.html}")
        elif args.json:
            print(res.to_json(indent=2))
        elif args.mermaid:
            print(res.to_mermaid(diagram_type="sequence"))
        elif args.flowchart:
            print(res.to_mermaid(diagram_type="flowchart"))
        else:
            print(render_simulation_report(res))


if __name__ == "__main__":
    main()

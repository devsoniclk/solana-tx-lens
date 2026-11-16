from __future__ import annotations

import argparse
import json
import sys
from .bundle import BundleSimulator
from .contention import audit_account_contention
from .error_decoder import decode_solana_error
from .html_report import render_bundle_html_report, render_html_report
from .mcp_server import SolanaLensMCPServer
from .optimizer import optimize_compute_budget
from .simulator import SolanaSimulator
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

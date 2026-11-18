from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

from .access_list import analyze_access_list
from .bundle import BundleSimulator
from .compression import audit_compression_tree
from .contention import audit_account_contention
from .cpi_parser import parse_cpi_tree
from .error_decoder import decode_solana_error
from .events import decode_program_events_and_returns
from .fee_guide import generate_fee_guide
from .flamegraph import (
    build_flamegraph_from_logs,
    render_ascii_flamegraph,
    render_svg_flamegraph,
)
from .guard import assess_simulation_health
from .html_report import render_bundle_html_report, render_html_report
from .idl_decoder import AnchorIDLRegistry, get_default_idl_registry
from .mev_radar import scan_mev_vulnerabilities
from .optimizer import optimize_compute_budget
from .policy import verify_simulation_policy
from .route_analyzer import analyze_swap_route
from .simulator import SolanaSimulator
from .snapshot import create_account_snapshot_delta
from .stress_tester import stress_test_simulation
from .witness_bridge import attest_simulation
from .multisig import MultisigConsensusVerifier, MultisigVerificationError
from .priority_fee import DynamicFeeOptimizer
from .token_extensions import inspect_token_extensions
from .visualizer import render_cpi_mermaid_flowchart, render_cpi_mermaid_sequence
from .zero_copy import audit_zero_copy_layout, benchmark_zero_copy_cu


class SolanaLensMCPServer:
    """
    Standard Model Context Protocol (MCP) stdio server for solana-tx-lens.
    Provides headless simulation, CPI parsing, priority fee optimization,
    write-lock contention auditing, and Jito bundle verification to AI agents.
    """

    PROTOCOL_VERSION = "2024-11-05"

    def __init__(self, rpc_url: str = "https://api.mainnet-beta.solana.com"):
        self.rpc_url = rpc_url
        self.simulator = SolanaSimulator(rpc_url=rpc_url)
        self.bundle_simulator = BundleSimulator(rpc_url=rpc_url)

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "solana_simulate",
                "description": "Simulate a Solana transaction (base64 string or raw JSON log output) and return parsed CPI tree, account diffs, token deltas, and error decoding.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Base64 encoded transaction or serialized JSON string containing simulation logs and accounts.",
                        },
                        "rpc_url": {
                            "type": "string",
                            "description": "Optional Solana JSON-RPC URL.",
                        },
                    },
                    "required": ["target"],
                },
            },
            {
                "name": "solana_inspect_cpi",
                "description": "Parse Solana transaction execution logs into a recursive CPI call graph with Mermaid diagrams.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "logs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Array of raw log strings from Solana simulateTransaction.",
                        },
                    },
                    "required": ["logs"],
                },
            },
            {
                "name": "solana_optimize_cu",
                "description": "Calculate optimal SetComputeUnitLimit and estimate micro-lamport priority fees across min, low, medium, and high congestion tiers.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "simulated_cus": {
                            "type": "integer",
                            "description": "Compute units consumed in simulation.",
                        },
                        "safety_buffer_pct": {
                            "type": "number",
                            "description": "Safety buffer fraction (default: 0.15 for +15%).",
                            "default": 0.15,
                        },
                    },
                    "required": ["simulated_cus"],
                },
            },
            {
                "name": "solana_audit_contention",
                "description": "Audit account write-lock contention and parallel execution bottlenecks for a set of account keys.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "accounts": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "pubkey": {"type": "string"},
                                    "writable": {"type": "boolean"},
                                    "signer": {"type": "boolean"},
                                },
                                "required": ["pubkey", "writable"],
                            },
                            "description": "List of account metadata dicts.",
                        },
                    },
                    "required": ["accounts"],
                },
            },
            {
                "name": "solana_audit_guard",
                "description": "Evaluate pre-flight safety invariants: unauthorized SOL drain, excessive slippage, and signer authorization.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "simulation_json": {
                            "type": "string",
                            "description": "JSON serialized SimulationResult or raw simulation value.",
                        },
                    },
                    "required": ["simulation_json"],
                },
            },
            {
                "name": "solana_simulate_bundle",
                "description": "Simulate and validate an atomic multi-transaction bundle (e.g. Jito MEV bundle) with tip verification and cumulative state transitions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "bundle_json": {
                            "type": "string",
                            "description": "JSON array of transaction simulation objects in sequential execution order.",
                        },
                    },
                    "required": ["bundle_json"],
                },
            },
            {
                "name": "solana_generate_dossier",
                "description": "Render a standalone, dark-themed HTML diagnostic dossier for a transaction or bundle simulation.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "simulation_json": {
                            "type": "string",
                            "description": "JSON serialized SimulationResult or BundleSimulationResult.",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Path to write the HTML dossier (e.g. 'dossier.html').",
                        },
                    },
                    "required": ["simulation_json", "output_path"],
                },
            },
            {
                "name": "solana_mev_radar",
                "description": "Scan transaction simulation for sandwich attack vulnerabilities, excessive slippage exposure, and frontrunning risks.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "simulation_json": {
                            "type": "string",
                            "description": "JSON serialized SimulationResult or raw simulation object with logs.",
                        },
                        "slippage_tolerance_bps": {
                            "type": "integer",
                            "description": "Optional configured slippage tolerance in basis points (e.g. 50 = 0.50%).",
                        },
                        "is_public_mempool": {
                            "type": "boolean",
                            "description": "Whether the transaction will be broadcast via public mempool gossip (default: true).",
                            "default": True,
                        },
                    },
                    "required": ["simulation_json"],
                },
            },
            {
                "name": "solana_analyze_route",
                "description": "Reconstruct multi-hop token swap route, intermediate DEX pool hops, effective exchange rates, and cyclic arbitrage loops from simulation logs and token diffs.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "simulation_json": {
                            "type": "string",
                            "description": "JSON serialized SimulationResult or raw simulation object with logs.",
                        },
                    },
                    "required": ["simulation_json"],
                },
            },
            {
                "name": "solana_fee_guide",
                "description": "Generate dynamic multi-tier priority fee and Jito MEV tip recommendations tailored to transaction type, compute limit, and network congestion.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "estimated_cus": {
                            "type": "integer",
                            "description": "Estimated compute units consumed (default: 200,000).",
                            "default": 200000,
                        },
                        "tx_type": {
                            "type": "string",
                            "description": "Transaction archetype ('transfer', 'dex_swap', 'arbitrage', 'nft_mint', 'generic').",
                            "default": "dex_swap",
                        },
                        "is_bundle": {
                            "type": "boolean",
                            "description": "Whether transaction is submitted in an atomic Jito MEV bundle.",
                            "default": False,
                        },
                    },
                },
            },
            {
                "name": "solana_decode_events",
                "description": "Decode Anchor event logs (Program data: <base64>) and program return data (Program return: <program_id> <base64>) from transaction execution logs.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "logs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Raw log lines from simulateTransaction or getTransaction RPC.",
                        },
                    },
                    "required": ["logs"],
                },
            },
            {
                "name": "solana_stress_test",
                "description": "Stress-test transaction resilience under adverse market conditions: slippage cliff points, compute unit truncation jitter, priority fee surges, and price volatility.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Base64 transaction or serialized JSON simulation object.",
                        },
                        "configured_cu_limit": {
                            "type": "integer",
                            "description": "Optional configured compute unit limit to test margin against.",
                        },
                        "slippage_bps": {
                            "type": "integer",
                            "description": "Optional target slippage tolerance in basis points (default: 50).",
                            "default": 50,
                        },
                    },
                    "required": ["target"],
                },
            },
            {
                "name": "solana_shadow_diff",
                "description": "Compute granular byte-level account snapshot deltas and verify Solana rent-exempt reserves across simulation transitions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pre_accounts": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Pre-simulation account states (lamports, owner, data).",
                        },
                        "post_accounts": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Post-simulation account states (lamports, owner, data).",
                        },
                        "account_keys": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of account public keys in index order.",
                        },
                    },
                    "required": ["post_accounts"],
                },
            },
            {
                "name": "solana_inspect_token_extensions",
                "description": "Deeply inspect Solana Token-2022 extensions: compute transfer fees, detect transfer hooks and permanent delegates, and evaluate soulbound/frozen restrictions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "mint": {
                            "type": "string",
                            "description": "Token mint public key.",
                        },
                        "program_id": {
                            "type": "string",
                            "description": "Token program ID (default: TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb).",
                            "default": "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
                        },
                        "account_data_extensions": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Parsed extension structures from mint account data.",
                        },
                        "simulation_logs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional simulation logs to detect runtime transfer hook execution.",
                        },
                        "transfer_amount": {
                            "type": "number",
                            "description": "Optional transfer amount to calculate exact net receipt and deducted fee.",
                            "default": 0.0,
                        },
                        "decimals": {
                            "type": "integer",
                            "description": "Token decimals (default: 6).",
                            "default": 6,
                        },
                    },
                    "required": ["mint"],
                },
            },
            {
                "name": "solana_analyze_access_list",
                "description": "Analyze Solana transaction account access lists: partition read/write locks, detect validator concurrency anti-patterns, evaluate serialization byte budget against MTU, and suggest Address Lookup Table (ALT) compression.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_keys": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of account public keys in the transaction message.",
                        },
                        "writable_indices": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Indices of accounts marked writable.",
                        },
                        "signer_indices": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Indices of accounts that are signers.",
                        },
                    },
                    "required": ["account_keys"],
                },
            },
            {
                "name": "solana_verify_policy",
                "description": "Verify declarative pre-execution safety policy rules against a simulated transaction (enforce max SOL loss, min received tokens, forbidden programs, required signers, and compute bounds).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Base64 transaction or serialized JSON simulation result.",
                        },
                        "rules": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Array of policy rule definitions ({rule_id, rule_type, severity, params}).",
                        },
                    },
                    "required": ["target", "rules"],
                },
            },
            {
                "name": "solana_audit_zero_copy",
                "description": "Audit Solana account memory layout against Anchor zero_copy, bytemuck Pod/Zeroable, and #[repr(C)] memory alignment rules. Computes field offsets, padding holes, 8-byte alignment, and CU savings.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "struct_name": {"type": "string", "description": "Name of the account struct."},
                        "fields": {
                            "type": "array",
                            "items": {"type": "array", "items": {"type": "string"}},
                            "description": "List of [field_name, type_str] pairs (e.g. [['owner', 'Pubkey'], ['amount', 'u64']]).",
                        },
                        "has_discriminator": {
                            "type": "boolean",
                            "default": True,
                            "description": "Whether Anchor injects an 8-byte discriminator prefix.",
                        },
                    },
                    "required": ["struct_name", "fields"],
                },
            },
            {
                "name": "solana_benchmark_zero_copy",
                "description": "Benchmark Compute Unit (CU) and heap allocation differences between standard Borsh deserialization and Zero-Copy AccountLoader in-place access.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "total_size": {"type": "integer", "description": "Total account size in bytes."},
                        "num_fields": {"type": "integer", "description": "Number of struct fields."},
                        "num_dynamic_vectors": {"type": "integer", "default": 0, "description": "Number of dynamic Vec elements."},
                    },
                    "required": ["total_size", "num_fields"],
                },
            },
            {
                "name": "solana_decode_idl",
                "description": "Decode instruction data and account addresses against an Anchor IDL (or built-in popular IDLs such as Pump.fun).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "program_id": {"type": "string", "description": "Program base58 address."},
                        "data_hex": {"type": "string", "description": "Raw instruction data as hex string."},
                        "account_keys": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of account public keys in transaction.",
                        },
                        "idl_json": {
                            "type": "string",
                            "description": "Optional JSON string of the Anchor IDL specification.",
                        },
                    },
                    "required": ["program_id", "data_hex"],
                },
            },
            {
                "name": "solana_generate_flamegraph",
                "description": "Generate a hierarchical Compute Unit execution tree and flamegraph from Solana simulation logs.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "logs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Simulation log messages array.",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["json", "ascii"],
                            "default": "json",
                            "description": "Output format: structured JSON or formatted ASCII tree.",
                        },
                    },
                    "required": ["logs"],
                },
            },
            {
                "name": "solana_export_flamegraph_svg",
                "description": "Generate a standalone, responsive dark-mode SVG flamegraph representing instruction and CPI CU consumption.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "logs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Simulation log messages array.",
                        },
                        "width": {
                            "type": "integer",
                            "default": 880,
                            "description": "SVG width in points.",
                        },
                    },
                    "required": ["logs"],
                },
            },
            {
                "name": "solana_audit_compression",
                "description": "Audit SPL State Compression Concurrent Merkle Tree configuration (max_depth, max_buffer_size, canopy_depth), capacity, account size, rent, and transaction MTU safety.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "max_depth": {"type": "integer", "description": "Merkle tree depth (e.g. 14, 20, 26, 30)."},
                        "max_buffer_size": {"type": "integer", "description": "Max concurrent changelog buffer size (e.g. 64, 256, 1024, 2048)."},
                        "canopy_depth": {"type": "integer", "default": 0, "description": "Cached on-chain canopy levels (0 to max_depth)."},
                    },
                    "required": ["max_depth", "max_buffer_size"],
                },
            },
            {
                "name": "solana_attest_simulation",
                "description": "Attest Solana transaction simulation telemetry into an agent-witness deliberation step or receipt.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "simulation": {"type": "object", "description": "Simulation result dictionary."},
                        "agent_id": {"type": "string", "description": "Agent identifier proposing attestation.", "default": "solana-tx-lens"},
                    },
                    "required": ["simulation"],
                },
            },
            {
                "name": "solana_simulate_multisig_consensus",
                "description": "Verify multisig threshold signatures or BFT consensus certificates for a transaction before simulation.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "present_signers": {"type": "array", "items": {"type": "string"}, "description": "List of public keys that signed."},
                        "threshold": {"type": "integer", "description": "Required signature threshold.", "default": 2},
                        "total_members": {"type": "integer", "description": "Total multisig committee size.", "default": 3},
                        "slashed_members": {"type": "array", "items": {"type": "string"}, "description": "List of slashed/Byzantine keys."},
                        "certificate": {"type": "object", "description": "Optional BFT consensus certificate."},
                    },
                },
            },
            {
                "name": "solana_predict_priority_fee",
                "description": "Predict dynamic priority fees across percentiles (P50, P75, P90, P99) based on account write-lock contention.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "writable_accounts": {"type": "array", "items": {"type": "string"}, "description": "List of writable account pubkeys."},
                        "target_compute_units": {"type": "integer", "description": "Target compute units required.", "default": 200000},
                        "congestion_multiplier": {"type": "number", "description": "Cluster congestion factor multiplier.", "default": 1.0},
                    },
                    "required": ["writable_accounts"],
                },
            },
        ]

    def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if name == "solana_simulate":
                target = arguments["target"]
                sim_val = None
                try:
                    sim_val = json.loads(target)
                except (json.JSONDecodeError, TypeError):
                    pass

                sim = self.simulator
                rpc = arguments.get("rpc_url")
                if rpc and rpc != sim.rpc_url:
                    sim = SolanaSimulator(rpc_url=rpc)

                if sim_val and isinstance(sim_val, dict):
                    res = sim.parse_raw_simulation(sim_val)
                else:
                    res = sim.simulate_encoded_transaction(target)

                return {
                    "success": res.success,
                    "total_compute_units": res.total_compute_units,
                    "max_compute_units": res.max_compute_units,
                    "error": res.error.__dict__ if res.error else None,
                    "cpi_roots_count": len(res.cpi_roots),
                    "account_diffs_count": len(res.account_diffs),
                    "token_diffs_count": len(res.token_diffs),
                    "health_status": res.health.status if res.health else "UNKNOWN",
                    "optimization": res.optimization.to_dict() if res.optimization else None,
                    "contention": res.contention.to_dict() if res.contention else None,
                }

            elif name == "solana_inspect_cpi":
                logs = arguments.get("logs", [])
                cpi_roots = parse_cpi_tree(logs)
                seq_mermaid = render_cpi_mermaid_sequence(cpi_roots)
                flow_mermaid = render_cpi_mermaid_flowchart(cpi_roots)
                return {
                    "root_invocations": len(cpi_roots),
                    "tree": [dataclasses_to_dict(r) for r in cpi_roots],
                    "mermaid_sequence": seq_mermaid,
                    "mermaid_flowchart": flow_mermaid,
                }

            elif name == "solana_optimize_cu":
                cus = int(arguments["simulated_cus"])
                buf = float(arguments.get("safety_buffer_pct", 0.15))
                opt = optimize_compute_budget(cus, safety_buffer_pct=buf)
                return opt.to_dict()

            elif name == "solana_audit_contention":
                accounts = arguments.get("accounts", [])
                cnt = audit_account_contention(accounts)
                return cnt.to_dict()

            elif name == "solana_audit_guard":
                raw_json = arguments["simulation_json"]
                data = json.loads(raw_json)
                if "unitsConsumed" in data or "logs" in data:
                    res = self.simulator.parse_raw_simulation(data)
                    health = res.health
                else:
                    # Construct minimal check
                    health = assess_simulation_health(
                        data.get("unitsConsumed", data.get("total_compute_units", 0)),
                        data.get("account_diffs", []),
                        data.get("token_diffs", []),
                        data.get("logs", []),
                        data.get("error"),
                    )
                return {
                    "status": health.status if health else "UNKNOWN",
                    "cu_utilization_pct": health.cu_utilization_pct if health else 0.0,
                    "issues": [dataclasses_to_dict(i) for i in (health.issues if health else [])],
                    "has_critical_failure": health.has_critical_failure if health else False,
                }

            elif name == "solana_simulate_bundle":
                bundle_json = arguments["bundle_json"]
                txs = json.loads(bundle_json)
                if not isinstance(txs, list):
                    raise ValueError("bundle_json must be an array of transaction simulation objects.")
                res = self.bundle_simulator.simulate_bundle(txs)
                return res.to_dict()

            elif name == "solana_generate_dossier":
                sim_json = arguments["simulation_json"]
                out_path = arguments["output_path"]
                data = json.loads(sim_json)

                if "transaction_count" in data or "jito_tip" in data:
                    # Bundle simulation
                    txs = data.get("transactions", [])
                    bundle_res = self.bundle_simulator.simulate_bundle(txs)
                    html = render_bundle_html_report(bundle_res)
                else:
                    res = self.simulator.parse_raw_simulation(data)
                    html = render_html_report(res)

                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(html)

                return {
                    "written": True,
                    "output_path": out_path,
                    "html_size_bytes": len(html.encode("utf-8")),
                }

            elif name == "solana_mev_radar":
                sim_json = arguments["simulation_json"]
                slippage = arguments.get("slippage_tolerance_bps")
                public_mempool = arguments.get("is_public_mempool", True)
                data = json.loads(sim_json)

                if isinstance(data, dict) and ("unitsConsumed" in data or "logs" in data):
                    res = self.simulator.parse_raw_simulation(data)
                elif isinstance(data, dict) and "cpi_roots" in data:
                    res = self.simulator.parse_raw_simulation({"logs": data.get("raw_logs", []), "unitsConsumed": data.get("total_compute_units", 0)})
                else:
                    res = self.simulator.parse_raw_simulation(data if isinstance(data, dict) else {"logs": []})

                radar = scan_mev_vulnerabilities(res, slippage_tolerance_bps=slippage, is_public_mempool=public_mempool)
                return radar.to_dict()

            elif name == "solana_analyze_route":
                sim_json = arguments["simulation_json"]
                data = json.loads(sim_json)

                if isinstance(data, dict) and ("unitsConsumed" in data or "logs" in data):
                    res = self.simulator.parse_raw_simulation(data)
                else:
                    res = self.simulator.parse_raw_simulation(data if isinstance(data, dict) else {"logs": []})

                route = analyze_swap_route(res)
                return route.to_dict()

            elif name == "solana_fee_guide":
                cus = int(arguments.get("estimated_cus", 200_000))
                tx_type = str(arguments.get("tx_type", "dex_swap"))
                is_bundle = bool(arguments.get("is_bundle", False))

                guide = generate_fee_guide(estimated_cus=cus, tx_type=tx_type, is_bundle=is_bundle)
                return guide.to_dict()

            elif name == "solana_decode_events":
                logs = arguments.get("logs", [])
                events_rep = decode_program_events_and_returns(logs)
                return events_rep.to_dict()

            elif name == "solana_stress_test":
                target = arguments["target"]
                cu_lim = arguments.get("configured_cu_limit")
                slip = arguments.get("slippage_bps", 50)
                try:
                    data = json.loads(target)
                except Exception:
                    data = target

                if isinstance(data, dict) and ("unitsConsumed" in data or "logs" in data):
                    res = self.simulator.parse_raw_simulation(data)
                elif isinstance(data, str):
                    res = self.simulator.simulate_encoded_transaction(data)
                else:
                    res = self.simulator.parse_raw_simulation(data if isinstance(data, dict) else {"logs": []})

                stress_rep = stress_test_simulation(res, configured_cu_limit=cu_lim, observed_slippage_bps=slip)
                return stress_rep.to_dict()

            elif name == "solana_shadow_diff":
                pre_accs = arguments.get("pre_accounts", [])
                post_accs = arguments.get("post_accounts", [])
                acc_keys = arguments.get("account_keys")
                shadow_rep = create_account_snapshot_delta(pre_accs, post_accs, account_keys=acc_keys)
                return shadow_rep.to_dict()

            elif name == "solana_inspect_token_extensions":
                mint = arguments["mint"]
                prog = arguments.get("program_id", "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")
                ext_data = arguments.get("account_data_extensions", [])
                logs = arguments.get("simulation_logs")
                amt = float(arguments.get("transfer_amount", 0.0))
                decs = int(arguments.get("decimals", 6))
                t22_rep = inspect_token_extensions(
                    mint=mint,
                    program_id=prog,
                    account_data_extensions=ext_data,
                    simulation_logs=logs,
                    transfer_amount=amt,
                    decimals=decs,
                )
                return t22_rep.to_dict()

            elif name == "solana_analyze_access_list":
                keys = arguments["account_keys"]
                w_idxs = arguments.get("writable_indices")
                s_idxs = arguments.get("signer_indices")
                acc_rep = analyze_access_list(
                    account_keys=keys,
                    writable_indices=w_idxs,
                    signer_indices=s_idxs,
                )
                return acc_rep.to_dict()

            elif name == "solana_verify_policy":
                target = arguments["target"]
                rules = arguments["rules"]
                try:
                    data = json.loads(target)
                except Exception:
                    data = target

                if isinstance(data, dict) and ("unitsConsumed" in data or "logs" in data):
                    res = self.simulator.parse_raw_simulation(data)
                elif isinstance(data, str):
                    res = self.simulator.simulate_encoded_transaction(data)
                else:
                    res = self.simulator.parse_raw_simulation(data if isinstance(data, dict) else {"logs": []})

                pol_rep = verify_simulation_policy(res, rules=rules)
                return pol_rep.to_dict()

            elif name == "solana_audit_zero_copy":
                sname = arguments["struct_name"]
                fields_raw = arguments["fields"]
                fields = [(str(f[0]), str(f[1])) for f in fields_raw]
                disc = arguments.get("has_discriminator", True)
                rep = audit_zero_copy_layout(struct_name=sname, fields=fields, has_discriminator=disc)
                return rep.to_dict()

            elif name == "solana_benchmark_zero_copy":
                tsize = int(arguments["total_size"])
                nfields = int(arguments["num_fields"])
                ndyn = int(arguments.get("num_dynamic_vectors", 0))
                return benchmark_zero_copy_cu(total_size=tsize, num_fields=nfields, num_dynamic_vectors=ndyn)

            elif name == "solana_decode_idl":
                pid = arguments["program_id"]
                data_hex = arguments["data_hex"]
                account_keys = arguments.get("account_keys")
                idl_json = arguments.get("idl_json")
                registry = get_default_idl_registry()
                if idl_json:
                    idl_dict = json.loads(idl_json)
                    registry.register_idl(pid, idl_dict)
                raw_bytes = bytes.fromhex(data_hex.replace("0x", ""))
                decoded = registry.decode_instruction(pid, raw_bytes, account_keys=account_keys)
                if decoded:
                    return decoded.to_dict()
                return {"error": f"Failed to decode instruction for program {pid}"}

            elif name == "solana_generate_flamegraph":
                logs = arguments.get("logs", [])
                fmt = arguments.get("format", "json")
                rep = build_flamegraph_from_logs(logs)
                if fmt == "ascii":
                    return {"ascii": render_ascii_flamegraph(rep), "report": rep.to_dict()}
                return rep.to_dict()

            elif name == "solana_export_flamegraph_svg":
                logs = arguments.get("logs", [])
                width = int(arguments.get("width", 880))
                rep = build_flamegraph_from_logs(logs)
                svg = render_svg_flamegraph(rep, width=width)
                return {"svg": svg, "total_compute_units": rep.total_cus_consumed, "max_depth": rep.max_depth}

            elif name == "solana_audit_compression":
                mdepth = int(arguments["max_depth"])
                mbuffer = int(arguments["max_buffer_size"])
                cdepth = int(arguments.get("canopy_depth", 0))
                rep = audit_compression_tree(max_depth=mdepth, max_buffer_size=mbuffer, canopy_depth=cdepth)
                return rep.to_dict()

            elif name == "solana_attest_simulation":
                sim_data = arguments.get("simulation", {})
                agent_id = arguments.get("agent_id", "solana-tx-lens")
                return attest_simulation(sim_data, agent_id=agent_id)

            elif name == "solana_simulate_multisig_consensus":
                threshold = int(arguments.get("threshold", 2))
                total_members = int(arguments.get("total_members", 3))
                slashed = arguments.get("slashed_members", [])
                verifier = MultisigConsensusVerifier(threshold=threshold, total_members=total_members, slashed_members=slashed)
                if "certificate" in arguments and arguments["certificate"]:
                    return verifier.verify_bft_certificate(arguments["certificate"])
                signers = arguments.get("present_signers", [])
                return verifier.verify_signers(signers)

            elif name == "solana_predict_priority_fee":
                accounts = arguments.get("writable_accounts", [])
                cu = int(arguments.get("target_compute_units", 200000))
                factor = float(arguments.get("congestion_multiplier", 1.0))
                optimizer = DynamicFeeOptimizer()
                return optimizer.predict_priority_fee(accounts, target_compute_units=cu, congestion_multiplier=factor)

            else:
                return {"error": f"Unknown tool: {name}"}

        except Exception as e:
            return {"error": str(e)}

    def handle_request(self, req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        msg_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": self.PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "solana-tx-lens-mcp",
                        "version": "0.8.0",
                    },
                },
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": self.get_tool_definitions(),
                },
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            res = self.handle_tool_call(tool_name, tool_args)
            result_payload = dict(res) if isinstance(res, dict) else {}
            result_payload["content"] = [
                {
                    "type": "text",
                    "text": json.dumps(res, indent=2),
                }
            ]
            result_payload["isError"] = "error" in res if isinstance(res, dict) else False
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": result_payload,
            }

        elif method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

        elif method.startswith("notifications/"):
            return None

        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }

    def run_stdio(self) -> None:
        """Run the JSON-RPC stdio event loop."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError as e:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {str(e)}"},
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()
                continue

            resp = self.handle_request(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()


def dataclasses_to_dict(obj: Any) -> Any:
    import dataclasses

    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    elif isinstance(obj, list):
        return [dataclasses_to_dict(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: dataclasses_to_dict(v) for k, v in obj.items()}
    return obj

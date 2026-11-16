from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

from .bundle import BundleSimulator
from .contention import audit_account_contention
from .cpi_parser import parse_cpi_tree
from .error_decoder import decode_solana_error
from .fee_guide import generate_fee_guide
from .guard import assess_simulation_health
from .html_report import render_bundle_html_report, render_html_report
from .mev_radar import scan_mev_vulnerabilities
from .optimizer import optimize_compute_budget
from .route_analyzer import analyze_swap_route
from .simulator import SolanaSimulator
from .visualizer import render_cpi_mermaid_flowchart, render_cpi_mermaid_sequence


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
                        "version": "0.5.0",
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
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(res, indent=2),
                        }
                    ],
                    "isError": "error" in res,
                },
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

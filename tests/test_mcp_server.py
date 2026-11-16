from __future__ import annotations

import json
import os
import tempfile
from solana_tx_lens.mcp_server import SolanaLensMCPServer


def test_mcp_initialize():
    server = SolanaLensMCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {},
    }
    resp = server.handle_request(req)
    assert resp["id"] == 1
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert resp["result"]["serverInfo"]["name"] == "solana-tx-lens-mcp"
    assert resp["result"]["serverInfo"]["version"] == "0.4.0"


def test_mcp_tools_list():
    server = SolanaLensMCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    resp = server.handle_request(req)
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "solana_simulate" in tool_names
    assert "solana_inspect_cpi" in tool_names
    assert "solana_optimize_cu" in tool_names
    assert "solana_audit_contention" in tool_names
    assert "solana_audit_guard" in tool_names
    assert "solana_simulate_bundle" in tool_names
    assert "solana_generate_dossier" in tool_names


def test_mcp_call_optimize_cu():
    server = SolanaLensMCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "solana_optimize_cu",
            "arguments": {
                "simulated_cus": 80000,
                "safety_buffer_pct": 0.15,
            },
        },
    }
    resp = server.handle_request(req)
    assert resp["id"] == 3
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["simulated_cus"] == 80000
    assert content["recommended_limit"] == 92000
    assert content["cu_savings"] == 108000


def test_mcp_call_inspect_cpi():
    server = SolanaLensMCPServer()
    logs = [
        "Program 11111111111111111111111111111111 invoke [1]",
        "Program 11111111111111111111111111111111 success",
    ]
    req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "solana_inspect_cpi",
            "arguments": {"logs": logs},
        },
    }
    resp = server.handle_request(req)
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["root_invocations"] == 1
    assert "sequenceDiagram" in content["mermaid_sequence"]


def test_mcp_call_audit_contention():
    server = SolanaLensMCPServer()
    accounts = [
        {"pubkey": "Account1111111111111111111111111111111111111", "writable": False, "signer": False},
        {"pubkey": "Account2222222222222222222222222222222222222", "writable": True, "signer": True},
    ]
    req = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "solana_audit_contention",
            "arguments": {"accounts": accounts},
        },
    }
    resp = server.handle_request(req)
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["total_accounts"] == 2
    assert content["writable_count"] == 1
    assert content["readonly_count"] == 1


def test_mcp_call_simulate_bundle():
    server = SolanaLensMCPServer()
    bundle = [
        {
            "unitsConsumed": 18000,
            "logs": ["Program 11111111111111111111111111111111 invoke [1]", "Program 11111111111111111111111111111111 success"],
        }
    ]
    req = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "solana_simulate_bundle",
            "arguments": {"bundle_json": json.dumps(bundle)},
        },
    }
    resp = server.handle_request(req)
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["success"] is True
    assert content["transaction_count"] == 1
    assert content["total_compute_units"] == 18000


def test_mcp_call_generate_dossier():
    server = SolanaLensMCPServer()
    sim_data = {
        "unitsConsumed": 20000,
        "logs": ["Program 11111111111111111111111111111111 invoke [1]", "Program 11111111111111111111111111111111 success"],
    }
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        out_path = f.name

    try:
        req = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "solana_generate_dossier",
                "arguments": {
                    "simulation_json": json.dumps(sim_data),
                    "output_path": out_path,
                },
            },
        }
        resp = server.handle_request(req)
        content = json.loads(resp["result"]["content"][0]["text"])
        assert content["written"] is True
        assert os.path.exists(out_path)
        with open(out_path) as fp:
            html = fp.read()
            assert "<!DOCTYPE html>" in html
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)


def test_mcp_unknown_tool():
    server = SolanaLensMCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {"name": "non_existent_tool", "arguments": {}},
    }
    resp = server.handle_request(req)
    assert resp["result"]["isError"] is True

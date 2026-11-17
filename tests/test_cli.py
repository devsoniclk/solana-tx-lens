from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def test_cli_decode_error():
    repo_root = Path(__file__).parent.parent
    res = subprocess.run(
        [sys.executable, "-m", "solana_tx_lens.cli", "decode-error", "6001"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res.returncode == 0
    assert "SlippageExceeded" in res.stdout
    assert "Error Type:   DEX" in res.stdout


def test_cli_simulate_log_file():
    repo_root = Path(__file__).parent.parent
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        json.dump(
            {
                "unitsConsumed": 45000,
                "logs": [
                    "Program 11111111111111111111111111111111 invoke [1]",
                    "Program 11111111111111111111111111111111 consumed 150 of 200000 compute units",
                    "Program 11111111111111111111111111111111 success",
                ],
                "err": None,
            },
            tf,
        )
        tf_path = tf.name

    try:
        res = subprocess.run(
            [sys.executable, "-m", "solana_tx_lens.cli", "simulate", tf_path],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(repo_root)},
        )
        assert res.returncode == 0
        assert "SOLANA TRANSACTION SIMULATION DIAGNOSTIC REPORT" in res.stdout
        assert "SUCCESS" in res.stdout
        assert "45,000" in res.stdout
    finally:
        Path(tf_path).unlink(missing_ok=True)


def test_cli_simulate_mermaid_and_json():
    repo_root = Path(__file__).parent.parent
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        json.dump(
            {
                "unitsConsumed": 32000,
                "logs": [
                    "Program 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 invoke [1]",
                    "Program log: Instruction: swap_exact_in",
                    "Program 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 consumed 32000 of 200000 compute units",
                    "Program 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 success",
                ],
                "err": None,
            },
            tf,
        )
        tf_path = tf.name

    try:
        # Test Mermaid flag
        res_m = subprocess.run(
            [sys.executable, "-m", "solana_tx_lens.cli", "simulate", tf_path, "--mermaid"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(repo_root)},
        )
        assert res_m.returncode == 0
        assert "sequenceDiagram" in res_m.stdout
        assert "Raydium AMM v4" in res_m.stdout

        # Test JSON flag
        res_j = subprocess.run(
            [sys.executable, "-m", "solana_tx_lens.cli", "simulate", tf_path, "--json"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(repo_root)},
        )
        assert res_j.returncode == 0
        parsed = json.loads(res_j.stdout)
        assert parsed["success"] is True
        assert parsed["total_compute_units"] == 32000
        assert parsed["health"]["status"] == "HEALTHY"
    finally:
        Path(tf_path).unlink(missing_ok=True)


def test_cli_simulate_html_output():
    repo_root = Path(__file__).parent.parent
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        json.dump(
            {
                "unitsConsumed": 32000,
                "logs": [
                    "Program 11111111111111111111111111111111 invoke [1]",
                    "Program 11111111111111111111111111111111 success",
                ],
                "err": None,
            },
            tf,
        )
        tf_path = tf.name

    html_out = tempfile.mktemp(suffix=".html")
    try:
        res = subprocess.run(
            [sys.executable, "-m", "solana_tx_lens.cli", "simulate", tf_path, "--html", html_out],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(repo_root)},
        )
        assert res.returncode == 0
        assert Path(html_out).exists()
        content = Path(html_out).read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "Solana Transaction Simulation Dossier" in content
    finally:
        Path(tf_path).unlink(missing_ok=True)
        Path(html_out).unlink(missing_ok=True)


def test_cli_optimize_subcommand():
    repo_root = Path(__file__).parent.parent
    res = subprocess.run(
        [sys.executable, "-m", "solana_tx_lens.cli", "optimize", "50000", "--json"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["simulated_cus"] == 50000
    assert data["recommended_limit"] == 58000
    assert data["cu_savings_pct"] == 71.0


def test_cli_contention_subcommand():
    repo_root = Path(__file__).parent.parent
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        json.dump(
            [
                {"pubkey": "SysvarRent111111111111111111111111111111111", "signer": False, "writable": False},
                {"pubkey": "SenderWallet111111111111111111111111111111111", "signer": True, "writable": True},
            ],
            tf,
        )
        tf_path = tf.name

    try:
        res = subprocess.run(
            [sys.executable, "-m", "solana_tx_lens.cli", "contention", tf_path],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(repo_root)},
        )
        assert res.returncode == 0
        assert "ACCOUNT WRITE-LOCK CONTENTION & PARALLELISM AUDIT" in res.stdout
        assert "Concurrency Verdict" in res.stdout
    finally:
        Path(tf_path).unlink(missing_ok=True)


def test_cli_bundle_subcommand():
    repo_root = Path(__file__).parent.parent
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        json.dump(
            [
                {
                    "unitsConsumed": 25000,
                    "logs": ["Program 11111111111111111111111111111111 invoke [1]", "Program 11111111111111111111111111111111 success"],
                },
                {
                    "unitsConsumed": 15000,
                    "logs": ["Program 11111111111111111111111111111111 invoke [1]", "Program 11111111111111111111111111111111 success"],
                }
            ],
            tf,
        )
        tf_path = tf.name

    html_out = tempfile.mktemp(suffix=".html")
    try:
        # Test CLI text output
        res = subprocess.run(
            [sys.executable, "-m", "solana_tx_lens.cli", "bundle", tf_path],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(repo_root)},
        )
        assert res.returncode == 0
        assert "ATOMIC MULTI-TRANSACTION BUNDLE SIMULATION" in res.stdout
        assert "Transactions:       2" in res.stdout
        assert "40,000" in res.stdout

        # Test CLI JSON output
        res_j = subprocess.run(
            [sys.executable, "-m", "solana_tx_lens.cli", "bundle", tf_path, "--json"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(repo_root)},
        )
        assert res_j.returncode == 0
        data = json.loads(res_j.stdout)
        assert data["success"] is True
        assert data["transaction_count"] == 2
        assert data["total_compute_units"] == 40000

        # Test CLI HTML output
        res_h = subprocess.run(
            [sys.executable, "-m", "solana_tx_lens.cli", "bundle", tf_path, "--html", html_out],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(repo_root)},
        )
        assert res_h.returncode == 0
        assert Path(html_out).exists()
        content = Path(html_out).read_text(encoding="utf-8")
        assert "Solana Atomic Bundle Simulation Dossier" in content
    finally:
        Path(tf_path).unlink(missing_ok=True)
        Path(html_out).unlink(missing_ok=True)


def test_cli_mev_radar_subcommand(tmp_path):
    repo_root = Path(__file__).parent.parent
    sim_data = {
        "unitsConsumed": 85_000,
        "logs": [
            "Program 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 invoke [1]",
            "Program log: Instruction: SwapBaseIn",
            "Program 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 success",
        ],
    }
    tf = tmp_path / "sim_mev.json"
    tf.write_text(json.dumps(sim_data), encoding="utf-8")

    res = subprocess.run(
        [sys.executable, "-m", "solana_tx_lens.cli", "mev-radar", str(tf), "--slippage", "350"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res.returncode == 0
    assert "PRE-FLIGHT MEV RADAR" in res.stdout
    assert "CRITICAL" in res.stdout

    res_json = subprocess.run(
        [sys.executable, "-m", "solana_tx_lens.cli", "mev-radar", str(tf), "--json"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res_json.returncode == 0
    data = json.loads(res_json.stdout)
    assert "risk_level" in data
    assert data["is_dex_swap"] is True


def test_cli_route_subcommand(tmp_path):
    repo_root = Path(__file__).parent.parent
    sim_data = {
        "unitsConsumed": 95_000,
        "logs": [
            "Program whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc invoke [1]",
            "Program log: Instruction: Swap",
            "Program whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc success",
        ],
    }
    tf = tmp_path / "sim_route.json"
    tf.write_text(json.dumps(sim_data), encoding="utf-8")

    res = subprocess.run(
        [sys.executable, "-m", "solana_tx_lens.cli", "route", str(tf)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res.returncode == 0
    assert "MULTI-DEX SWAP ROUTE" in res.stdout
    assert "Orca Whirlpool" in res.stdout

    res_mermaid = subprocess.run(
        [sys.executable, "-m", "solana_tx_lens.cli", "route", str(tf), "--mermaid"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res_mermaid.returncode == 0
    assert "flowchart LR" in res_mermaid.stdout


def test_cli_fee_guide_subcommand():
    repo_root = Path(__file__).parent.parent
    res = subprocess.run(
        [sys.executable, "-m", "solana_tx_lens.cli", "fee-guide", "--cus", "180000", "--type", "dex_swap"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res.returncode == 0
    assert "DYNAMIC PRIORITY FEE & JITO TIP ADVISORY" in res.stdout
    assert "DEX_SWAP" in res.stdout
    assert "180,000 CUs" in res.stdout

    res_json = subprocess.run(
        [sys.executable, "-m", "solana_tx_lens.cli", "fee-guide", "--cus", "180000", "--json"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res_json.returncode == 0
    data = json.loads(res_json.stdout)
    assert data["tx_type"] == "dex_swap"
    assert len(data["priority_fee_tiers"]) == 6


def test_cli_decode_events_subcommand(tmp_path):
    repo_root = Path(__file__).parent.parent
    tf = tmp_path / "events.json"
    tf.write_text(
        json.dumps(
            {
                "logs": [
                    "Program 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 invoke [1]",
                    "Program return: 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 VGVzdA==",
                    "Program 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 success",
                ]
            }
        )
    )

    res = subprocess.run(
        [sys.executable, "-m", "solana_tx_lens.cli", "decode-events", str(tf)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res.returncode == 0
    assert "PROGRAM RETURN DATA & ANCHOR EVENT LOGS" in res.stdout
    assert "Test" in res.stdout

    res_json = subprocess.run(
        [sys.executable, "-m", "solana_tx_lens.cli", "decode-events", str(tf), "--json"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res_json.returncode == 0
    data = json.loads(res_json.stdout)
    assert data["has_return_data"] is True


def test_cli_stress_test_subcommand(tmp_path):
    repo_root = Path(__file__).parent.parent
    tf = tmp_path / "sim.json"
    tf.write_text(json.dumps({"unitsConsumed": 85000, "logs": []}))

    res = subprocess.run(
        [sys.executable, "-m", "solana_tx_lens.cli", "stress-test", str(tf), "--cu-limit", "100000", "--slippage", "50"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res.returncode == 0
    assert "TRANSACTION EXECUTION RESILIENCE & STRESS TEST" in res.stdout
    assert "Robustness Score" in res.stdout


def test_cli_shadow_diff_subcommand(tmp_path):
    repo_root = Path(__file__).parent.parent
    tf = tmp_path / "accounts.json"
    tf.write_text(
        json.dumps(
            {
                "preAccounts": [{"pubkey": "Pk1", "lamports": 5000}],
                "postAccounts": [{"pubkey": "Pk1", "lamports": 12000}],
            }
        )
    )

    res = subprocess.run(
        [sys.executable, "-m", "solana_tx_lens.cli", "shadow-diff", str(tf)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res.returncode == 0
    assert "ACCOUNT SHADOW SNAPSHOT & RENT EXEMPTION AUDIT" in res.stdout
    assert "Accounts Touched:    1" in res.stdout


def test_cli_token_extensions_subcommand(tmp_path):
    repo_root = Path(__file__).parent.parent
    tf = tmp_path / "mint_ext.json"
    tf.write_text(
        json.dumps(
            {
                "mint": "Token2022Mint11111111111111111111111111111",
                "extensions": [
                    {"type": "TransferFeeConfig", "fee_basis_points": 150, "maximum_fee": 10000000}
                ],
            }
        )
    )

    res = subprocess.run(
        [sys.executable, "-m", "solana_tx_lens.cli", "token-extensions", str(tf), "--amount", "100.0"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res.returncode == 0
    assert "TOKEN-2022 EXTENSIONS & TRANSFER HOOK AUDIT" in res.stdout
    assert "Transfer Fee Config:" in res.stdout
    assert "150 bps" in res.stdout

    # Test JSON mode
    res_json = subprocess.run(
        [sys.executable, "-m", "solana_tx_lens.cli", "token-extensions", str(tf), "--amount", "100.0", "--json"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res_json.returncode == 0
    data = json.loads(res_json.stdout)
    assert data["is_token_2022"] is True
    assert data["fee_deducted"] == 1.5


def test_cli_access_list_subcommand(tmp_path):
    repo_root = Path(__file__).parent.parent
    tf = tmp_path / "access.json"
    tf.write_text(
        json.dumps(
            {
                "account_keys": [
                    "Signer1111111111111111111111111111111111111",
                    "Writable11111111111111111111111111111111111",
                ],
                "writable_indices": [0, 1],
                "signer_indices": [0],
            }
        )
    )

    res = subprocess.run(
        [sys.executable, "-m", "solana_tx_lens.cli", "access-list", str(tf)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res.returncode == 0
    assert "SEALEVEL STATE ACCESS LIST & CONCURRENCY AUDIT" in res.stdout
    assert "Total Accounts:      2" in res.stdout
    assert "Concurrency Score:   100/100" in res.stdout


def test_cli_verify_policy_subcommand(tmp_path):
    repo_root = Path(__file__).parent.parent
    sim_file = tmp_path / "sim.json"
    sim_file.write_text(json.dumps({"unitsConsumed": 45000, "logs": []}))
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(
        json.dumps(
            [
                {"rule_id": "r_cu", "rule_type": "max_compute_units", "params": {"limit": 100000}}
            ]
        )
    )

    res = subprocess.run(
        [sys.executable, "-m", "solana_tx_lens.cli", "verify-policy", str(sim_file), "--rules", str(rules_file)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res.returncode == 0
    assert "PRE-FLIGHT SAFETY POLICY & INVARIANT AUDIT" in res.stdout
    assert "Policy Status:       PASSED" in res.stdout


def test_cli_zero_copy_subcommand(tmp_path):
    repo_root = Path(__file__).parent.parent
    zc_file = tmp_path / "zc.json"
    zc_file.write_text(
        json.dumps(
            {
                "struct_name": "VaultAccount",
                "fields": [["authority", "Pubkey"], ["amount", "u64"]],
                "has_discriminator": True,
            }
        )
    )

    res = subprocess.run(
        [sys.executable, "-m", "solana_tx_lens.cli", "zero-copy", str(zc_file)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res.returncode == 0
    assert "ZERO-COPY MEMORY LAYOUT AUDIT: VaultAccount" in res.stdout
    assert "8-Byte Aligned:      True" in res.stdout
    assert "BPF Memory Safe:     True" in res.stdout


def test_cli_idl_subcommand():
    repo_root = Path(__file__).parent.parent
    import hashlib
    import struct
    disc = hashlib.sha256("global:buy".encode()).digest()[:8]
    data_hex = (disc + struct.pack("<QQ", 500000, 25000)).hex()

    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "solana_tx_lens.cli",
            "idl",
            "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
            "--data",
            data_hex,
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res.returncode == 0
    assert "ANCHOR IDL INSTRUCTION DECODER" in res.stdout
    assert "Instruction Name:   buy" in res.stdout
    assert "amount: 500000" in res.stdout


def test_cli_flamegraph_subcommand(tmp_path):
    repo_root = Path(__file__).parent.parent
    log_file = tmp_path / "logs.txt"
    log_file.write_text(
        "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke [1]\n"
        "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA consumed 3500 of 200000 compute units\n"
        "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA success\n"
    )
    svg_file = tmp_path / "flame.svg"

    res = subprocess.run(
        [sys.executable, "-m", "solana_tx_lens.cli", "flamegraph", str(log_file), "--ascii", "--svg", str(svg_file)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res.returncode == 0
    assert "Execution Flamegraph" in res.stdout
    assert svg_file.exists()
    assert "<svg" in svg_file.read_text()


def test_cli_compression_subcommand():
    repo_root = Path(__file__).parent.parent
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "solana_tx_lens.cli",
            "compression",
            "--depth",
            "14",
            "--buffer",
            "64",
            "--canopy",
            "0",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert res.returncode == 0
    assert "SPL CONCURRENT MERKLE TREE AUDIT" in res.stdout
    assert "Max Depth:           14 (Capacity: 16,384 leaves)" in res.stdout
    assert "MTU Safe:            True" in res.stdout


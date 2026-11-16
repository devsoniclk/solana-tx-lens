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

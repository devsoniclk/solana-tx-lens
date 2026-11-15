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

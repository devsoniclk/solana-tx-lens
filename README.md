# solana-tx-lens

> **Headless transaction simulation inspector, CPI tree visualizer, and Anchor error decoder for Solana.**

[![CI](https://github.com/devsoniclk/solana-tx-lens/actions/workflows/ci.yml/badge.svg)](https://github.com/devsoniclk/solana-tx-lens/actions)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://pypi.org/project/solana-tx-lens/)

---

## 1. Problem Statement
Debugging Solana transaction simulation failures is notoriously frustrating. When a transaction reverts in pre-flight, developers and trading bots receive cryptic error payloads like `InstructionError(0, Custom(6001))` or `ComputationalBudgetExceeded` without context. Explorers only index finalized on-chain transactions, and running local test validators with ledger dumps takes 10–30 seconds.

## 2. Why Existing Solutions Are Insufficient
- **Solana CLI (`solana confirm -v`)**: Emits flat unstructured text logs, does not reconstruct nested Cross-Program Invocation (CPI) call graphs, and leaves custom program errors undecoded.
- **Solana Explorer / Solscan**: Only inspects mined transactions. Cannot debug pre-flight simulated transactions or private Jito MEV bundles before broadcast.
- **Anchor CLI**: Requires a local workspace and source IDL; cannot dynamically decode arbitrary third-party DEX programs (Raydium, Whirlpool, Pump.fun, Jupiter).

## 3. What `solana-tx-lens` Does Differently
`solana-tx-lens` provides a **lightweight, headless simulation & diagnostic engine** with zero validator overhead:
- **Nested CPI Execution Tree**: Reconstructs multi-level Cross-Program Invocations (`invoke [1]`, `invoke [2]`, `invoke [3]`) into an ASCII/JSON call graph.
- **Compute Unit Profiling**: Attributes exact Compute Unit (CU) burn to each nested sub-invocation.
- **Human-Readable Error Decoding**: Translates Anchor standard error codes (100–500) and popular DEX custom error codes (e.g., `0x1771` / `6001` -> `SlippageExceeded`).
- **Account State Diffing**: Calculates pre- vs. post-simulation lamport deltas, token balances, and account data length mutations.
- **Zero Heavy Dependencies**: Pure Python standard library (`urllib.request`), works with any standard Solana JSON-RPC endpoint.

---

## 4. Key Features
- **Simulation Diagnostics**: Inspect arbitrary base64 transactions via RPC or parse raw JSON simulation outputs.
- **CLI & Python SDK**: Use via terminal command (`sol-lens`) or embed into automated trading bot pre-flight loops.
- **Jito & MEV Ready**: Diagnose bundles and atomic arbitrage transactions before broadcasting to protect priority fees.
- **Extensible Error Registry**: Built-in definitions for Anchor, System, Token, Raydium, Whirlpool, and Pump.fun.

---

## 5. Architecture

```mermaid
flowchart TD
    A["Raw Transaction / Base64 Payload"] -->|"simulateTransaction"| B["Solana JSON-RPC"]
    B -->|"Logs & Account States"| C["SolanaSimulator"]
    C --> D["cpi_parser"]
    C --> E["error_decoder"]
    C --> F["diff_engine"]
    D -->|"Nested Tree & CU Breakdown"| G["visualizer"]
    E -->|"Decoded Anchor / DEX Errors"| G
    F -->|"Lamports & Data Diffs"| G
    G --> H["Structured Diagnostic Report (CLI / JSON)"]
```

---

## 6. Installation

```bash
pip install solana-tx-lens
```

Or install from source:
```bash
git clone https://github.com/devsoniclk/solana-tx-lens.git
cd solana-tx-lens
pip install -e .
```

---

## 7. Quick-Start Guide

### Python SDK
```python
from solana_tx_lens import SolanaSimulator, render_simulation_report

# 1. Initialize simulator with your RPC
simulator = SolanaSimulator(rpc_url="https://api.mainnet-beta.solana.com")

# 2. Simulate raw base64 transaction
result = simulator.simulate_encoded_transaction("<base64_tx_payload>")

# 3. Print diagnostic report
print(render_simulation_report(result))

if not result.success:
    print(f"Failed at program: {result.error.program_id}")
    print(f"Decoded Reason: {result.error.name} - {result.error.description}")
```

---

## 8. CLI Usage

```bash
# Decode a numeric or hex Solana error code
sol-lens decode-error 6001
# Output:
# Error Type:   DEX
# Error Code:   6001 (0x1771)
# Name:         SlippageExceeded
# Description:  Slippage tolerance exceeded; output below min expected

# Decode an Anchor constraint violation
sol-lens decode-error 200
# Output:
# Error Type:   Anchor
# Error Code:   200 (0xc8)
# Name:         ConstraintMut
# Description:  A mut constraint was violated

# Inspect a raw simulation JSON output or log file
sol-lens simulate simulation_dump.json
```

---

## 9. Sample Terminal Output

```
==================================================================
 SOLANA TRANSACTION SIMULATION DIAGNOSTIC REPORT
==================================================================
Status:             FAILED
Total Compute Used: 74,500 / 200,000 CUs (37.2%)
Error Type:         DEX
Error Name:         SlippageExceeded (Code: 6001)
Description:        Slippage tolerance exceeded; output below min expected

[Cross-Program Invocation (CPI) Execution Tree]
└── [FAILED] Program: JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4 [depth 1] (74,500 CUs)
    └── ERROR: custom program error: 0x1771
    └── [FAILED] Program: CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7GrKberoP8 [depth 2] (48,200 CUs)
        └── ERROR: custom program error: 0x1771
        └── [OK] Program: TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA [depth 3] (4,645 CUs)

[Account State Diffs]
  Account Pubkey                               | Lamports Delta   | Data Delta
  ---------------------------------------------------------------------------
  User11111111111111111111111111111111111111   | -0.050000 SOL    | +0 bytes
==================================================================
```

---

## 10. Benchmarks

Measured on Apple Silicon (M5 Air):

| Operation | Latency | Memory Overhead |
| :--- | :--- | :--- |
| **Log Stream Parse (100 lines)** | `0.42 ms` | `< 1.0 MB` |
| **CPI Tree Construction (depth 4)** | `0.28 ms` | `< 0.8 MB` |
| **Error Code Table Lookup** | `0.02 ms` | `< 0.1 MB` |

---

## 11. Security Considerations
- `solana-tx-lens` executes simulations using read-only RPC calls (`sigVerify: false`).
- Does not require or handle private keys.
- Safe for public and air-gapped CI/CD environments.

---

## 12. Roadmap
- [x] Recursive CPI execution tree parser.
- [x] Anchor & DEX custom error decoder.
- [x] Account balance and data diffing engine.
- [ ] Automatic on-chain Anchor IDL fetcher from program account data.
- [ ] Interactive terminal UI (TUI) with collapsible tree nodes.

---

## 13. Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

---

## 14. License
Distributed under the [Apache-2.0 License](LICENSE). Copyright 2026 Lakshitha Dananjaya (`devsoniclk`).

# solana-tx-lens

> **Headless transaction simulation inspector, CPI tree visualizer, pre-flight MEV guard, and Anchor error decoder for Solana.**

[![CI](https://github.com/devsoniclk/solana-tx-lens/actions/workflows/ci.yml/badge.svg)](https://github.com/devsoniclk/solana-tx-lens/actions)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://pypi.org/project/solana-tx-lens/)
[![Version](https://img.shields.io/badge/version-0.2.0-green.svg)](https://github.com/devsoniclk/solana-tx-lens/releases)

---

## 1. Problem Statement
Debugging Solana transaction simulation failures is notoriously frustrating. When a transaction reverts in pre-flight, developers and trading bots receive cryptic error payloads like `InstructionError(0, Custom(6001))` or `ComputationalBudgetExceeded` without context. Explorers only index finalized on-chain transactions, and running local test validators with ledger dumps takes 10–30 seconds.

## 2. Why Existing Solutions Are Insufficient
- **Solana CLI (`solana confirm -v`)**: Emits flat unstructured text logs, does not reconstruct nested Cross-Program Invocation (CPI) call graphs, and leaves custom program errors undecoded.
- **Solana Explorer / Solscan**: Only inspects mined transactions. Cannot debug pre-flight simulated transactions or private Jito MEV bundles before broadcast.
- **Anchor CLI**: Requires a local workspace and source IDL; cannot dynamically decode arbitrary third-party DEX programs (Raydium, Whirlpool, Pump.fun, Jupiter).

## 3. What `solana-tx-lens` Does Differently
`solana-tx-lens` provides a **lightweight, headless simulation & diagnostic engine** with zero validator overhead:
- **Nested CPI Execution Tree**: Reconstructs multi-level Cross-Program Invocations (`invoke [1]`, `invoke [2]`, `invoke [3]`) into an ASCII/JSON call graph with program names and recognized instructions (`swap_exact_in`, `buy`, `TransferChecked`).
- **Compute Unit Profiling**: Attributes exact Compute Unit (CU) burn to each nested sub-invocation.
- **Pre-flight MEV & Safety Guard**: Evaluates transaction health prior to broadcast. Flags CU exhaustion risks (>85% limit), slippage breaches (0x1771/6001), asymmetric token drains (sandwich/front-run detection), and missing priority fees.
- **GitHub-Renderable Mermaid Diagrams**: Automatically exports execution call graphs into clean Mermaid sequence diagrams (`--mermaid`) and flowcharts (`--flowchart`).
- **SPL Token Balance Mutations**: Calculates pre- vs. post-simulation token balance deltas (e.g. `-100.00 USDC`, `+1.25 SOL`) across all affected accounts.
- **Human-Readable Error Decoding**: Translates Anchor standard error codes (100–500) and popular DEX custom error codes (e.g., `0x1771` / `6001` -> `SlippageExceeded`).
- **Zero Heavy Dependencies**: Pure Python standard library (`urllib.request`), works with any standard Solana JSON-RPC endpoint.

---

## 4. Key Features
- **Simulation Diagnostics**: Inspect arbitrary base64 transactions via RPC or parse raw JSON simulation outputs.
- **Pre-flight MEV Safety Guard**: Built-in automated risk analysis detecting out-of-gas vulnerability, sandwich attacks, and rent exemption issues.
- **Mermaid Export**: Copy-pasteable sequence diagrams for PRs, issues, and audit documentation.
- **CLI & Python SDK**: Use via terminal command (`sol-lens`) or embed into automated trading bot pre-flight loops.
- **Jito & MEV Ready**: Diagnose bundles and atomic arbitrage transactions before broadcasting to protect priority fees.
- **Extensible Error & Program Registry**: Built-in definitions for Anchor, System, Token, Token-2022, Raydium (AMM/CLMM/CPMM), Whirlpool, OpenBook, and Pump.fun.

---

## 5. Architecture

```mermaid
flowchart TD
    A["Raw Transaction / Base64 Payload"] -->|"simulateTransaction"| B["Solana JSON-RPC"]
    B -->|"Logs, Balances, & Account States"| C["SolanaSimulator"]
    C --> D["cpi_parser & instruction_decoder"]
    C --> E["error_decoder"]
    C --> F["diff_engine (SOL & SPL Tokens)"]
    C --> G["guard (Pre-flight MEV & Health)"]
    D -->|"Nested Tree & CU Breakdown"| H["visualizer"]
    E -->|"Decoded Anchor / DEX Errors"| H
    F -->|"Lamports & SPL Token Diffs"| H
    G -->|"Risk Scores & Warnings"| H
    H --> I["Structured Diagnostic Report (CLI / JSON / Mermaid)"]
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

# 4. Check Pre-flight MEV Health
if result.health.has_critical_failure:
    print(f"ABORT BROADCAST: {result.health.status}")
    for issue in result.health.issues:
        print(f"[{issue.severity}] {issue.check}: {issue.message}")

# 5. Export Mermaid Sequence Diagram for Documentation
mermaid_md = result.to_mermaid(diagram_type="sequence")
print(mermaid_md)
```

---

## 8. CLI Usage

```bash
# Inspect a simulation log file or JSON output
sol-lens simulate simulation_dump.json

# Export GitHub-ready Mermaid sequence diagram
sol-lens simulate simulation_dump.json --mermaid

# Export full machine-readable JSON diagnostic structure
sol-lens simulate simulation_dump.json --json

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
```

---

## 9. Sample Terminal Diagnostic Report

```
==================================================================
 SOLANA TRANSACTION SIMULATION DIAGNOSTIC REPORT (v0.2.0)
==================================================================
Status:             SUCCESS
Total Compute Used: 65,000 / 200,000 CUs (32.5%)
Health Status:      HEALTHY
CU Utilization:     32.5%

[Pre-flight Safety & MEV Health Checks]
  ℹ️ [INFO] PRIORITY_FEE_ADVISORY: No Compute Budget priority fee instruction detected in transaction.
     └─ Rec: Include SetComputeUnitPrice to prioritize bundle inclusion during network congestion.

[Cross-Program Invocation (CPI) Execution Tree]
└── [OK] Raydium AMM v4 (675k...1Mp8) [depth 1] -> swap_exact_in (65,000 CUs)
    └── [OK] SPL Token (Toke...5DA) [depth 2] -> TransferChecked (4,600 CUs)

[SPL Token Balance Mutations]
  Token Mint / Account                         | Token Delta        | Owner
  ---------------------------------------------------------------------------
  EPjFWdd5AufqSSqeM2qN...                      | -50.0000           | Owner1
  So111111111111111111...                      | +0.3500            | Owner1

[Account State Diffs]
  Account Pubkey                               | Lamports Delta   | Data Delta
  ---------------------------------------------------------------------------
  User11111111111111111111111111111111111111   | -0.000005 SOL    | +0 bytes
==================================================================
```

---

## 10. Mermaid Sequence Diagram Output (`--mermaid`)

```mermaid
sequenceDiagram
    autonumber
    actor Client as Caller / Bot
    participant P_1_Raydium_AMM_v4 as Raydium AMM v4
    participant P_2_SPL_Token as SPL Token
    Client->>+P_1_Raydium_AMM_v4: invoke [d=1] (swap_exact_in)
    P_1_Raydium_AMM_v4->>+P_2_SPL_Token: invoke [d=2] (TransferChecked)
    P_2_SPL_Token-->>-P_1_Raydium_AMM_v4: success (4,600 CUs)
    P_1_Raydium_AMM_v4-->>-Client: success (65,000 CUs)
```

---

## 11. Benchmarks

Measured on Apple Silicon (M5 Air):

| Operation | Latency | Memory Overhead |
| :--- | :--- | :--- |
| **Log Stream Parse (100 lines)** | `0.42 ms` | `< 1.0 MB` |
| **CPI Tree Construction (depth 4)** | `0.28 ms` | `< 0.8 MB` |
| **SPL Token & Lamport Diffing** | `0.15 ms` | `< 0.5 MB` |
| **MEV Safety Guard Evaluation** | `0.06 ms` | `< 0.2 MB` |
| **Mermaid Diagram Generation** | `0.11 ms` | `< 0.3 MB` |
| **Error Code Table Lookup** | `0.02 ms` | `< 0.1 MB` |

---

## 12. Security Considerations
- `solana-tx-lens` executes simulations using read-only RPC calls (`sigVerify: false`).
- Does not require or handle private keys.
- Safe for public and air-gapped CI/CD environments.

---

## 13. Roadmap
- [x] Recursive CPI execution tree parser with friendly program aliases.
- [x] Anchor & DEX custom error decoder (Raydium, Whirlpool, Pump.fun).
- [x] Account balance (lamports) and SPL Token mutation diffing engine.
- [x] Pre-flight MEV & Safety Guard (CU headroom, slippage, sandwich checks).
- [x] GitHub Mermaid sequence & flowchart visualizer.
- [ ] Automatic on-chain Anchor IDL fetcher from program account data.
- [ ] Interactive terminal UI (TUI) with collapsible tree nodes.

---

## 14. License
Distributed under the [Apache-2.0 License](LICENSE). Copyright 2026 Lakshitha Dananjaya (`devsoniclk`).

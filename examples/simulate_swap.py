"""
Example: Simulating and diagnosing a Solana DEX swap simulation failure using `solana-tx-lens`.
"""

from solana_tx_lens import SolanaSimulator, render_cpi_tree
from solana_tx_lens.visualizer import render_simulation_report

# Example raw simulation logs from a failed Raydium CLMM swap
simulation_payload = {
    "unitsConsumed": 74500,
    "logs": [
        "Program JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4 invoke [1]",
        "Program log: Instruction: Route",
        "Program CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7GrKberoP8 invoke [2]",
        "Program log: Instruction: Swap",
        "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke [3]",
        "Program log: Instruction: Transfer",
        "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA consumed 4645 of 120000 compute units",
        "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA success",
        "Program log: Error: Slippage tolerance exceeded",
        "Program CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7GrKberoP8 consumed 48200 of 145000 compute units",
        "Program CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7GrKberoP8 failed: custom program error: 0x1771",
        "Program JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4 consumed 74500 of 200000 compute units",
        "Program JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4 failed: custom program error: 0x1771",
    ],
    "err": {"InstructionError": [0, {"Custom": 6001}]},
    "accounts": [
        {"pubkey": "User11111111111111111111111111111111111111", "lamports": 1_000_000_000, "owner": "11111111111111111111111111111111"},
    ],
}

simulator = SolanaSimulator()
result = simulator.parse_raw_simulation(simulation_payload)

print(render_simulation_report(result))

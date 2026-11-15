import argparse
import json
import sys
from .error_decoder import decode_solana_error
from .simulator import SolanaSimulator
from .visualizer import render_simulation_report


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sol-lens",
        description="Headless Solana transaction simulation inspector and CPI visualizer.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # simulate command
    p_sim = subparsers.add_parser("simulate", help="Simulate a base64 encoded transaction or analyze a log file.")
    p_sim.add_argument("target", help="Base64 transaction string, or path to JSON simulation output / log file.")
    p_sim.add_argument("--rpc", default="https://api.mainnet-beta.solana.com", help="Solana RPC endpoint.")
    p_sim.add_argument("--json", action="store_true", help="Output raw JSON diagnostic structure.")

    # decode-error command
    p_dec = subparsers.add_parser("decode-error", help="Decode a numeric or hex Solana/Anchor error code.")
    p_dec.add_argument("code", help="Error code (e.g. 6001, 0x1771, Custom(6001)).")
    p_dec.add_argument("--program", default=None, help="Optional target program ID.")

    args = parser.parse_args()

    if args.command == "decode-error":
        err_info = decode_solana_error(args.code, args.program)
        print(f"Error Type:   {err_info.error_type}")
        print(f"Error Code:   {err_info.code} (0x{err_info.code:x})" if err_info.code >= 0 else "Error Code:   N/A")
        print(f"Name:         {err_info.name}")
        print(f"Description:  {err_info.description}")

    elif args.command == "simulate":
        # Check if target is a file or raw string
        sim_val = None
        try:
            with open(args.target, "r") as f:
                content = f.read().strip()
                try:
                    sim_val = json.loads(content)
                except json.JSONDecodeError:
                    # Treat as lines of logs
                    sim_val = {"logs": content.splitlines(), "unitsConsumed": 0, "err": None}
        except (FileNotFoundError, OSError):
            pass

        sim = SolanaSimulator(rpc_url=args.rpc)
        if sim_val:
            res = sim.parse_raw_simulation(sim_val)
        else:
            res = sim.simulate_encoded_transaction(args.target)

        if args.json:
            import dataclasses
            print(json.dumps(dataclasses.asdict(res), indent=2))
        else:
            print(render_simulation_report(res))


if __name__ == "__main__":
    main()

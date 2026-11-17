from __future__ import annotations

import struct
import unittest

from solana_tx_lens.idl_decoder import (
    AnchorIDLRegistry,
    compute_account_discriminator,
    compute_anchor_discriminator,
    compute_event_discriminator,
    compute_instruction_discriminator,
    get_default_idl_registry,
)


class TestAnchorIDLDecoder(unittest.TestCase):
    def test_discriminator_computations(self):
        ix_disc = compute_instruction_discriminator("initialize")
        self.assertEqual(len(ix_disc), 8)

        acc_disc = compute_account_discriminator("StateAccount")
        self.assertEqual(len(acc_disc), 8)

        ev_disc = compute_event_discriminator("SwapEvent")
        self.assertEqual(len(ev_disc), 8)

        # Ensure distinct prefixes produce distinct values
        self.assertNotEqual(ix_disc, acc_disc)

    def test_decode_builtin_pump_fun_instruction(self):
        reg = get_default_idl_registry()
        pump_pid = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

        # Build raw bytes for buy instruction: disc (8) + amount (u64) + maxSolCost (u64)
        buy_disc = compute_instruction_discriminator("buy")
        args_payload = struct.pack("<QQ", 1_000_000_000, 50_000_000)
        data = buy_disc + args_payload

        account_keys = [
            "GlobalAccount11111111111111111111111111111",
            "FeeRecipient1111111111111111111111111111111",
            "TokenMint111111111111111111111111111111111",
            "BondingCurve1111111111111111111111111111111",
            "AssociatedBondingCurve1111111111111111111111",
            "AssociatedUser111111111111111111111111111111",
            "UserSigner111111111111111111111111111111111",
        ]

        decoded = reg.decode_instruction(pump_pid, data, account_keys=account_keys)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.instruction_name, "buy")
        self.assertEqual(decoded.args["amount"], 1_000_000_000)
        self.assertEqual(decoded.args["maxSolCost"], 50_000_000)
        self.assertEqual(len(decoded.accounts), 10)
        self.assertEqual(decoded.accounts[0].name, "global")
        self.assertEqual(decoded.accounts[0].pubkey, account_keys[0])

        d = decoded.to_dict()
        self.assertEqual(d["instruction_name"], "buy")
        self.assertEqual(d["program_id"], pump_pid)

    def test_custom_idl_registration_and_error_lookup(self):
        reg = AnchorIDLRegistry()
        my_pid = "MyCustomProgram1111111111111111111111111111"
        idl = {
            "version": "0.1.0",
            "name": "custom",
            "instructions": [
                {
                    "name": "set_fee",
                    "accounts": [{"name": "admin", "isMut": False, "isSigner": True}],
                    "args": [{"name": "basis_points", "type": "u16"}],
                }
            ],
            "errors": [
                {"code": 6005, "name": "FeeTooHigh", "msg": "Configured fee exceeds maximum allowed basis points."}
            ],
        }
        reg.register_idl(my_pid, idl)

        # Test error lookup
        err = reg.decode_error(my_pid, 6005)
        self.assertIsNotNone(err)
        self.assertEqual(err["name"], "FeeTooHigh")
        self.assertIn("exceeds", err["msg"])

        # Test instruction decoding
        disc = compute_instruction_discriminator("set_fee")
        data = disc + struct.pack("<H", 250)
        decoded = reg.decode_instruction(my_pid, data, ["Admin1111111111111111111111111111111111111"])
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.instruction_name, "set_fee")
        self.assertEqual(decoded.args["basis_points"], 250)


if __name__ == "__main__":
    unittest.main()

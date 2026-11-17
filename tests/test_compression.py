from __future__ import annotations

import unittest

from solana_tx_lens.compression import (
    audit_compression_tree,
    calculate_tree_account_size,
)


class TestStateCompressionAuditor(unittest.TestCase):
    def test_tree_account_size_and_capacity(self):
        # 14 depth, 64 buffer, no canopy
        size_no_canopy = calculate_tree_account_size(14, 64, 0)
        self.assertGreater(size_no_canopy, 5000)

        # 14 depth, 64 buffer, canopy depth 10
        # canopy node count = (1 << 11) - 2 = 2046 nodes * 32 bytes = 65,472 bytes
        size_with_canopy = calculate_tree_account_size(14, 64, 10)
        self.assertEqual(size_with_canopy, size_no_canopy + (2046 * 32))

    def test_audit_compression_tree_depth14(self):
        rep = audit_compression_tree(max_depth=14, max_buffer_size=64, canopy_depth=0)
        self.assertEqual(rep.max_capacity_nodes, 16384)
        self.assertEqual(rep.required_proof_len, 14)
        self.assertEqual(rep.proof_bytes_in_tx, 14 * 32)
        self.assertTrue(rep.is_valid_depth_buffer_pair)
        self.assertTrue(rep.is_mtu_safe)

    def test_audit_compression_tree_depth20_with_canopy(self):
        rep = audit_compression_tree(max_depth=20, max_buffer_size=1024, canopy_depth=10)
        self.assertEqual(rep.max_capacity_nodes, 1048576)
        # Required proof = 20 - 10 = 10 nodes (320 bytes), safe for MTU
        self.assertEqual(rep.required_proof_len, 10)
        self.assertEqual(rep.proof_bytes_in_tx, 320)
        self.assertTrue(rep.is_mtu_safe)
        self.assertIn("1,024 concurrent", rep.concurrency_throughput_tier)

        # Serialization check
        d = rep.to_dict()
        self.assertEqual(d["max_depth"], 20)
        self.assertEqual(d["canopy_depth"], 10)
        self.assertIn("rent_exempt_sol", d)

    def test_audit_compression_unsafe_canopy_zero(self):
        # Depth 26 without canopy requires 26 proof nodes (832 bytes) -> MTU dangerous!
        rep = audit_compression_tree(max_depth=26, max_buffer_size=1024, canopy_depth=0)
        self.assertFalse(rep.is_mtu_safe)
        self.assertTrue(any("canopy" in r.lower() for r in rep.recommendations))


if __name__ == "__main__":
    unittest.main()

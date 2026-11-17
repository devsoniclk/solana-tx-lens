from __future__ import annotations

import unittest

from solana_tx_lens.zero_copy import (
    TYPE_SPECS,
    audit_zero_copy_layout,
    benchmark_zero_copy_cu,
    parse_type_spec,
)


class TestZeroCopyAuditor(unittest.TestCase):
    def test_parse_primitive_and_array_types(self):
        u8_spec = parse_type_spec("u8")
        self.assertEqual(u8_spec.size, 1)
        self.assertEqual(u8_spec.alignment, 1)

        u64_spec = parse_type_spec("u64")
        self.assertEqual(u64_spec.size, 8)
        self.assertEqual(u64_spec.alignment, 8)

        pk_spec = parse_type_spec("Pubkey")
        self.assertEqual(pk_spec.size, 32)

        arr_spec = parse_type_spec("[u8; 64]")
        self.assertEqual(arr_spec.size, 64)
        self.assertEqual(arr_spec.alignment, 1)

        arr64_spec = parse_type_spec("[u64; 4]")
        self.assertEqual(arr64_spec.size, 32)
        self.assertEqual(arr64_spec.alignment, 8)

    def test_optimal_zero_copy_struct(self):
        fields = [
            ("authority", "Pubkey"),
            ("vault", "Pubkey"),
            ("total_staked", "u64"),
            ("reward_rate", "u64"),
            ("bump", "u8"),
        ]
        rep = audit_zero_copy_layout("StakingPool", fields, has_discriminator=True)

        self.assertEqual(rep.struct_name, "StakingPool")
        self.assertTrue(rep.is_8byte_aligned)
        self.assertTrue(rep.is_bpf_safe)
        self.assertEqual(len(rep.unaligned_fields), 0)
        self.assertEqual(rep.zero_copy_estimated_cus, 120)
        self.assertGreater(rep.cu_savings_percent, 80.0)

        # Check serialization
        d = rep.to_dict()
        self.assertIn("struct_name", d)
        self.assertIn("total_size", d)
        self.assertEqual(d["is_bpf_safe"], True)

    def test_fragmented_and_unaligned_struct(self):
        # Deliberately pathological ordering with unaligned padding holes
        fields = [
            ("flag1", "u8"),
            ("large_num", "u64"),  # requires 7 bytes padding before
            ("flag2", "u8"),
            ("balance", "u128"),  # requires 7 bytes padding before
            ("flag3", "u8"),
        ]
        rep = audit_zero_copy_layout("FragStruct", fields, has_discriminator=False)

        self.assertGreater(rep.total_padding_bytes, 10)
        self.assertTrue(rep.is_8byte_aligned)
        self.assertTrue(any("padding" in r.lower() for r in rep.recommendations))

    def test_benchmark_zero_copy_cu(self):
        bench = benchmark_zero_copy_cu(total_size=1024, num_fields=16, num_dynamic_vectors=2)
        self.assertEqual(bench["account_size_bytes"], 1024)
        self.assertGreater(bench["cu_savings"], 5000)
        self.assertTrue(bench["zero_copy_recommended"])
        self.assertEqual(bench["zero_copy_deserialization"]["compute_units"], 125)


if __name__ == "__main__":
    unittest.main()

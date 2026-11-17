from __future__ import annotations

import unittest

from solana_tx_lens.flamegraph import (
    build_flamegraph_from_logs,
    render_ascii_flamegraph,
    render_svg_flamegraph,
)


class TestCUFlamegraph(unittest.TestCase):
    def test_build_hierarchical_flamegraph(self):
        logs = [
            "Program JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4 invoke [1]",
            "Program log: Instruction: Route",
            "Program whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc invoke [2]",
            "Program log: Instruction: SwapV2",
            "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke [3]",
            "Program log: Instruction: TransferChecked",
            "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA consumed 4500 of 180000 compute units",
            "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA success",
            "Program whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc consumed 62000 of 190000 compute units",
            "Program whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc success",
            "Program JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4 consumed 78000 of 200000 compute units",
            "Program JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4 success",
        ]

        rep = build_flamegraph_from_logs(logs)

        self.assertEqual(rep.total_cus_consumed, 78000)
        self.assertEqual(rep.max_depth, 3)
        self.assertEqual(len(rep.root_nodes), 1)

        root = rep.root_nodes[0]
        self.assertEqual(root.program_id, "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4")
        self.assertEqual(root.inclusive_cus, 78000)
        self.assertEqual(root.exclusive_cus, 16000)  # 78000 - 62000

        whirl = root.children[0]
        self.assertEqual(whirl.program_id, "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc")
        self.assertEqual(whirl.inclusive_cus, 62000)
        self.assertEqual(whirl.exclusive_cus, 57500)  # 62000 - 4500

        token = whirl.children[0]
        self.assertEqual(token.program_id, "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
        self.assertEqual(token.inclusive_cus, 4500)
        self.assertEqual(token.exclusive_cus, 4500)

        # Check hotspots: whirl consumed 57,500 exclusive CUs (the biggest bottleneck!)
        self.assertGreaterEqual(len(rep.hotspots), 1)
        self.assertEqual(rep.hotspots[0].program_id, "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc")

        # Test ASCII render
        ascii_out = render_ascii_flamegraph(rep)
        self.assertIn("Execution Flamegraph", ascii_out)
        self.assertIn("78,000 CUs", ascii_out)
        self.assertIn("whir...", ascii_out)

        # Test SVG render
        svg_out = render_svg_flamegraph(rep)
        self.assertTrue(svg_out.startswith("<svg"))
        self.assertTrue(svg_out.endswith("</svg>"))
        self.assertIn("78,000 CUs", svg_out)
        self.assertIn("JUP6..TaV4", svg_out)


if __name__ == "__main__":
    unittest.main()

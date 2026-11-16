import pytest
from solana_tx_lens.models import CPIInvocation, SimulationResult, TokenBalanceDiff
from solana_tx_lens.route_analyzer import analyze_swap_route, render_route_ascii, render_route_mermaid


def test_analyze_direct_swap_route():
    res = SimulationResult(
        success=True,
        total_compute_units=75_000,
        max_compute_units=200_000,
        cpi_roots=[
            CPIInvocation(
                program_id="whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",  # Orca Whirlpool
                depth=1,
                program_name="Orca Whirlpool",
                instruction_name="swap",
                consumed_cus=45_000,
            )
        ],
        account_diffs=[],
        token_diffs=[
            TokenBalanceDiff(
                account="Acc1",
                mint="So11111111111111111111111111111111111111112",
                owner="User",
                pre_amount=10.0,
                post_amount=8.0,
                delta=-2.0,
                decimals=9,
                symbol="SOL",
            ),
            TokenBalanceDiff(
                account="Acc2",
                mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                owner="User",
                pre_amount=50.0,
                post_amount=490.0,
                delta=440.0,
                decimals=6,
                symbol="USDC",
            ),
        ],
    )
    report = analyze_swap_route(res)
    assert report.is_swap
    assert report.total_hops == 1
    assert report.input_token == "SOL"
    assert report.output_token == "USDC"
    assert report.input_amount == 2.0
    assert report.output_amount == 440.0
    assert report.hops[0].effective_rate == 220.0
    assert not report.is_cyclic_arbitrage
    assert "Orca Whirlpool" in report.ascii_diagram
    assert "flowchart LR" in report.mermaid_flowchart


def test_analyze_multi_hop_route():
    res = SimulationResult(
        success=True,
        total_compute_units=150_000,
        max_compute_units=200_000,
        cpi_roots=[
            CPIInvocation(
                program_id="JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",  # Jupiter
                depth=1,
                program_name="Jupiter v6",
                instruction_name="Route",
                consumed_cus=140_000,
                children=[
                    CPIInvocation(
                        program_id="whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
                        depth=2,
                        program_name="Orca Whirlpool",
                        instruction_name="swap",
                        consumed_cus=60_000,
                    ),
                    CPIInvocation(
                        program_id="CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",
                        depth=2,
                        program_name="Raydium CLMM",
                        instruction_name="swap",
                        consumed_cus=70_000,
                    ),
                ],
            )
        ],
        account_diffs=[],
        token_diffs=[
            TokenBalanceDiff(
                account="Acc1",
                mint="So11111111111111111111111111111111111111112",
                owner="User",
                pre_amount=5.0,
                post_amount=4.0,
                delta=-1.0,
                decimals=9,
                symbol="SOL",
            ),
            TokenBalanceDiff(
                account="Acc2",
                mint="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                owner="User",
                pre_amount=0.0,
                post_amount=10_000_000.0,
                delta=10_000_000.0,
                decimals=5,
                symbol="BONK",
            ),
        ],
    )
    report = analyze_swap_route(res)
    assert report.is_swap
    assert report.total_hops >= 2
    assert "Orca Whirlpool" in report.dexes_involved
    assert "Raydium CLMM" in report.dexes_involved


def test_analyze_cyclic_arbitrage_route():
    res = SimulationResult(
        success=True,
        total_compute_units=90_000,
        max_compute_units=200_000,
        cpi_roots=[
            CPIInvocation(
                program_id="whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
                depth=1,
                program_name="Orca Whirlpool",
                instruction_name="swap",
                consumed_cus=40_000,
            ),
            CPIInvocation(
                program_id="675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
                depth=1,
                program_name="Raydium AMM v4",
                instruction_name="swap",
                consumed_cus=45_000,
            ),
        ],
        account_diffs=[],
        token_diffs=[
            TokenBalanceDiff(
                account="AccA",
                mint="So11111111111111111111111111111111111111112",
                owner="User",
                pre_amount=10.0,
                post_amount=9.0,
                delta=-1.0,
                decimals=9,
                symbol="SOL",
            ),
            TokenBalanceDiff(
                account="AccB",
                mint="So11111111111111111111111111111111111111112",
                owner="User",
                pre_amount=9.0,
                post_amount=10.05,
                delta=1.05,
                decimals=9,
                symbol="SOL",
            ),
        ],
    )
    report = analyze_swap_route(res)
    assert report.is_swap
    assert report.is_cyclic_arbitrage
    assert report.arbitrage_profit == 0.05
    assert "Cyclic Arbitrage" in report.summary

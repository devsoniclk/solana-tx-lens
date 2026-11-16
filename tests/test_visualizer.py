from solana_tx_lens.models import (
    CPIInvocation,
    ErrorInfo,
    SimulationHealth,
    SimulationResult,
    TokenBalanceDiff,
)
from solana_tx_lens.visualizer import (
    render_cpi_mermaid_flowchart,
    render_cpi_mermaid_sequence,
    render_cpi_tree,
    render_simulation_report,
)


def test_render_mermaid_sequence():
    roots = [
        CPIInvocation(
            program_id="675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
            depth=1,
            program_name="Raydium AMM v4",
            instruction_name="swap_exact_in",
            consumed_cus=45_000,
            children=[
                CPIInvocation(
                    program_id="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                    depth=2,
                    program_name="SPL Token",
                    instruction_name="TransferChecked",
                    consumed_cus=4_600,
                )
            ],
        )
    ]

    seq = render_cpi_mermaid_sequence(roots)
    assert "sequenceDiagram" in seq
    assert "actor Client" in seq
    assert "Raydium AMM v4" in seq
    assert "TransferChecked" in seq
    assert "4,600 CUs" in seq


def test_render_mermaid_flowchart():
    roots = [
        CPIInvocation(
            program_id="6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
            depth=1,
            program_name="Pump.fun",
            instruction_name="buy",
            consumed_cus=32_000,
            children=[
                CPIInvocation(
                    program_id="11111111111111111111111111111111",
                    depth=2,
                    program_name="System Program",
                    instruction_name="Transfer",
                    consumed_cus=1_500,
                )
            ],
        )
    ]

    chart = render_cpi_mermaid_flowchart(roots)
    assert "flowchart TD" in chart
    assert "Pump.fun" in chart
    assert "System Program" in chart
    assert "classDef okNode" in chart


def test_render_simulation_report_with_token_and_health():
    res = SimulationResult(
        success=True,
        total_compute_units=65_000,
        max_compute_units=200_000,
        cpi_roots=[
            CPIInvocation(
                program_id="675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
                depth=1,
                program_name="Raydium AMM v4",
                instruction_name="swap_exact_in",
                consumed_cus=65_000,
            )
        ],
        account_diffs=[],
        token_diffs=[
            TokenBalanceDiff(
                account="AccA",
                mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                owner="Owner1",
                pre_amount=50.0,
                post_amount=0.0,
                delta=-50.0,
                decimals=6,
            ),
            TokenBalanceDiff(
                account="AccB",
                mint="So11111111111111111111111111111111111111112",
                owner="Owner1",
                pre_amount=1.0,
                post_amount=1.35,
                delta=0.35,
                decimals=9,
            ),
        ],
        health=SimulationHealth(
            status="HEALTHY",
            cu_utilization_pct=32.5,
            issues=[],
        ),
    )

    report = render_simulation_report(res)
    assert "DIAGNOSTIC REPORT (v0.3.0)" in report
    assert "SPL Token Balance Mutations" in report
    assert "-50.0000" in report
    assert "+0.3500" in report
    assert "Health Status:      HEALTHY" in report

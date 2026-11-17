from __future__ import annotations

"""
solana_tx_lens.compression: SPL State Compression & Concurrent Merkle Tree Auditor.

Audits Concurrent Merkle Tree parameters (max_depth, max_buffer_size, canopy_depth),
calculates tree storage capacity, required on-chain account sizes, rent-exempt costs,
transaction proof payload byte footprints, and IPv6 1,232-byte MTU limit compliance.
"""

from dataclasses import asdict, dataclass
import math
from typing import Any

SPL_ACCOUNT_COMPRESSION_PROGRAM_ID = "cmtDvXumGCrqC1Age74AVPhSRVXJMd8PJS91L8KbNCK"
SOLANA_TX_MTU_BYTES = 1232

# Standard supported (max_depth, max_buffer_size) pairs per SPL account compression
VALID_DEPTH_BUFFER_PAIRS: set[tuple[int, int]] = {
    (3, 8),
    (5, 8),
    (14, 64),
    (14, 256),
    (14, 1024),
    (14, 2048),
    (20, 64),
    (20, 256),
    (20, 1024),
    (20, 2048),
    (24, 64),
    (24, 256),
    (24, 512),
    (24, 1024),
    (24, 2048),
    (26, 512),
    (26, 1024),
    (26, 2048),
    (30, 512),
    (30, 1024),
    (30, 2048),
}


@dataclass
class CompressionTreeAuditReport:
    max_depth: int
    max_buffer_size: int
    canopy_depth: int
    max_capacity_nodes: int
    required_proof_len: int
    proof_bytes_in_tx: int
    canopy_node_count: int
    tree_account_size_bytes: int
    rent_exempt_lamports: int
    rent_exempt_sol: float
    is_valid_depth_buffer_pair: bool
    is_mtu_safe: bool
    concurrency_throughput_tier: str
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_depth": self.max_depth,
            "max_buffer_size": self.max_buffer_size,
            "canopy_depth": self.canopy_depth,
            "max_capacity_nodes": self.max_capacity_nodes,
            "required_proof_len": self.required_proof_len,
            "proof_bytes_in_tx": self.proof_bytes_in_tx,
            "canopy_node_count": self.canopy_node_count,
            "tree_account_size_bytes": self.tree_account_size_bytes,
            "rent_exempt_lamports": self.rent_exempt_lamports,
            "rent_exempt_sol": round(self.rent_exempt_sol, 4),
            "is_valid_depth_buffer_pair": self.is_valid_depth_buffer_pair,
            "is_mtu_safe": self.is_mtu_safe,
            "concurrency_throughput_tier": self.concurrency_throughput_tier,
            "recommendations": self.recommendations,
        }


def calculate_tree_account_size(max_depth: int, max_buffer_size: int, canopy_depth: int) -> int:
    """
    Computes exact byte footprint of an SPL Concurrent Merkle Tree account.
    Layout:
      - Header: 104 bytes
      - ChangeLog buffer: max_buffer_size * 72 bytes
      - Right-most path cache: max_depth * 32 bytes
      - Canopy nodes: ((1 << (canopy_depth + 1)) - 2) * 32 bytes (if canopy_depth > 0)
    """
    header_bytes = 104
    changelog_bytes = max_buffer_size * 72
    path_bytes = max_depth * 32
    canopy_bytes = 0
    if canopy_depth > 0:
        canopy_nodes = (1 << (canopy_depth + 1)) - 2
        canopy_bytes = canopy_nodes * 32

    return header_bytes + changelog_bytes + path_bytes + canopy_bytes


def audit_compression_tree(
    max_depth: int,
    max_buffer_size: int,
    canopy_depth: int = 0,
) -> CompressionTreeAuditReport:
    """
    Audits an SPL State Compression Concurrent Merkle Tree configuration.
    """
    max_capacity = 1 << max_depth
    is_valid_pair = (max_depth, max_buffer_size) in VALID_DEPTH_BUFFER_PAIRS

    # Required proof length that callers must pass in transaction accounts
    required_proof_len = max(0, max_depth - canopy_depth)
    proof_bytes = required_proof_len * 32

    canopy_node_count = ((1 << (canopy_depth + 1)) - 2) if canopy_depth > 0 else 0
    tree_size = calculate_tree_account_size(max_depth, max_buffer_size, canopy_depth)

    # Solana rent: 890,880 base lamports + 6,960 lamports per byte
    rent_lamports = 890880 + (tree_size * 6960)
    rent_sol = rent_lamports / 1_000_000_000.0

    # MTU safety: if proof bytes > 448 bytes (14 accounts), transactions frequently breach MTU
    is_mtu_safe = proof_bytes <= 448

    # Throughput tier
    if max_buffer_size >= 2048:
        throughput_tier = "Ultra-High Throughput (2,048 concurrent slot updates)"
    elif max_buffer_size >= 1024:
        throughput_tier = "High Throughput (1,024 concurrent slot updates)"
    elif max_buffer_size >= 256:
        throughput_tier = "Standard Throughput (256 concurrent slot updates)"
    else:
        throughput_tier = "Low Concurrency (64 concurrent slot updates)"

    recommendations: list[str] = []
    if not is_valid_pair:
        recommendations.append(
            f"Invalid (max_depth={max_depth}, max_buffer_size={max_buffer_size}) pair. Use supported standard SPL pairs."
        )

    if canopy_depth == 0 and max_depth > 14:
        recommendations.append(
            f"Canopy depth is 0 with max_depth {max_depth}. Transactions will require {max_depth} proof accounts ({proof_bytes} bytes), risking transaction MTU limit overflow. Recommend canopy_depth >= {max_depth - 10}."
        )
    elif canopy_depth > max_depth:
        recommendations.append(
            f"Canopy depth ({canopy_depth}) exceeds max_depth ({max_depth}). Canopy depth must be <= max_depth."
        )

    if not is_mtu_safe:
        recommendations.append(
            f"Proof payload ({proof_bytes} bytes) consumes >36% of the 1,232-byte transaction MTU. Increase canopy_depth to reduce client proof payload."
        )

    if not recommendations:
        recommendations.append(
            f"Tree configuration optimal: capacity {max_capacity:,} leaves, proof footprint {proof_bytes} bytes ({required_proof_len} nodes), MTU safe."
        )

    return CompressionTreeAuditReport(
        max_depth=max_depth,
        max_buffer_size=max_buffer_size,
        canopy_depth=canopy_depth,
        max_capacity_nodes=max_capacity,
        required_proof_len=required_proof_len,
        proof_bytes_in_tx=proof_bytes,
        canopy_node_count=canopy_node_count,
        tree_account_size_bytes=tree_size,
        rent_exempt_lamports=rent_lamports,
        rent_exempt_sol=rent_sol,
        is_valid_depth_buffer_pair=is_valid_pair,
        is_mtu_safe=is_mtu_safe,
        concurrency_throughput_tier=throughput_tier,
        recommendations=recommendations,
    )

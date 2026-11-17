from __future__ import annotations

"""
solana_tx_lens.zero_copy: Zero-Copy Account Memory Layout & Alignment Auditor.

Audits Solana account structures against Anchor `zero_copy`, `bytemuck::Pod`,
`bytemuck::Zeroable`, and C-representation (`#[repr(C)]`) memory alignment constraints.
Computes field offsets, padding holes, 8-byte alignment compliance for Solana eBPF,
and calculates Compute Unit (CU) savings compared to standard Borsh deserialization.
"""

from dataclasses import asdict, dataclass
import math
from typing import Any


@dataclass
class FieldTypeSpec:
    size: int
    alignment: int
    is_pod: bool = True
    description: str = ""


# Standard type specifications for 64-bit Solana BPF target
TYPE_SPECS: dict[str, FieldTypeSpec] = {
    "u8": FieldTypeSpec(size=1, alignment=1, is_pod=True, description="Unsigned 8-bit integer"),
    "i8": FieldTypeSpec(size=1, alignment=1, is_pod=True, description="Signed 8-bit integer"),
    "bool": FieldTypeSpec(size=1, alignment=1, is_pod=True, description="1-byte boolean"),
    "u16": FieldTypeSpec(size=2, alignment=2, is_pod=True, description="Unsigned 16-bit integer (little-endian)"),
    "i16": FieldTypeSpec(size=2, alignment=2, is_pod=True, description="Signed 16-bit integer"),
    "u32": FieldTypeSpec(size=4, alignment=4, is_pod=True, description="Unsigned 32-bit integer"),
    "i32": FieldTypeSpec(size=4, alignment=4, is_pod=True, description="Signed 32-bit integer"),
    "f32": FieldTypeSpec(size=4, alignment=4, is_pod=True, description="32-bit IEEE float"),
    "u64": FieldTypeSpec(size=8, alignment=8, is_pod=True, description="Unsigned 64-bit integer / lamports"),
    "i64": FieldTypeSpec(size=8, alignment=8, is_pod=True, description="Signed 64-bit integer / Unix timestamp"),
    "f64": FieldTypeSpec(size=8, alignment=8, is_pod=True, description="64-bit IEEE float"),
    "u128": FieldTypeSpec(size=16, alignment=8, is_pod=True, description="Unsigned 128-bit integer (8-byte aligned on C-repr)"),
    "i128": FieldTypeSpec(size=16, alignment=8, is_pod=True, description="Signed 128-bit integer"),
    "Pubkey": FieldTypeSpec(size=32, alignment=1, is_pod=True, description="32-byte Solana public key"),
    "pubkey": FieldTypeSpec(size=32, alignment=1, is_pod=True, description="32-byte Solana public key"),
}


def parse_type_spec(type_str: str) -> FieldTypeSpec:
    """Parses raw type string, including fixed-size arrays like [u8; 32] or [u64; 4]."""
    cleaned = type_str.strip()
    if cleaned in TYPE_SPECS:
        return TYPE_SPECS[cleaned]

    # Array parsing: [type; N]
    if cleaned.startswith("[") and cleaned.endswith("]"):
        inner = cleaned[1:-1].strip()
        if ";" in inner:
            elem_type_str, count_str = [p.strip() for p in inner.split(";", 1)]
            try:
                count = int(count_str)
                elem_spec = parse_type_spec(elem_type_str)
                return FieldTypeSpec(
                    size=elem_spec.size * count,
                    alignment=elem_spec.alignment,
                    is_pod=elem_spec.is_pod,
                    description=f"Fixed array of {count} x {elem_type_str}",
                )
            except ValueError:
                pass

    # Default fallback: unknown custom type, assume 8-byte aligned pointer or blob
    return FieldTypeSpec(size=8, alignment=8, is_pod=True, description=f"Custom type: {type_str}")


@dataclass
class FieldLayout:
    name: str
    type_name: str
    size: int
    alignment: int
    offset: int
    padding_before: int
    is_aligned: bool


@dataclass
class ZeroCopyAuditReport:
    struct_name: str
    total_size: int
    usable_size: int
    total_padding_bytes: int
    padding_ratio: float
    is_8byte_aligned: bool
    has_discriminator: bool
    unaligned_fields: list[str]
    fields: list[FieldLayout]
    borsh_estimated_cus: int
    zero_copy_estimated_cus: int
    cu_savings_percent: float
    is_bpf_safe: bool
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "struct_name": self.struct_name,
            "total_size": self.total_size,
            "usable_size": self.usable_size,
            "total_padding_bytes": self.total_padding_bytes,
            "padding_ratio": round(self.padding_ratio, 4),
            "is_8byte_aligned": self.is_8byte_aligned,
            "has_discriminator": self.has_discriminator,
            "unaligned_fields": self.unaligned_fields,
            "fields": [asdict(f) for f in self.fields],
            "borsh_estimated_cus": self.borsh_estimated_cus,
            "zero_copy_estimated_cus": self.zero_copy_estimated_cus,
            "cu_savings_percent": round(self.cu_savings_percent, 2),
            "is_bpf_safe": self.is_bpf_safe,
            "recommendations": self.recommendations,
        }


def audit_zero_copy_layout(
    struct_name: str,
    fields: list[tuple[str, str]],
    has_discriminator: bool = True,
) -> ZeroCopyAuditReport:
    """
    Audits a struct definition against #[repr(C)] memory alignment and Anchor zero_copy rules.

    :param struct_name: Name of the account struct.
    :param fields: List of (field_name, field_type_str) tuples.
    :param has_discriminator: Whether Anchor injects an 8-byte discriminator prefix.
    """
    current_offset = 0
    total_padding = 0
    usable_bytes = 0
    layouts: list[FieldLayout] = []
    unaligned_fields: list[str] = []
    max_align = 8  # Anchor zero_copy enforces 8-byte alignment

    if has_discriminator:
        current_offset = 8
        usable_bytes += 8
        layouts.append(
            FieldLayout(
                name="_discriminator",
                type_name="[u8; 8]",
                size=8,
                alignment=8,
                offset=0,
                padding_before=0,
                is_aligned=True,
            )
        )

    for name, type_str in fields:
        spec = parse_type_spec(type_str)
        align = spec.alignment
        max_align = max(max_align, align)

        # Calculate padding needed to satisfy field alignment
        remainder = current_offset % align
        padding_before = (align - remainder) % align

        offset = current_offset + padding_before
        total_padding += padding_before
        usable_bytes += spec.size

        # Check if offset is naturally aligned
        is_aligned = (offset % align) == 0
        if not is_aligned:
            unaligned_fields.append(name)

        layouts.append(
            FieldLayout(
                name=name,
                type_name=type_str,
                size=spec.size,
                alignment=align,
                offset=offset,
                padding_before=padding_before,
                is_aligned=is_aligned,
            )
        )
        current_offset = offset + spec.size

    # Tail padding to make struct size a multiple of max_align (at least 8 for zero_copy)
    tail_remainder = current_offset % max_align
    tail_padding = (max_align - tail_remainder) % max_align
    total_padding += tail_padding
    total_size = current_offset + tail_padding

    if tail_padding > 0:
        layouts.append(
            FieldLayout(
                name="_tail_padding",
                type_name=f"[u8; {tail_padding}]",
                size=tail_padding,
                alignment=1,
                offset=current_offset,
                padding_before=0,
                is_aligned=True,
            )
        )

    padding_ratio = total_padding / total_size if total_size > 0 else 0.0
    is_8byte_aligned = (total_size % 8) == 0

    # Calculate estimated CUs
    # Borsh: ~5 CUs per byte + ~50 CUs per field allocation overhead
    borsh_cus = max(1000, int(total_size * 6.5 + len(fields) * 80))
    # Zero-copy: direct slice pointer cast + 8-byte discriminator check ~120-150 CUs flat!
    zero_copy_cus = 120
    savings_pct = max(0.0, ((borsh_cus - zero_copy_cus) / borsh_cus) * 100.0)

    # BPF safety verdict: all fields naturally aligned, total size 8-byte aligned, zero unaligned fields
    is_bpf_safe = (len(unaligned_fields) == 0) and is_8byte_aligned

    recommendations: list[str] = []
    if not is_8byte_aligned:
        recommendations.append(
            f"Struct size ({total_size} bytes) is not a multiple of 8. Anchor zero_copy requires 8-byte alignment."
        )
    if total_padding > 16:
        recommendations.append(
            f"High memory fragmentation: {total_padding} bytes of padding detected ({round(padding_ratio * 100, 1)}% waste). Reorder fields from largest alignment to smallest (e.g. u128/u64 -> u32 -> u16 -> u8) to eliminate internal padding holes."
        )
    if unaligned_fields:
        recommendations.append(
            f"Fields {unaligned_fields} violate natural alignment, risking memory traps on Solana BPF."
        )
    if not recommendations:
        recommendations.append("Layout is optimal: strictly 8-byte aligned, zero unaligned fields, zero-allocation BPF safe.")

    return ZeroCopyAuditReport(
        struct_name=struct_name,
        total_size=total_size,
        usable_size=usable_bytes,
        total_padding_bytes=total_padding,
        padding_ratio=padding_ratio,
        is_8byte_aligned=is_8byte_aligned,
        has_discriminator=has_discriminator,
        unaligned_fields=unaligned_fields,
        fields=layouts,
        borsh_estimated_cus=borsh_cus,
        zero_copy_estimated_cus=zero_copy_cus,
        cu_savings_percent=savings_pct,
        is_bpf_safe=is_bpf_safe,
        recommendations=recommendations,
    )


def benchmark_zero_copy_cu(
    total_size: int,
    num_fields: int,
    num_dynamic_vectors: int = 0,
) -> dict[str, Any]:
    """
    Benchmarks theoretical Compute Unit (CU) and memory allocation differences
    between Borsh deserialization and Zero-Copy AccountLoader access.
    """
    # Borsh allocates heap memory for deserialized struct + dynamic heap allocations
    borsh_cus = int(1200 + total_size * 7.2 + num_fields * 95 + num_dynamic_vectors * 850)
    borsh_heap_alloc_bytes = total_size + (num_fields * 16) + (num_dynamic_vectors * 64)

    # Zero-copy does not allocate heap memory; direct pointer cast over account data slice
    zero_copy_cus = 125
    zero_copy_heap_alloc_bytes = 0

    return {
        "account_size_bytes": total_size,
        "num_fields": num_fields,
        "borsh_deserialization": {
            "compute_units": borsh_cus,
            "heap_allocations_bytes": borsh_heap_alloc_bytes,
            "deserialization_mode": "heap_copy",
        },
        "zero_copy_deserialization": {
            "compute_units": zero_copy_cus,
            "heap_allocations_bytes": zero_copy_heap_alloc_bytes,
            "deserialization_mode": "in_place_slice_cast",
        },
        "cu_savings": borsh_cus - zero_copy_cus,
        "cu_savings_multiplier": round(borsh_cus / zero_copy_cus, 1),
        "zero_copy_recommended": total_size >= 128 or num_fields >= 8,
    }

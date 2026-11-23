"""Bounds-checked EFE segment geometry from runtime-verified boundaries.

This module deliberately does not guess prefix, gap, suffix, or record counts.
Those must come from a source-to-runtime comparison. It validates the supplied
geometry against the object's declared extent and reports only segment sizes.
"""
from __future__ import annotations

HEADER_MIN = 46
GPR_BYTES = 3
INSTRUCTION_BYTES = 6


def describe_layout(data: bytes, *, paired_start_gpr: int | None = None,
                    paired_count: int = 0, instruction_start: int | None = None,
                    instruction_count: int = 0,
                    aliases: tuple[tuple[int, int], ...] = ()) -> dict:
    if len(data) < HEADER_MIN:
        raise ValueError("EFE object is shorter than the observed header")
    fx_size = int.from_bytes(data[34:38], "big")
    fx_ucode = int.from_bytes(data[38:40], "big")
    if not HEADER_MIN <= fx_ucode < fx_size <= len(data):
        raise ValueError("invalid observed FxUcode/FxSize bounds")
    if min(paired_count, instruction_count) < 0 or paired_count + instruction_count == 0:
        raise ValueError("record counts must be nonnegative with at least one physical record")
    if (paired_count and paired_start_gpr is None) or (not paired_count and paired_start_gpr is not None):
        raise ValueError("paired start must be supplied exactly when paired records exist")
    if (instruction_count and instruction_start is None) or (not instruction_count and instruction_start is not None):
        raise ValueError("instruction start must be supplied exactly when instruction-only records exist")

    paired_stride = GPR_BYTES + INSTRUCTION_BYTES
    paired_end = None
    if paired_count:
        if paired_start_gpr < fx_ucode:
            raise ValueError("paired records begin before FxUcode")
        paired_end = paired_start_gpr + paired_count * paired_stride
        if paired_end > fx_size:
            raise ValueError("paired records extend beyond FxSize")
    instruction_end = None
    if instruction_count:
        if instruction_start < fx_ucode:
            raise ValueError("instruction records begin before FxUcode")
        instruction_end = instruction_start + instruction_count * INSTRUCTION_BYTES
        if instruction_end > fx_size:
            raise ValueError("instruction records extend beyond FxSize")
        if paired_end is not None and instruction_start < paired_end:
            raise ValueError("instruction-only records overlap paired records")

    alias_pairs = tuple(aliases)
    if len(set(alias_pairs)) != len(alias_pairs) or any(i < 0 or j < 0 or i == j for i, j in alias_pairs):
        raise ValueError("invalid or duplicate instruction alias")
    if len({i for i, _ in alias_pairs}) != len(alias_pairs):
        raise ValueError("one active instruction cannot have multiple source aliases")

    first_segment = paired_start_gpr if paired_count else instruction_start
    code_end = instruction_end if instruction_end is not None else paired_end
    assert first_segment is not None and code_end is not None
    gap = instruction_start - paired_end if paired_count and instruction_count else None
    if gap is not None and gap < 0:
        raise ValueError("negative segment gap")
    return {
        "fx_ucode": fx_ucode,
        "fx_size": fx_size,
        "paired_records": ({"offset": paired_start_gpr, "count": paired_count,
                            "stride": paired_stride, "length": paired_count * paired_stride}
                           if paired_count else None),
        "instruction_only_records": ({"offset": instruction_start, "count": instruction_count,
                                      "stride": INSTRUCTION_BYTES,
                                      "length": instruction_count * INSTRUCTION_BYTES}
                                     if instruction_count else None),
        "aliases": [{"active_index": i, "source_active_index": j} for i, j in alias_pairs],
        "unclassified": {
            "prefix_bytes_from_FxUcode": first_segment - fx_ucode,
            "gap_bytes_between_segments": gap,
            "suffix_bytes_to_FxSize": fx_size - code_end,
            "outside_declared_extent": len(data) - fx_size,
        },
        "payload_bytes_disclosed": False,
    }

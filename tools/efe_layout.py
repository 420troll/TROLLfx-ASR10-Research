#!/usr/bin/env python3
"""Bounds-checked decoder for experimentally verified EFE code layouts.

This decodes segment boundaries only. It does not interpret opcodes, suffix
records, parameter tables, or any other unverified fields.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

HEADER_MIN = 46
COMMON_PREFIX_BYTES = 11
MIXED_GAP_BYTES = 3


def decode_layout(data: bytes, paired_count: int, instruction_only_count: int) -> dict:
    if len(data) < HEADER_MIN:
        raise ValueError("EFE object is shorter than the observed fixed header")
    fx_size = int.from_bytes(data[34:38], "big")
    fx_ucode = int.from_bytes(data[38:40], "big")
    if not HEADER_MIN <= fx_ucode < fx_size <= len(data):
        raise ValueError("invalid observed FxUcode/FxSize bounds")
    if paired_count < 0 or instruction_only_count < 0 or paired_count + instruction_only_count == 0:
        raise ValueError("record counts must be nonnegative with at least one instruction")
    if paired_count > 0 and instruction_only_count == 0:
        raise ValueError("paired-only layouts have not been verified")
    mixed = paired_count > 0 and instruction_only_count > 0
    paired_start = fx_ucode + COMMON_PREFIX_BYTES
    paired_bytes = paired_count * 9
    gap_start = paired_start + paired_bytes
    instruction_start = gap_start + (MIXED_GAP_BYTES if mixed else 0)
    instruction_bytes = instruction_only_count * 6
    code_end = instruction_start + instruction_bytes
    if code_end > fx_size:
        raise ValueError("declared records extend beyond FxSize")
    # This experimental grammar has only established the mixed gap. A
    # single-region layout has no intervening gap.
    return {
        "fx_ucode": fx_ucode,
        "fx_size": fx_size,
        "prefix": {"offset": fx_ucode, "length": COMMON_PREFIX_BYTES},
        "paired_records": ({"offset": paired_start, "count": paired_count,
                            "stride": 9, "length": paired_bytes} if paired_count else None),
        "mixed_gap": ({"offset": gap_start, "length": MIXED_GAP_BYTES} if mixed else None),
        "instruction_only_records": {"offset": instruction_start,
                                     "count": instruction_only_count,
                                     "stride": 6, "length": instruction_bytes},
        "suffix": {"offset": code_end, "length": fx_size - code_end},
        "outside_declared_extent": len(data) - fx_size,
        "segment_sha256": {
            "prefix": hashlib.sha256(data[fx_ucode:paired_start]).hexdigest(),
            "paired_records": hashlib.sha256(data[paired_start:gap_start]).hexdigest() if paired_count else None,
            "mixed_gap": hashlib.sha256(data[gap_start:instruction_start]).hexdigest() if mixed else None,
            "instruction_only_records": hashlib.sha256(data[instruction_start:code_end]).hexdigest(),
            "suffix": hashlib.sha256(data[code_end:fx_size]).hexdigest(),
        },
        "payload_bytes_disclosed": False,
    }


def decode_file(path: Path, paired_count: int, instruction_only_count: int) -> dict:
    return decode_layout(path.read_bytes(), paired_count, instruction_only_count)

#!/usr/bin/env python3
"""Interleave private ASR-10 high/low ROM byte-lane copies for Ghidra.

Writes only to an explicit destination outside this repository. Inputs are
read-only; existing output files are never overwritten.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def interleave(high: bytes, low: bytes) -> bytes:
    if len(high) != len(low):
        raise ValueError("high and low ROM lanes must have equal length")
    out = bytearray(len(high) * 2)
    out[0::2] = high
    out[1::2] = low
    return bytes(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("high", type=Path, help="private high-byte ROM copy")
    parser.add_argument("low", type=Path, help="private low-byte ROM copy")
    parser.add_argument("output", type=Path, help="new private interleaved output path")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    if output == repo or repo in output.parents:
        parser.error("output must be outside the Git repository")
    if output.exists():
        parser.error("output already exists; choose a new private destination")
    try:
        data = interleave(args.high.read_bytes(), args.low.read_bytes())
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    print(f"wrote {len(data)} bytes to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

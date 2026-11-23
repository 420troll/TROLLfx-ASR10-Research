#!/usr/bin/env python3
"""Validate and summarize private ES5510 capture files; never prints DSP bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

MAGIC = b"ES5510C\0"
HEADER_BYTES = 44
SPECIAL_COUNT = 22
STATE_BYTES = 74


def read_capture(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) < HEADER_BYTES or raw[:8] != MAGIC:
        raise ValueError("not an ES5510C capture")
    version, header, nins, ngpr, nspecial, ndram, flags, nstate, payload = struct.unpack_from("<9I", raw, 8)
    expected_payload = nins * 6 + ngpr * 3 + nspecial * 3 + nstate + ndram * 2
    if version != 1 or header != HEADER_BYTES:
        raise ValueError(f"unsupported capture version/header: {version}/{header}")
    if (nins, ngpr, nspecial, nstate) != (160, 192, SPECIAL_COUNT, STATE_BYTES):
        raise ValueError("unexpected ES5510 section dimensions")
    if flags != 1 or payload != expected_payload or len(raw) != header + payload:
        raise ValueError("capture length/flags do not match header")

    p = header
    instruction_bytes = raw[p:p + nins * 6]; p += len(instruction_bytes)
    gpr_bytes = raw[p:p + ngpr * 3]; p += len(gpr_bytes)
    special_bytes = raw[p:p + nspecial * 3]; p += len(special_bytes)
    state = raw[p:p + nstate]; p += len(state)
    dram = raw[p:]
    instructions = [int.from_bytes(instruction_bytes[i:i + 6], "big") for i in range(0, len(instruction_bytes), 6)]
    ends = [i for i, word in enumerate(instructions) if ((word >> 12) & 15) == 15]
    active_words = ends[0] + 1 if ends else None
    memory = {
        "memsiz": struct.unpack_from("<I", state, 7)[0],
        "memmask": struct.unpack_from("<I", state, 11)[0],
        "memincrement": struct.unpack_from("<I", state, 15)[0],
        "dram_mask": struct.unpack_from("<I", state, 19)[0],
        "memshift": state[23],
    }
    return {
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "file_bytes": len(raw),
        "version": version,
        "program": {
            "words": nins,
            "active_words_through_first_END": active_words,
            "END_indices": ends,
            "all_160_words_sha256": hashlib.sha256(instruction_bytes).hexdigest(),
            "active_program_sha256": hashlib.sha256(instruction_bytes[:active_words * 6]).hexdigest() if active_words else None,
        },
        "registers": {
            "gpr_count": ngpr,
            "gpr_sha256": hashlib.sha256(gpr_bytes).hexdigest(),
            "special_count": nspecial,
            "special_sha256": hashlib.sha256(special_bytes).hexdigest(),
        },
        "runtime": {
            "state_bytes": nstate,
            "control": {"host_control": state[0], "host_serial": state[1], "ram_ctl": state[2],
                        "halted": bool(state[3]), "halt_asserted": bool(state[4]), "pc": state[5], "refresh_pc": state[6]},
            "memory_configuration": memory,
            "dram_words": ndram,
            "dram_sha256": hashlib.sha256(dram).hexdigest(),
            "dram_nonzero_words": sum(1 for i in range(0, len(dram), 2) if dram[i] or dram[i + 1]),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(read_capture(args.capture), indent=2))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

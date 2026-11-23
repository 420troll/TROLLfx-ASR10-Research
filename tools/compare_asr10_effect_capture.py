#!/usr/bin/env python3
"""Compare a private ASR-10 EFE object with a private ES5510 capture/log.

The report contains offsets, counts, and hashes only. It never prints DSP
instruction words, GPR values, source payload bytes, or host-write contents.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

MAGIC = b"ES5510C\0"
HEADER_BYTES = 44


def capture_sections(path: Path) -> tuple[bytes, bytes, bytes, int]:
    raw = path.read_bytes()
    if len(raw) < HEADER_BYTES or raw[:8] != MAGIC:
        raise ValueError("not an ES5510C capture")
    version, header, nins, ngpr, nspecial, ndram, flags, nstate, payload = struct.unpack_from("<9I", raw, 8)
    expected = nins * 6 + ngpr * 3 + nspecial * 3 + nstate + ndram * 2
    if (version, header, nins, ngpr, nspecial, ndram, flags, nstate) != (
        1, HEADER_BYTES, 160, 192, 22, 1 << 20, 1, 74
    ):
        raise ValueError("unsupported capture layout")
    if payload != expected or len(raw) != HEADER_BYTES + payload:
        raise ValueError("capture is truncated or inconsistent")
    p = HEADER_BYTES
    instructions = raw[p:p + nins * 6]
    p += nins * 6
    gprs = raw[p:p + ngpr * 3]
    p += ngpr * 3 + nspecial * 3 + nstate
    dram = raw[p:]
    ends = [i for i in range(nins) if ((int.from_bytes(instructions[i * 6:i * 6 + 6], "big") >> 12) & 15) == 15]
    if not ends:
        raise ValueError("capture has no END instruction")
    return instructions[:(ends[0] + 1) * 6], gprs, dram, ends[0] + 1


def parse_host_log(path: Path, at_time: float | None = None, before_line: int | None = None) -> tuple[dict[int, tuple[int, int | None, str]], dict[int, int]]:
    instructions: dict[int, tuple[int, int | None, str]] = {}
    gprs: dict[int, int] = {}
    for line_number, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        if before_line is not None and line_number >= before_line:
            break
        if at_time is not None:
            timestamp = re.search(r"\bt=([0-9.]+)", line)
            if timestamp and float(timestamp.group(1)) > at_time + 1e-9:
                continue
        m = re.search(r"ESPHOST (?:event=\d+ cycles=\d+ frame=\d+ pc=[0-9a-f]{6,8} )?(both|instr) ([0-9a-f]{2}) <- ([0-9a-f]{12})(?: / ([0-9a-f]{6}))?", line, re.I)
        if m:
            index = int(m.group(2), 16)
            instructions[index] = (int(m.group(3), 16), int(m.group(4), 16) if m.group(4) else None, m.group(1).lower())
        m = re.search(r"ESPHOST (?:event=\d+ cycles=\d+ frame=\d+ pc=[0-9a-f]{6,8} )?gpr ([0-9a-f]{2}) <- ([0-9a-f]{6})", line, re.I)
        if m:
            gprs[int(m.group(1), 16)] = int(m.group(2), 16)
    return instructions, gprs


def compare(object_path: Path, capture_path: Path, host_log_path: Path,
            expected_name: str | None = None, at_time: float | None = None,
            before_line: int | None = None) -> dict:
    source = object_path.read_bytes()
    if len(source) < 46:
        raise ValueError("EFE object is shorter than its fixed header")
    name = "".join(chr(c) for c in source[10:34:2] if 32 <= c < 127).strip()
    fx_size = int.from_bytes(source[34:38], "big")
    fx_ucode = int.from_bytes(source[38:40], "big")
    if not (46 <= fx_ucode < fx_size <= len(source)):
        raise ValueError("invalid EFE size or FxUcode pointer")
    if expected_name and name.casefold() != expected_name.casefold():
        raise ValueError(f"EFE name mismatch: expected {expected_name!r}, got {name!r}")
    host_log_text = host_log_path.read_text(errors="replace")
    if expected_name and expected_name.casefold() not in host_log_text.casefold():
        raise ValueError("expected effect name is absent from the host log")

    code, gpr_state, _dram, active_count = capture_sections(capture_path)
    host_instructions, _host_gprs = parse_host_log(host_log_path, at_time, before_line)
    words = [code[i:i + 6] for i in range(0, len(code), 6)]
    host_matches = sum(host_instructions.get(i, (None, None, ""))[0] == int.from_bytes(word, "big") for i, word in enumerate(words))
    if host_matches != active_count:
        raise ValueError(f"host instruction commits match only {host_matches}/{active_count} active words")

    modes: list[str] = []
    source_candidates: list[list[int]] = []
    source_words_unique = True
    candidate = source[fx_ucode:fx_size]
    for i, word in enumerate(words):
        event = host_instructions.get(i)
        if event is None or event[2] not in ("both", "instr"):
            raise ValueError(f"active host instruction {i} has no supported instruction commit")
        modes.append(event[2])
        positions: list[int] = []
        start = 0
        while True:
            found = candidate.find(word, start)
            if found < 0:
                break
            if positions or start > 0:
                source_words_unique = False
            absolute = fx_ucode + found
            if event[2] == "both" and event[1] is not None and absolute >= fx_ucode + 3:
                source_gpr = int.from_bytes(source[absolute - 3:absolute], "big")
                if source_gpr == event[1]:
                    positions.append(absolute)
            elif event[2] == "instr":
                positions.append(absolute)
            start = found + 1
        if not positions:
            raise ValueError(f"instruction {i} has no source occurrence consistent with its host commit")
        source_candidates.append(positions)

    # A source layout is one paired run followed by one instruction-only run.
    # Requiring each run's observed stride lets the host GPR values disambiguate
    # repeated instruction words without guessing an occurrence.
    if "both" in modes and modes != ["both"] * modes.count("both") + ["instr"] * modes.count("instr"):
        raise ValueError("host commits do not form one paired run followed by one instruction-only run")
    paired_count = modes.count("both")
    instruction_only_count = active_count - paired_count
    # Transaction payload widths are defined by the host protocol: one 3-byte
    # GPR initializer and one 6-byte instruction, or an instruction alone.
    # Segment starts, gaps, and suffixes are inferred from matching source
    # candidates instead of being fixed to a single EFE template.
    paired_stride = 3 + 6
    instruction_stride = 6
    source_paths: list[tuple[tuple[int, ...], tuple[int, ...]]] = [
        ((pos,), ()) for pos in source_candidates[0]
    ]
    for i in range(1, active_count):
        next_paths: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
        mode = modes[i]
        for pos in source_candidates[i]:
            for offsets, aliases in source_paths:
                previous_source_index = next((j for j in range(len(offsets) - 1, -1, -1) if j not in aliases), None)
                if previous_source_index is None:
                    continue
                prior = offsets[previous_source_index]
                if mode == "both":
                    valid, alias = pos == prior + paired_stride, False
                else:
                    alias = pos in offsets
                    has_tail_record = any(j >= paired_count and j not in aliases for j in range(i))
                    if has_tail_record:
                        valid = alias or pos == prior + instruction_stride
                    else:
                        valid = alias or pos >= prior + instruction_stride
                if valid:
                    candidate = (offsets + (pos,), aliases + ((i,) if alias else ()))
                    if candidate not in next_paths:
                        next_paths.append(candidate)
        source_paths = next_paths
        if not source_paths:
            raise ValueError("capture matches the EFE, but no source layout satisfies the observed host records")
        if len(source_paths) > 4096:
            raise ValueError("capture matches the EFE, but candidate source layouts are excessively ambiguous")
    if len(source_paths) != 1:
        raise ValueError("capture matches the EFE, but source offsets remain ambiguous")
    offsets, alias_indices = source_paths[0]

    paired_values_match = all(
        modes[i] != "both" or source[off - 3:off] == host_instructions[i][1].to_bytes(3, "big")
        for i, off in enumerate(offsets)
    )
    instruction_only_commits_match = all(modes[i] == "instr" for i in range(paired_count, active_count))
    paired_layout = all(offsets[i] == offsets[0] + paired_stride * i for i in range(paired_count))
    instruction_only_offsets = [offsets[i] for i in range(paired_count, active_count) if i not in alias_indices]
    instruction_only_layout = all(
        instruction_only_offsets[i] == instruction_only_offsets[0] + instruction_stride * i
        for i in range(len(instruction_only_offsets))
    ) if instruction_only_offsets else True
    if not (paired_values_match and instruction_only_commits_match and paired_layout and instruction_only_layout):
        raise ValueError("capture matches the EFE, but the paired/instruction-only layout did not validate")

    segment_start = offsets[0] - 3 if paired_count else offsets[0]
    paired_end = offsets[paired_count - 1] + 6 if paired_count else segment_start
    instruction_only_start = instruction_only_offsets[0] if instruction_only_offsets else None
    gap_bytes = max(0, instruction_only_start - paired_end) if paired_count and instruction_only_start is not None else 0
    code_end = max(instruction_only_offsets or list(offsets)) + instruction_stride
    return {
        "effect_name": name,
        "source_object": object_path.name,
        "source_object_bytes": len(source),
        "source_object_sha256": hashlib.sha256(source).hexdigest(),
        "fx_size": fx_size,
        "fx_ucode": fx_ucode,
        "naive_six_byte_candidate_words": (fx_size - fx_ucode) // 6,
        "capture_active_instructions": active_count,
        "capture_program_sha256": hashlib.sha256(code).hexdigest(),
        "capture_gpr_snapshot_sha256": hashlib.sha256(gpr_state).hexdigest(),
        "host_instruction_commits_exact_match": host_matches,
        "source_instruction_words_unique": source_words_unique,
        "source_instruction_locations_resolved_by_layout": True,
        "source_offsets": {
            "paired_records_start_gpr": segment_start if paired_count else None,
            "paired_records_count": paired_count,
            "paired_records_stride_bytes": paired_stride if paired_count else None,
            "instruction_only_start": instruction_only_start,
            "instruction_only_count": len(instruction_only_offsets),
            "host_instruction_only_commits": instruction_only_count,
            "instruction_only_stride_bytes": instruction_stride if instruction_only_offsets else None,
            "source_instruction_alias_count": len(alias_indices),
            "source_instruction_aliases": [
                {"active_index": i, "source_active_index": offsets.index(offsets[i])}
                for i in alias_indices
            ],
            "first_live_instruction": offsets[0],
            "last_live_instruction_end_exclusive": code_end,
            "unclassified_prefix_bytes_from_FxUcode": segment_start - fx_ucode,
            "unclassified_bytes_before_instruction_only": gap_bytes,
            "unclassified_suffix_bytes_to_FxSize": fx_size - code_end,
        },
        "host_commit_gpr_bytes_match_source_for_paired_records": paired_values_match,
        "remaining_host_commits_are_instruction_only": instruction_only_commits_match,
        "hostlog_unique_gpr_only_addresses": len(_host_gprs),
        "payload_bytes_disclosed": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("effect_object", type=Path)
    p.add_argument("capture", type=Path)
    p.add_argument("host_log", type=Path)
    p.add_argument("--expected-name")
    p.add_argument("--at-time", type=float, help="use only timestamped host writes at or before this emulator time")
    p.add_argument("--snapshot-id", type=int, help="cut writes at the ESP_ROM_STATE marker for this effect ID")
    args = p.parse_args()
    try:
        before_line = None
        if args.snapshot_id is not None:
            marker = re.compile(rf"^ESP_ROM_STATE id={args.snapshot_id:02d} ")
            with args.host_log.open(errors="replace") as f:
                before_line = next((n for n, line in enumerate(f, 1) if marker.search(line)), None)
            if before_line is None:
                raise ValueError(f"no ESP_ROM_STATE marker for effect {args.snapshot_id:02d}")
        print(json.dumps(compare(args.effect_object, args.capture, args.host_log, args.expected_name,
                                 args.at_time, before_line), indent=2))
    except (OSError, ValueError) as exc:
        p.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

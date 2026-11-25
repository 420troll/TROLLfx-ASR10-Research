#!/usr/bin/env python3
"""Recompute route-dependent HALL DECAY register evidence from private trace JSON."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ORDER = ["0x6e", "0x5b", "0x03", "0x04", "0x05"]


def signed16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def helper_registers(raw):
    """Independent implementation of the documented 68000 coefficient arithmetic."""
    d2 = raw << 8
    product = signed16(d2) * signed16(-d2)
    d5 = ((product + 0x3FFFFFFF) & 0xFFFFFFFF)
    if d5 & 0x80000000:
        d5 -= 0x100000000
    g03 = (d2 << 8) & 0xFFFFFF
    return {0x03: g03, 0x04: (-g03) & 0xFFFFFF, 0x05: (d5 >> 7) & 0xFFFFFF}


def last_parameter_group(step):
    writes = step.get("register_writes", [])
    found = []
    for i in range(len(writes) - len(ORDER) + 1):
        group = writes[i:i + len(ORDER)]
        if [w.get("gpr", "").lower() for w in group] == ORDER:
            found.append({int(w["gpr"], 16): int(w["value24"], 16) for w in group})
    return found[-1] if found else None


def shown_value(text):
    match = re.search(r"=(\d+)\s*$", text)
    return int(match.group(1)) if match else None


def summarize(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    by_direction = {"up": {}, "down": {}}
    for step in payload.get("steps", []):
        target = shown_value(step.get("to_display", ""))
        group = last_parameter_group(step)
        if target is None or group is None:
            continue
        direction = step.get("direction") or (
            "up" if step.get("segment") in ("to_max", "restore") else
            "down" if step.get("segment") in ("to_origin", "to_min") else None)
        if direction in by_direction:
            by_direction[direction][target] = group
    shared = sorted(set(by_direction["up"]) & set(by_direction["down"]) & set(range(1, 99)))
    differing = [v for v in shared if by_direction["up"][v][0x6E] != by_direction["down"][v][0x6E]]
    helper_total = helper_matches = 0
    for direction in ("up", "down"):
        for value in shared:
            group = by_direction[direction][value]
            raw = (group[0x6E] >> 16) & 0x7F
            expected = helper_registers(raw)
            helper_total += 1
            helper_matches += all(group[k] == expected[k] for k in (0x03, 0x04, 0x05))
    initial = payload.get("events", [{}])[0]
    return {
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "step_count": len(payload.get("steps", [])),
        "shared_interior_display_values": len(shared),
        "gpr6e_direction_difference_count": len(differing),
        "gpr6e_direction_difference_values": differing,
        "first_lcd_event_cycles": initial.get("cycles"),
        "first_lcd_event_frame": initial.get("frame"),
        "helper_03_04_05_match_count": helper_matches,
        "helper_03_04_05_total_directional_cases": helper_total,
        "register_order": ORDER,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace", type=Path, help="private Codex 1 step-level HALL range JSON")
    ap.add_argument("--compare", type=Path, action="append", default=[],
                    help="additional private summaries to compare boot/start metadata")
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    result = {"schema": "trollfx-asr10-hall-decay-independent-trace-audit-v1",
              "primary": summarize(args.trace),
              "comparisons": [summarize(p) for p in args.compare]}
    starts = {(r.get("first_lcd_event_cycles"), r.get("first_lcd_event_frame"))
              for r in [result["primary"], *result["comparisons"]]}
    result["independent_boot_evidence"] = (
        "INCONCLUSIVE_NO_UNIQUE_PROCESS_OR_BOOT_ID" if len(starts) <= 1 else
        "DISTINCT_START_COORDINATES_BUT_STILL_REQUIRES_PROCESS_PROVENANCE")
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()

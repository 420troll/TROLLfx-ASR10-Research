#!/usr/bin/env python3
"""Independently compare OS 3.53 HALL decay sweeps with the captured OS table.

This tool does not import Codex 1's coefficient or raw/display implementation.
Give it private sweep JSON, the private OS memory dump, and CLI PIDs recorded by
the caller. It emits aggregate evidence only.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

GROUP_ORDER = ["0x6e", "0x5b", "0x03", "0x04", "0x05"]
TABLE_LINE = re.compile(r"^([0-9A-F]{8}):((?:\s+[0-9A-F]{2}){1,16})$", re.I)


def parse_os_table(path):
    addressed = {}
    for line in path.read_text(errors="replace").splitlines():
        match = TABLE_LINE.match(line.strip())
        if not match:
            continue
        start = int(match.group(1), 16)
        for index, token in enumerate(match.group(2).split()):
            addressed[start + index] = int(token, 16)
    base = 0xFFF825A9
    table = [addressed.get(base + i) for i in range(128)]
    if any(value is None for value in table):
        raise ValueError("private OS dump does not contain the full 128-byte HALL display table")
    if set(table) != set(range(100)):
        raise ValueError("captured table does not map exactly onto display values 0..99")
    return table


def parameter_group(step):
    records = parameter_group_records(step)
    return None if records is None else {
        int(row["gpr"], 16): int(row["value24"], 16) for row in records
    }


def parameter_group_records(step):
    writes = step.get("register_writes", [])
    groups = []
    for index in range(len(writes) - len(GROUP_ORDER) + 1):
        candidate = writes[index:index + len(GROUP_ORDER)]
        if [row.get("gpr", "").lower() for row in candidate] == GROUP_ORDER:
            groups.append(candidate)
    return groups[-1] if groups else None


def lcd_value(text):
    match = re.search(r"DECAY TIME\s*=\s*(\d+)", text or "")
    return None if not match else int(match.group(1))


def read_sweep(path):
    document = json.loads(path.read_text())
    rows = {"up": {}, "down": {}}
    order_failures = 0
    for step in document.get("steps", []):
        if not step.get("complete"):
            continue
        value = lcd_value(step.get("to_display"))
        group = parameter_group(step)
        if value is None or group is None:
            continue
        direction = step.get("direction")
        if direction not in rows:
            direction = {"to_max": "up", "restore": "up", "to_min": "down", "to_origin": "down"}.get(step.get("segment"))
        if direction not in rows:
            continue
        rows[direction][value] = group
        ordered = [item.get("gpr", "").lower() for item in step.get("register_writes", [])]
        if not any(ordered[i:i + 5] == GROUP_ORDER for i in range(max(0, len(ordered) - 4))):
            order_failures += 1
    return document, rows, order_failures


def derived_registers(raw):
    # Independent 68000 arithmetic reconstruction. Clamp bounds are inferred
    # from the original OS GPR 03 plateau over the observed raw sweep.
    coefficient = max(12, min(76, raw))
    x = coefficient << 8
    product = ((x & 0xFFFF) - (0x10000 if x & 0x8000 else 0)) * (
        ((-x) & 0xFFFF) - (0x10000 if ((-x) & 0x8000) else 0))
    intermediate = (product + 0x3FFFFFFF) & 0xFFFFFFFF
    if intermediate & 0x80000000:
        intermediate -= 0x100000000
    gpr03 = (x << 8) & 0xFFFFFF
    return {0x03: gpr03, 0x04: (-gpr03) & 0xFFFFFF,
            0x05: (intermediate >> 7) & 0xFFFFFF}


def summarize(sweep_path, table_path, pid_path):
    document, directional, order_failures = read_sweep(sweep_path)
    table = parse_os_table(table_path)
    display_codes = {}
    for raw, display in enumerate(table):
        display_codes.setdefault(display, []).append(raw)
    duplicate_pairs = [{"display": display, "raw_low": codes[0], "raw_high": codes[1]}
                       for display, codes in display_codes.items() if len(codes) == 2]
    unexpected_bucket_sizes = {str(k): len(v) for k, v in display_codes.items() if len(v) not in (1, 2)}

    mismatches = []
    for display, codes in display_codes.items():
        for direction, expected_raw in (("up", codes[0]), ("down", codes[-1])):
            group = directional[direction].get(display)
            if group is None:
                continue
            raw = (group[0x6E] >> 16) & 0x7F
            if raw != expected_raw:
                mismatches.append({"display": display, "direction": direction,
                                   "observed_raw": raw, "table_raw": expected_raw})

    group_counts = {"gpr03_04_05_checked": 0, "gpr03_04_05_match": 0,
                    "gpr6e_raw_match": 0, "gpr5b_low_byte_match": 0,
                    "gpr5b_full_match": 0, "unbounded_03_04_05_checked": 0,
                    "unbounded_03_04_05_match": 0}
    gpr5b_by_raw = {}
    raw_codes_seen = set()
    for direction in ("up", "down"):
        for display, group in directional[direction].items():
            raw = (group[0x6E] >> 16) & 0x7F
            raw_codes_seen.add(raw)
            group_counts["gpr6e_raw_match"] += group[0x6E] == (raw << 16)
            group_counts["gpr5b_low_byte_match"] += (group[0x5B] & 0xFF) == raw
            gpr5b_by_raw.setdefault(raw, set()).add(group[0x5B])
            expected = derived_registers(raw)
            group_counts["gpr03_04_05_checked"] += 1
            group_counts["gpr03_04_05_match"] += all(group[gpr] == expected[gpr] for gpr in expected)
            tag = min(8, 127 - raw)
            group_counts["gpr5b_full_match"] += group[0x5B] == ((tag << 16) | raw)
            unbounded = derived_registers_unbounded(raw)
            group_counts["unbounded_03_04_05_checked"] += 1
            group_counts["unbounded_03_04_05_match"] += all(
                group[gpr] == unbounded[gpr] for gpr in (0x03, 0x04, 0x05))

    shared = sorted(set(directional["up"]) & set(directional["down"]) & set(range(1, 99)))
    route_differences = [display for display in shared
        if directional["up"][display][0x6E] != directional["down"][display][0x6E]]
    endpoint_union = set(directional["up"]) | set(directional["down"])
    pids = [line.strip() for line in pid_path.read_text().splitlines() if line.strip()]
    return {
        "trace_sha256": hashlib.sha256(sweep_path.read_bytes()).hexdigest(),
        "cli_pid": pids[0] if pids else None,
        "sweep_complete": bool(document.get("sweep_complete")),
        "observed_display_values": sorted(endpoint_union),
        "both_direction_interior_count": len(shared),
        "all_display_values_observed": endpoint_union == set(range(100)),
        "os_table_raw_codes": 128,
        "os_table_display_values": len(display_codes),
        "duplicate_display_count": len(duplicate_pairs),
        "duplicate_pairs": duplicate_pairs,
        "unexpected_bucket_sizes": unexpected_bucket_sizes,
        "raw_direction_difference_values": route_differences,
        "raw_matches_os_table_route": len(mismatches) == 0,
        "raw_route_mismatches": mismatches,
        "write_order_failures": order_failures,
        "register_checks": group_counts,
        "gpr5b_raw_codes_observed": len(raw_codes_seen),
        "gpr5b_distinct_full_values": len({value for values in gpr5b_by_raw.values() for value in values}),
        "gpr5b_unstable_raw_codes": [raw for raw, values in gpr5b_by_raw.items() if len(values) > 1],
    }


def derived_registers_unbounded(raw):
    """Reproduce the older QA helper's unclamped operand hypothesis."""
    x = raw << 8
    s16 = lambda v: (v & 0xFFFF) - (0x10000 if v & 0x8000 else 0)
    product = s16(x) * s16(-x)
    acc = (product + 0x3FFFFFFF) & 0xFFFFFFFF
    if acc & 0x80000000:
        acc -= 0x100000000
    g03 = (x << 8) & 0xFFFFFF
    return {0x03: g03, 0x04: (-g03) & 0xFFFFFF, 0x05: (acc >> 7) & 0xFFFFFF}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep", type=Path, required=True)
    parser.add_argument("--table-dump", type=Path, required=True)
    parser.add_argument("--cli-pid", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.sweep, args.table_dump, args.cli_pid)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "duplicate_pairs"}, indent=2))


if __name__ == "__main__":
    main()
